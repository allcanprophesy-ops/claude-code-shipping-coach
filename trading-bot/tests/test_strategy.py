"""Sanity tests so refinements don't silently break the core logic.

Run:  python -m pytest trading-bot/tests -q     (or)   python trading-bot/tests/test_strategy.py

These assert invariants, not specific returns: weights are valid, look-ahead is
absent, the kill-switch trips/resets, and order planning conserves dollars.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from botkit.config import load_config
from botkit.backtest import run_backtest, _turnover
from botkit.data import _synthetic_prices
from botkit.execution.base import OrderIntent, Position, plan_orders
from botkit.execution.paper import PaperBroker
from botkit.risk import RiskManager
from botkit.strategy import StrategyEngine


def _cfg():
    return load_config()


def _prices():
    cfg = _cfg()
    return _synthetic_prices(cfg.all_tickers, "2015-01-01", "2024-01-01")


def test_weights_are_valid():
    cfg = _cfg()
    eng = StrategyEngine(_prices(), cfg)
    w = eng.weights_on(eng.prices.index[-1])
    assert (w >= -1e-9).all(), "no negative weights (long-only strategy)"
    assert w.sum() <= 1.0 + 1e-6, f"weights must not exceed 100%, got {w.sum()}"
    for sym, val in w.items():
        if sym != cfg.defensive_asset:
            assert val <= cfg.risk["max_weight_per_position"] + 1e-9


def test_no_lookahead():
    """weights_on(t) must be unchanged if FUTURE prices are deleted."""
    cfg = _cfg()
    prices = _prices()
    cut = prices.index[len(prices) // 2]
    full = StrategyEngine(prices, cfg).weights_on(cut)
    truncated = StrategyEngine(prices.loc[:cut], cfg).weights_on(cut)
    assert set(full.index) == set(truncated.index), "signal leaked future data!"
    for sym in full.index:
        assert abs(full[sym] - truncated[sym]) < 1e-9


def test_killswitch_trips_and_resets():
    cfg = _cfg()
    cfg.risk["max_drawdown_killswitch"] = 0.20
    rm = RiskManager(cfg)
    assert rm.update_killswitch(100) is False
    assert rm.update_killswitch(85) is False     # -15%, under threshold
    assert rm.update_killswitch(75) is True       # -25%, trips
    assert rm.update_killswitch(90) is True        # recovering but not new high
    assert rm.update_killswitch(105) is False      # new high -> resets


def test_turnover_bounds():
    a = pd.Series({"XLK": 0.5, "XLF": 0.5})
    b = pd.Series({"XLV": 0.5, "XLF": 0.5})
    t = _turnover(a, b)
    assert 0.0 <= t <= 1.0
    assert abs(t - 0.5) < 1e-9  # swapped one of two sleeves -> 50% one-sided turnover


def test_plan_orders_conserves_dollars():
    target = pd.Series({"XLK": 0.5, "XLF": 0.5})
    orders = plan_orders(target, [], account_value=10_000)
    assert sum(o.notional for o in orders) == 10_000
    assert all(o.side == "buy" for o in orders)


def test_paper_broker_roundtrip():
    b = PaperBroker(starting_cash=10_000, marks={"XLK": 100.0})
    b.submit(OrderIntent("XLK", "buy", 5_000))
    assert abs(b.account_value() - 10_000) < 1e-6  # value conserved at same mark
    assert b.positions()[0].symbol == "XLK"


def test_backtest_runs_end_to_end():
    cfg = _cfg()
    res = run_backtest(_prices(), cfg, data_source="synthetic")
    assert len(res.equity) > 0
    assert res.metrics["n_rebalances"] > 0
    assert np.isfinite(res.metrics["cagr"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
