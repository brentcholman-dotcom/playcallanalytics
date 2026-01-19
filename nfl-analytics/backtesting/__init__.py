"""
Backtesting Package

This package provides validation and comparison tools for model evaluation.
"""

from .validator import backtest_predictions, compare_to_baseline

__all__ = [
    'backtest_predictions',
    'compare_to_baseline'
]
