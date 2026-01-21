"""
Backtesting Package

This package provides validation and comparison tools for model evaluation.
"""

from .validator import (
    BacktestRunner,
    BacktestResults,
    generate_report,
    run_backtest
)

__all__ = [
    'BacktestRunner',
    'BacktestResults',
    'generate_report',
    'run_backtest'
]
