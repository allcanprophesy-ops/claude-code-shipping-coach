"""Broker adapter interface + the rebalance-to-orders planner.

`plan_orders` is the shared, broker-agnostic logic that converts (target weights,
current positions, account value) into a list of OrderIntents. Every adapter
reuses it, so order math is defined once and tested once.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

import pandas as pd


@dataclass
class Position:
    symbol: str
    quantity: float
    market_value: float


@dataclass
class OrderIntent:
    symbol: str
    side: str          # "buy" | "sell"
    notional: float    # dollar amount to trade (we size by $, broker converts)
    reason: str = ""

    def __str__(self) -> str:
        return f"{self.side.upper():4s} ${self.notional:>10,.2f}  {self.symbol:6s}  {self.reason}"


class BrokerAdapter(abc.ABC):
    """Implement these four methods to support a new broker."""

    @abc.abstractmethod
    def account_value(self) -> float: ...

    @abc.abstractmethod
    def positions(self) -> list[Position]: ...

    @abc.abstractmethod
    def submit(self, order: OrderIntent) -> dict:
        """Place one order. Should be idempotent-friendly (use a client id)."""

    @abc.abstractmethod
    def name(self) -> str: ...


def plan_orders(
    target_weights: pd.Series,
    positions: list[Position],
    account_value: float,
    min_order_notional: float = 1.0,
) -> list[OrderIntent]:
    """Diff current vs target holdings -> minimal set of buy/sell intents.

    Sells are emitted before buys (free up cash first). Tiny deltas below
    `min_order_notional` are skipped to avoid churn/fees on noise.
    """
    cur_val = {p.symbol: p.market_value for p in positions}
    symbols = set(cur_val) | set(target_weights.index)

    sells, buys = [], []
    for sym in sorted(symbols):
        target_val = float(target_weights.get(sym, 0.0)) * account_value
        delta = target_val - cur_val.get(sym, 0.0)
        if abs(delta) < min_order_notional:
            continue
        intent = OrderIntent(
            symbol=sym,
            side="buy" if delta > 0 else "sell",
            notional=round(abs(delta), 2),
            reason=f"-> {target_weights.get(sym, 0.0):.0%} target",
        )
        (buys if delta > 0 else sells).append(intent)
    return sells + buys
