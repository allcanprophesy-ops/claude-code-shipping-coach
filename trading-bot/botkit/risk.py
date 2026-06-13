"""Risk overlay — applied AFTER the strategy proposes weights, BEFORE execution.

Two jobs:
  1. Enforce hard exposure limits (belt-and-suspenders over the strategy).
  2. Drawdown kill-switch: if the portfolio's drawdown from its peak breaches a
     threshold, flatten to defensive/cash until a new equity high is reclaimed.
     This is the circuit breaker that the research repeatedly stresses: survival
     first. It caps the damage from a broken strategy or a regime the model
     never saw.

Keeping risk OUT of the strategy means you can tighten/loosen safety without
touching alpha logic — and reuse the exact same overlay in live trading.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import Config


@dataclass
class KillSwitchState:
    tripped: bool = False
    peak_equity: float = 0.0


class RiskManager:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.max_dd = cfg.risk.get("max_drawdown_killswitch")
        self.defensive = cfg.defensive_asset
        self.state = KillSwitchState()

    def update_killswitch(self, equity: float) -> bool:
        """Feed the latest equity; returns True if the kill-switch is ACTIVE.

        Trips when drawdown from peak exceeds the threshold. Resets only when a
        NEW equity high is made (drawdown back to 0) — avoids whipsawing in/out
        right at the threshold.
        """
        if self.max_dd is None:
            return False
        st = self.state
        st.peak_equity = max(st.peak_equity, equity)
        if st.peak_equity <= 0:
            return st.tripped
        dd = equity / st.peak_equity - 1.0
        if not st.tripped and dd <= -abs(self.max_dd):
            st.tripped = True
        elif st.tripped and equity >= st.peak_equity:  # reclaimed the high
            st.tripped = False
        return st.tripped

    def apply(self, weights: pd.Series, killswitch_active: bool) -> pd.Series:
        """Return the risk-adjusted weights actually sent to the broker."""
        if killswitch_active:
            if self.defensive.upper() == "CASH":
                return pd.Series(dtype=float)
            return pd.Series({self.defensive: 1.0})

        w = weights.copy()
        cap = float(self.cfg.risk["max_weight_per_position"])
        # Don't cap the defensive sleeve — it's the parking lot, not a bet.
        for t in list(w.index):
            if t != self.defensive and w[t] > cap:
                w[t] = cap
        total = w.sum()
        max_expo = float(self.cfg.risk["target_total_exposure"])
        if total > max_expo > 0:
            w = w * (max_expo / total)
        return w[w > 1e-9]
