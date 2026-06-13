"""The strategy: dual-momentum sector rotation with a regime filter.

This is the Tier-1, best-evidence setup from the research:
  * RELATIVE momentum  — rank sectors by blended trailing return, hold the top N.
  * ABSOLUTE momentum  — only hold a winner if it also beats cash (else go
                         defensive). This is the "crash filter" that historically
                         cut drawdowns versus buy-and-hold.
  * REGIME filter      — only hold if price > its 200-day SMA.

`weights_on(date)` is the single source of truth for target allocation and is
used by BOTH the backtester and live execution — so what you test is what you
trade. It is strictly point-in-time: it only looks at prices up to `date`.

Refine here by editing the selection logic, or just tune config.yaml.
"""
from __future__ import annotations

import pandas as pd

from .config import Config
from .indicators import above_sma, blended_momentum, total_return, sma


class StrategyEngine:
    def __init__(self, prices: pd.DataFrame, cfg: Config):
        self.prices = prices
        self.cfg = cfg
        s = cfg.strategy
        self.risk_assets = [t for t in cfg.risk_assets if t in prices.columns]
        self.defensive = cfg.defensive_asset
        self.cash = cfg.cash_proxy

        # Precompute signal frames once (vectorized) for speed.
        self._mom = blended_momentum(
            prices[self.risk_assets], s["momentum_lookbacks_days"], s["momentum_weights"]
        )
        self._abs_lb = s["absolute_momentum_lookback_days"]
        self._abs_mom = total_return(prices, self._abs_lb)  # all tickers incl. cash
        self._regime_ok = (
            above_sma(prices[self.risk_assets], s["regime_sma_days"])
            if s["use_regime_filter"]
            else None
        )

    def warmup_days(self) -> int:
        """Rows of history needed before the first valid signal."""
        s = self.cfg.strategy
        return max([*s["momentum_lookbacks_days"], self._abs_lb, s["regime_sma_days"]])

    def weights_on(self, date: pd.Timestamp) -> pd.Series:
        """Target weights (sum<=1) for the close of `date`. Defensive/cash holds remainder."""
        cfg = self.cfg
        s = cfg.strategy
        if date not in self.prices.index:
            # snap to most recent available trading day <= date
            prior = self.prices.index[self.prices.index <= date]
            if len(prior) == 0:
                return pd.Series(dtype=float)
            date = prior[-1]

        mom = self._mom.loc[date].dropna()
        if mom.empty:
            return self._all_defensive()

        # 1) RELATIVE momentum: rank, take top N candidates.
        ranked = mom.sort_values(ascending=False)
        candidates = list(ranked.index[: s["top_n"]])

        # 2/3) Filter each candidate by absolute momentum + regime.
        held: list[str] = []
        for t in candidates:
            if s["use_absolute_momentum"] and not self._passes_absolute(t, date):
                continue
            if s["use_regime_filter"] and not bool(self._regime_ok.loc[date, t]):
                continue
            held.append(t)

        return self._allocate(held)

    # ------------------------------------------------------------------ helpers
    def _passes_absolute(self, ticker: str, date: pd.Timestamp) -> bool:
        """Own trailing return must beat the cash proxy over the same window."""
        try:
            asset_r = self._abs_mom.loc[date, ticker]
            cash_r = self._abs_mom.loc[date, self.cash] if self.cash in self._abs_mom else 0.0
        except KeyError:
            return False
        if pd.isna(asset_r):
            return False
        if pd.isna(cash_r):
            cash_r = 0.0
        return asset_r > cash_r

    def _allocate(self, held: list[str]) -> pd.Series:
        """Equal-weight held sleeves, cap per-position, park remainder defensively."""
        risk = self.cfg.risk
        target_expo = float(risk["target_total_exposure"])
        cap = float(risk["max_weight_per_position"])
        w = pd.Series(0.0, index=sorted(set(self.prices.columns)))
        if held:
            each = min(target_expo / len(held), cap)
            for t in held:
                w[t] = each
        # Whatever isn't allocated to risk sleeves goes defensive (cash if CASH).
        invested = w.sum()
        remainder = 1.0 - invested
        if remainder > 1e-9 and self.defensive.upper() != "CASH":
            w[self.defensive] = w.get(self.defensive, 0.0) + remainder
        return w[w > 0]

    def _all_defensive(self) -> pd.Series:
        if self.defensive.upper() == "CASH":
            return pd.Series(dtype=float)
        return pd.Series({self.defensive: 1.0})
