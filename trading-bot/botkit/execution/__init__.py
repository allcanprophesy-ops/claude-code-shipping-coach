"""Execution adapters — the swappable boundary between strategy and a broker.

The strategy/backtest layers never talk to a broker directly. They produce
*target weights*; an adapter turns those into orders. Swap adapters without
touching strategy code:

    PaperBroker        — in-memory simulation, zero risk, for dry runs.
    RobinhoodMCPBroker — maps to the Robinhood MCP tools available in this
                         session (review-then-place). Ships GUARDED OFF.

Add an AlpacaBroker the same way (recommended for real equities automation —
Robinhood has no official equities API; see the report).
"""
from .base import BrokerAdapter, OrderIntent, Position
from .paper import PaperBroker

__all__ = ["BrokerAdapter", "OrderIntent", "Position", "PaperBroker"]
