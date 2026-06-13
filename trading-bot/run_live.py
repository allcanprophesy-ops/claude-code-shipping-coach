#!/usr/bin/env python3
"""Generate today's target allocation and an order plan (NO live trading by default).

    python run_live.py                 # print today's target weights
    python run_live.py --broker paper  # dry-run the rebalance against a paper book
    python run_live.py --broker robinhood-mcp   # emit order_plan.json for the agent

This uses the SAME StrategyEngine + RiskManager as the backtest, so what you see
here is exactly what was tested. It NEVER places a live order on its own — the
Robinhood adapter writes a reviewable plan for the agent to execute via MCP.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from botkit.backtest import TRADING_DAYS  # noqa: F401  (kept for parity/refinement)
from botkit.config import load_config
from botkit.data import load_prices
from botkit.execution import PaperBroker
from botkit.execution.base import plan_orders
from botkit.risk import RiskManager
from botkit.strategy import StrategyEngine


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute today's target allocation + order plan.")
    ap.add_argument("--config", default=None)
    ap.add_argument("--broker", choices=["none", "paper", "robinhood-mcp"], default="none")
    args = ap.parse_args()

    cfg = load_config(args.config)
    prices, source = load_prices(
        cfg.all_tickers, cfg.backtest["start"], cfg.backtest["end"],
        cfg.data["source"], cfg.data["cache_dir"],
    )
    if prices.empty:
        print("No price data.", file=sys.stderr)
        return 1

    engine = StrategyEngine(prices, cfg)
    risk = RiskManager(cfg)
    asof = prices.index[-1]
    target = engine.weights_on(asof)
    # Note: live kill-switch state should be loaded from your equity history; here
    # we run it un-tripped for a fresh process. Persist RiskManager.state to retain it.
    target = risk.apply(target, killswitch_active=False)

    print(f"\nAs of {asof:%Y-%m-%d}  (data: {source})")
    print("Target allocation:")
    if target.empty:
        print("  100% CASH (no qualifying sleeves / defensive)")
    else:
        for sym, w in target.sort_values(ascending=False).items():
            print(f"  {sym:6s} {w:6.1%}")
    if source == "synthetic":
        print("\n  ⚠️  SYNTHETIC DATA — do not trade on this.")

    if args.broker == "none":
        return 0

    marks = prices.loc[asof].to_dict()
    if args.broker == "paper":
        broker = PaperBroker(starting_cash=float(cfg.backtest["initial_capital"]), marks=marks)
    else:
        from botkit.execution.robinhood_mcp import RobinhoodMCPBroker
        broker = RobinhoodMCPBroker(plan_out="order_plan.json", live=False)

    if args.broker == "paper":
        orders = plan_orders(target, broker.positions(), broker.account_value())
        print(f"\nOrder plan ({broker.name()}):")
        for o in orders:
            print("  " + str(o))
            broker.submit(o)
        print(f"\nPost-trade account value: ${broker.account_value():,.2f}")
    else:
        # Robinhood-MCP path: account value/positions come from MCP reads done by
        # the agent. For a standalone dry-run we assume a flat book at config capital.
        acct = float(cfg.backtest["initial_capital"])
        orders = plan_orders(target, [], acct)
        print(f"\nOrder plan ({broker.name()}) — written to order_plan.json:")
        for o in orders:
            print("  " + str(o))
            broker.submit(o)
        print("\nHand order_plan.json to the agent to review_* then place_* via MCP.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
