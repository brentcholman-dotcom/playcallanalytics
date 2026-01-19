"""
Data Ingestion Package

This package handles data loading from various sources including
nflfastR, weather APIs, and injury reports.
"""

from .play_by_play import (
    load_pbp_data,
    filter_fourth_down_plays,
    enrich_play_context,
    save_processed_data,
    load_and_process_fourth_downs
)
from .weather_api import fetch_game_weather
from .injury_feed import parse_injury_report

__all__ = [
    'load_pbp_data',
    'filter_fourth_down_plays',
    'enrich_play_context',
    'save_processed_data',
    'load_and_process_fourth_downs',
    'fetch_game_weather',
    'parse_injury_report'
]
