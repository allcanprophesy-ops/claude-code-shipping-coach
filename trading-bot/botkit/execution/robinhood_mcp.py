"""Robinhood execution via this session's Robinhood MCP tools.

IMPORTANT CONTEXT (from the research report):
  * Robinhood has NO official equities API. The MCP tools in this session are the
    sanctioned bridge available to us here. For durable, self-hosted automation,
    prefer Alpaca (official API + free paper trading). This adapter exists so you
    can act on signals inside the agent session.
  * Standalone Python CANNOT call mcp__* tools directly — those are invoked by
    the agent (Claude) in-session. So this adapter is DESIGNED to emit a precise,
    reviewable ORDER PLAN that the agent then executes with the MCP tools, using
    the review-then-place pattern:
          mcp__<server>__review_equity_order   (validate)
          mcp__<server>__place_equity_order    (submit)

SAFETY: ships in dry-run. `submit()` never places a live order from Python; it
records the intent. Real placement is a deliberate, human-in-the-loop MCP call.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import BrokerAdapter, OrderIntent, Position


class RobinhoodMCPBroker(BrokerAdapter):
    def __init__(self, plan_out: str = "order_plan.json", live: bool = False):
        self.plan_out = Path(plan_out)
        self.live = live              # leave False; live placement is via MCP, not here
        self._intents: list[dict] = []

    # These two are populated by the agent from MCP reads (get_accounts /
    # get_equity_positions) before planning. Defaults keep dry runs functional.
    def account_value(self) -> float:
        raise NotImplementedError(
            "Fetch via MCP: mcp__<server>__get_accounts / get_portfolio, then pass "
            "account_value into plan_orders() directly."
        )

    def positions(self) -> list[Position]:
        raise NotImplementedError(
            "Fetch via MCP: mcp__<server>__get_equity_positions, map into "
            "Position(symbol, quantity, market_value)."
        )

    def submit(self, order: OrderIntent) -> dict:
        """Record the intent and the exact MCP call the agent should make.

        We intentionally DO NOT place orders from Python. Returning the planned
        MCP invocation keeps a human/agent in the loop for every live trade.
        """
        mcp_call = {
            "tool": "mcp__<robinhood-server>__place_equity_order",
            "precheck": "mcp__<robinhood-server>__review_equity_order",
            "args": {
                "symbol": order.symbol,
                "side": order.side,
                "type": "market",          # refine: limit w/ marketable price for control
                "amount_in_dollars": order.notional,
                "time_in_force": "gfd",
            },
            "reason": order.reason,
        }
        self._intents.append(mcp_call)
        self._flush()
        if self.live:
            raise RuntimeError(
                "Live placement must go through the agent's MCP tools, not Python. "
                "Hand this order_plan.json to the agent to review_* then place_*."
            )
        return {"status": "planned", **mcp_call}

    def _flush(self):
        self.plan_out.write_text(json.dumps(self._intents, indent=2))

    def name(self) -> str:
        return "robinhood-mcp (dry-run)"
