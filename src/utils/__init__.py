"""
Utility modules.

This package contains utility functions for bet logging and backtesting.
"""

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'BetLogger':
        from .bet_logger import BetLogger
        return BetLogger
    elif name == 'HistoricalBacktester':
        from .backtest import HistoricalBacktester
        return HistoricalBacktester
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ['BetLogger', 'HistoricalBacktester']
