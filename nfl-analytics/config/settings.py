"""
Configuration Settings

This module contains API keys, model weights, thresholds,
and other configuration parameters for the analytics system.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY', '')
NFL_DATA_API_KEY = os.getenv('NFL_DATA_API_KEY', '')

# Data Paths
RAW_DATA_PATH = 'data/raw/'
PROCESSED_DATA_PATH = 'data/processed/'

# Model Weights
# Weights for combining different factors in conversion probability
MODEL_WEIGHTS = {
    'momentum': 0.20,
    'injuries': 0.15,
    'weather': 0.10,
    'crowd_noise': 0.08,
    'fatigue': 0.12,
    'base_model': 0.35  # Static model baseline
}

# Thresholds
CONVERSION_THRESHOLD = 0.50  # Minimum probability to recommend "go for it"
CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence for strong recommendation

# Weather Impact Thresholds
WEATHER_THRESHOLDS = {
    'high_wind_mph': 15,
    'low_temp_fahrenheit': 32,
    'heavy_precipitation': 0.5
}

# Fatigue Thresholds
FATIGUE_THRESHOLDS = {
    'high_snap_count': 70,
    'low_rest_seconds': 60
}

# Injury Impact Weights
INJURY_POSITION_WEIGHTS = {
    'QB': 0.30,
    'LT': 0.15,
    'RT': 0.12,
    'C': 0.10,
    'WR1': 0.12,
    'RB1': 0.10,
    'other': 0.05
}

# Backtesting Configuration
BACKTEST_SEASONS = [2020, 2021, 2022, 2023]
VALIDATION_SPLIT = 0.2

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = 'nfl_analytics.log'
