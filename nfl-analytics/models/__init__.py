"""
NFL Analytics Models Package

This package contains all the contextual models for 4th down decision analysis.
"""

from .momentum import (
    calculate_momentum_score,
    calculate_momentum,
    add_momentum_scores,
    get_momentum_category,
    analyze_momentum_distribution,
    calculate_season_averages
)
from .injuries import calculate_injury_impact
from .weather import calculate_weather_impact
from .crowd_noise import calculate_noise_impact
from .fatigue import calculate_fatigue_level
from .conversion import calculate_conversion_probability, recommend_decision
from .game_context import (
    add_game_context,
    process_all_games_with_context,
    get_context_summary,
    calculate_recent_offensive_history,
    calculate_recent_defensive_history,
    calculate_drive_context,
    calculate_scoring_context,
    calculate_turnover_context
)

__all__ = [
    'calculate_momentum_score',
    'calculate_momentum',
    'add_momentum_scores',
    'get_momentum_category',
    'analyze_momentum_distribution',
    'calculate_season_averages',
    'calculate_injury_impact',
    'calculate_weather_impact',
    'calculate_noise_impact',
    'calculate_fatigue_level',
    'calculate_conversion_probability',
    'recommend_decision',
    'add_game_context',
    'process_all_games_with_context',
    'get_context_summary',
    'calculate_recent_offensive_history',
    'calculate_recent_defensive_history',
    'calculate_drive_context',
    'calculate_scoring_context',
    'calculate_turnover_context'
]
