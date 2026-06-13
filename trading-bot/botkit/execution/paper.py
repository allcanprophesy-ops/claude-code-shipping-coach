"""In-memory paper broker. Fills instantly at the provided mark prices.

Use this for dry runs of the live loop with ZERO risk. It tracks cash and
positions so you can watch the rebalance logic behave before wiring a real
broker. State is in-memory only (resets each run) unless you persist it yourself.
"""
from __future__ import annotations

from .base import BrokerAdapter, OrderIntent, Position


class PaperBroker(BrokerAdapter):
    def __init__(self, starting_cash: float = 10_000.0, marks: dict[str, float] | None = None):
        self.cash = float(starting_cash)
        self._qty: dict[str, float] = {}
        self.marks = dict(marks or {})

    def set_marks(self, marks: dict[str, float]):
        self.marks.update(marks)

    def _price(self, symbol: str) -> float:
        if symbol not in self.marks:
            raise KeyError(f"PaperBroker has no mark price for {symbol}; call set_marks().")
        return self.marks[symbol]

    def account_value(self) -> float:
        holdings = sum(q * self._price(s) for s, q in self._qty.items())
        return self.cash + holdings

    def positions(self) -> list[Position]:
        out = []
        for s, q in self._qty.items():
            if abs(q) > 1e-9:
                out.append(Position(s, q, q * self._price(s)))
        return out

    def submit(self, order: OrderIntent) -> dict:
        px = self._price(order.symbol)
        qty = order.notional / px
        if order.side == "buy":
            self.cash -= order.notional
            self._qty[order.symbol] = self._qty.get(order.symbol, 0.0) + qty
        else:
            self.cash += order.notional
            self._qty[order.symbol] = self._qty.get(order.symbol, 0.0) - qty
        return {"status": "filled", "symbol": order.symbol, "side": order.side,
                "qty": round(qty, 6), "price": px}

    def name(self) -> str:
        return "paper"
