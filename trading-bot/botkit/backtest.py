"""Point-in-time rebalance backtester + performance metrics.

Deliberately simple and readable rather than a framework: a rebalance loop you
can trace end-to-end. The key correctness properties (the things that make
backtests lie when violated):

  * NO LOOK-AHEAD: weights decided at the close of rebalance day `r` are applied
    starting the NEXT trading day. Signals only use prices <= r.
  * COSTS ON TURNOVER: every rebalance pays commission + slippage on the traded
    fraction. Thin edges die here — that's the point of modeling it.
  * KILL-SWITCH IN THE LOOP: the drawdown circuit breaker sees running equity,
    exactly as it would live.

What it does NOT model (be honest about it): intraday fills, partial fills,
survivorship in single stocks (ETFs largely sidestep this), borrow costs,
taxes/wash-sales. Treat results as an upper bound on reality.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config
from .indicators import drawdown
from .risk import RiskManager
from .strategy import StrategyEngine

TRADING_DAYS = 252


@dataclass
class BacktestResult:
    equity: pd.Series          # daily portfolio equity
    weights_log: pd.DataFrame  # target weights at each rebalance
    metrics: dict
    data_source: str

    def summary(self) -> str:
        m = self.metrics
        lines = [
            "",
            "=" * 58,
            f"  BACKTEST RESULTS   (data: {self.data_source})",
            "=" * 58,
            f"  Period            {m['start']:%Y-%m-%d} -> {m['end']:%Y-%m-%d}  ({m['years']:.1f}y)",
            f"  Final equity      ${m['final_equity']:,.0f}  (start ${m['initial']:,.0f})",
            f"  Total return      {m['total_return']:+.1%}",
            f"  CAGR              {m['cagr']:+.2%}",
            f"  Volatility (ann)  {m['vol']:.2%}",
            f"  Sharpe (rf=0)     {m['sharpe']:.2f}",
            f"  Max drawdown      {m['max_drawdown']:.2%}",
            f"  % positive months {m['pct_positive_months']:.0%}",
            f"  Time in market    {m['time_in_market']:.0%}",
            f"  Avg turnover/yr   {m['turnover_per_year']:.1f}x",
            f"  Rebalances        {m['n_rebalances']}",
        ]
        if self.data_source == "synthetic":
            lines += ["", "  ⚠️  SYNTHETIC DATA — plumbing demo only, not a real edge."]
        lines.append("=" * 58)
        return "\n".join(lines)


def _rebalance_dates(index: pd.DatetimeIndex, freq: str, warmup: int) -> list[pd.Timestamp]:
    eligible = index[warmup:]
    if len(eligible) == 0:
        return []
    s = pd.Series(eligible, index=eligible)
    if freq == "week-end":
        grp = [g.index[-1] for _, g in s.groupby([eligible.isocalendar().year, eligible.isocalendar().week])]
    else:  # month-end
        grp = [g.index[-1] for _, g in s.groupby([eligible.year, eligible.month])]
    return sorted(grp)


def _turnover(prev: pd.Series, new: pd.Series) -> float:
    """One-sided turnover fraction in [0, 1]: 0.5*sum|w_new - w_old|."""
    all_t = prev.index.union(new.index)
    p = prev.reindex(all_t, fill_value=0.0)
    n = new.reindex(all_t, fill_value=0.0)
    return float(0.5 * (n - p).abs().sum())


def run_backtest(prices: pd.DataFrame, cfg: Config, data_source: str = "?") -> BacktestResult:
    engine = StrategyEngine(prices, cfg)
    risk = RiskManager(cfg)
    daily_ret = prices.pct_change().fillna(0.0)

    warmup = engine.warmup_days()
    rebals = _rebalance_dates(prices.index, cfg.strategy.get("rebalance", "month-end"), warmup)
    if not rebals:
        raise RuntimeError(
            f"Not enough history: need >{warmup} trading days of warmup, "
            f"have {len(prices.index)}. Widen backtest.start."
        )

    cost_rate = (float(cfg.costs["commission_bps"]) + float(cfg.costs["slippage_bps"])) / 1e4
    equity = float(cfg.backtest["initial_capital"])
    initial = equity

    idx = prices.index
    pos_of = {d: i for i, d in enumerate(idx)}
    equity_dates, equity_vals = [], []
    weights_log: dict[pd.Timestamp, pd.Series] = {}
    prev_target = pd.Series(dtype=float)
    total_turnover = 0.0
    invested_days = 0
    total_days = 0

    for i, r in enumerate(rebals):
        raw = engine.weights_on(r)
        ks_active = risk.update_killswitch(equity)
        target = risk.apply(raw, ks_active)
        weights_log[r] = target

        turn = _turnover(prev_target, target)
        total_turnover += turn
        equity *= (1.0 - turn * cost_rate)   # pay costs at rebalance
        prev_target = target

        start_pos = pos_of[r] + 1
        end_pos = pos_of[rebals[i + 1]] if i + 1 < len(rebals) else len(idx) - 1
        is_invested = target.sum() > 1e-9 and not (
            len(target) == 1 and target.index[0] == cfg.defensive_asset
        )
        for p in range(start_pos, end_pos + 1):
            d = idx[p]
            if len(target) > 0:
                row = daily_ret.iloc[p]
                port_r = float((target.reindex(row.index, fill_value=0.0) * row).sum())
            else:
                port_r = 0.0  # all cash
            equity *= (1.0 + port_r)
            equity_dates.append(d)
            equity_vals.append(equity)
            total_days += 1
            if is_invested:
                invested_days += 1

    equity_series = pd.Series(equity_vals, index=pd.DatetimeIndex(equity_dates))
    metrics = _metrics(equity_series, initial, weights_log, total_turnover, invested_days, total_days)
    wl = pd.DataFrame(weights_log).T.fillna(0.0).sort_index()
    return BacktestResult(equity_series, wl, metrics, data_source)


def _metrics(equity, initial, weights_log, total_turnover, invested_days, total_days) -> dict:
    rets = equity.pct_change().dropna()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / initial) ** (1 / years) - 1
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    sharpe = (rets.mean() * TRADING_DAYS) / vol if vol > 0 else 0.0
    max_dd = drawdown(equity).min()
    monthly = equity.resample("ME").last().pct_change().dropna()
    pct_pos = (monthly > 0).mean() if len(monthly) else float("nan")
    return {
        "start": equity.index[0],
        "end": equity.index[-1],
        "years": years,
        "initial": initial,
        "final_equity": float(equity.iloc[-1]),
        "total_return": float(equity.iloc[-1] / initial - 1),
        "cagr": float(cagr),
        "vol": float(vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "pct_positive_months": float(pct_pos),
        "time_in_market": invested_days / total_days if total_days else 0.0,
        "turnover_per_year": total_turnover / years,
        "n_rebalances": len(weights_log),
    }
