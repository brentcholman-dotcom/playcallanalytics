"""
Configuration Package

Contains all configuration settings, API keys, and model parameters.
"""

from .settings import (
    MODEL_WEIGHTS,
    CONVERSION_THRESHOLD,
    CONFIDENCE_THRESHOLD,
    WEATHER_THRESHOLDS,
    FATIGUE_THRESHOLDS,
    INJURY_POSITION_WEIGHTS
)

__all__ = [
    'MODEL_WEIGHTS',
    'CONVERSION_THRESHOLD',
    'CONFIDENCE_THRESHOLD',
    'WEATHER_THRESHOLDS',
    'FATIGUE_THRESHOLDS',
    'INJURY_POSITION_WEIGHTS'
]
