#!/usr/bin/env python3
"""Backtest the configured strategy.

    python run_backtest.py                 # uses config.yaml
    python run_backtest.py --config my.yaml
    python run_backtest.py --plot          # also writes equity_curve.png (needs matplotlib)
    python run_backtest.py --save results.csv

This is your main refinement loop: edit config.yaml -> re-run -> compare metrics.
"""
from __future__ import annotations

import argparse
import sys

from botkit.backtest import run_backtest
from botkit.config import load_config
from botkit.data import load_prices


def main() -> int:
    ap = argparse.ArgumentParser(description="Backtest the momentum-rotation strategy.")
    ap.add_argument("--config", default=None, help="path to config.yaml")
    ap.add_argument("--plot", action="store_true", help="write equity_curve.png")
    ap.add_argument("--save", metavar="CSV", help="write daily equity curve to CSV")
    ap.add_argument("--weights", action="store_true", help="print the latest target weights")
    args = ap.parse_args()

    cfg = load_config(args.config)
    prices, source = load_prices(
        cfg.all_tickers,
        start=cfg.backtest["start"],
        end=cfg.backtest["end"],
        source=cfg.data["source"],
        cache_dir=cfg.data["cache_dir"],
    )
    if prices.empty:
        print("No price data available.", file=sys.stderr)
        return 1

    result = run_backtest(prices, cfg, data_source=source)
    print(result.summary())

    if args.weights:
        last = result.weights_log.iloc[-1]
        last = last[last > 0]
        print("\nLatest target weights:")
        for sym, w in last.sort_values(ascending=False).items():
            print(f"  {sym:6s} {w:6.1%}")

    if args.save:
        result.equity.to_csv(args.save, header=["equity"])
        print(f"\nSaved equity curve -> {args.save}")

    if args.plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            ax = result.equity.plot(figsize=(11, 5), title="Strategy equity curve")
            ax.set_ylabel("Equity ($)")
            ax.figure.tight_layout()
            ax.figure.savefig("equity_curve.png", dpi=120)
            print("Saved plot -> equity_curve.png")
        except ImportError:
            print("matplotlib not installed; skipping --plot (pip install matplotlib)",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
