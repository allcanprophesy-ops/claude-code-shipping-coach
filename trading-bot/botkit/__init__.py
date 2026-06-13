"""botkit — a small, refinable toolkit for a momentum/trend rotation trading bot.

Layers (each independently swappable):
    config       — load + validate config.yaml
    data         — price history (yfinance, with a synthetic offline fallback)
    indicators   — momentum, SMA, ATR, drawdown
    strategy     — dual-momentum + regime filter -> target weights
    risk         — position sizing, exposure caps, drawdown kill-switch
    backtest     — point-in-time rebalance simulation + performance metrics
    execution    — pluggable broker adapters (paper, Robinhood MCP stub)

The design goal is *refinement*: every tunable lives in config.yaml, and each
layer is a plain function/class you can read in one sitting and edit safely.
"""

__version__ = "0.1.0"
