"""
Momentum Scoring Algorithm

This module calculates offensive momentum based on recent play success,
drive efficiency, scoring recency, and turnover impact.

Momentum Score: 0-100 scale
- 0-25: Cold/struggling offense
- 26-50: Average momentum
- 51-75: Good momentum
- 76-100: Hot/dominant offense
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Momentum component weights
WEIGHTS = {
    'recent_success': 40,      # Recent play success (0-40 points)
    'drive_efficiency': 25,     # Drive efficiency vs season avg (0-25 points)
    'scoring_recency': 20,      # How recently team scored (0-20 points)
    'turnover_impact': 15       # Recent turnover impact (0-15 points)
}


def calculate_recent_success_score(off_success_rate):
    """
    Calculate points based on recent play success rate.

    Args:
        off_success_rate: Success rate from last 5 plays (0.0-1.0)

    Returns:
        float: Points (0-40)
    """
    if pd.isna(off_success_rate):
        return WEIGHTS['recent_success'] / 2  # Default to 20 points if no data

    # Linear scale: 0% success = 0 points, 100% success = 40 points
    return off_success_rate * WEIGHTS['recent_success']


def calculate_drive_efficiency_score(drive_efficiency, season_avg):
    """
    Calculate points based on drive efficiency vs season average.

    Args:
        drive_efficiency: Current drive yards per play
        season_avg: Team's season average yards per play

    Returns:
        float: Points (0-25)
    """
    if pd.isna(drive_efficiency) or pd.isna(season_avg) or season_avg == 0:
        return WEIGHTS['drive_efficiency'] / 2  # Default to 12.5 points

    # Calculate ratio vs season average
    ratio = drive_efficiency / season_avg

    # Scale:
    # 50% better than average (1.5x) = 25 points
    # At average (1.0x) = 12.5 points
    # 50% worse than average (0.5x) = 0 points

    if ratio >= 1.5:
        score = WEIGHTS['drive_efficiency']
    elif ratio >= 1.0:
        # Linear interpolation between 12.5 and 25
        score = 12.5 + (ratio - 1.0) * (12.5 / 0.5)
    elif ratio >= 0.5:
        # Linear interpolation between 0 and 12.5
        score = (ratio - 0.5) * (12.5 / 0.5)
    else:
        score = 0

    return min(WEIGHTS['drive_efficiency'], max(0, score))


def calculate_scoring_recency_score(time_since_last_score, last_score_team, current_team):
    """
    Calculate points based on how recently the team scored.

    Args:
        time_since_last_score: Seconds since last score (either team)
        last_score_team: Team that scored last
        current_team: Current offensive team

    Returns:
        float: Points (0-20)
    """
    # If we don't know who scored last or when, return baseline
    if pd.isna(time_since_last_score) or pd.isna(last_score_team):
        return 5

    # If opponent scored last, lower score
    if last_score_team != current_team:
        return 5

    # Team scored last - calculate recency bonus
    if time_since_last_score <= 120:  # 2 minutes
        return 20
    elif time_since_last_score <= 300:  # 5 minutes
        return 15
    elif time_since_last_score <= 600:  # 10 minutes
        return 10
    else:
        return 5


def calculate_turnover_impact_score(turnovers_offense, turnovers_defense):
    """
    Calculate points based on recent turnover impact.

    Args:
        turnovers_offense: Turnovers by current offense in last 10 plays
        turnovers_defense: Turnovers forced by current defense in last 10 plays

    Returns:
        float: Points (0-15)
    """
    # Handle missing data
    if pd.isna(turnovers_offense):
        turnovers_offense = 0
    if pd.isna(turnovers_defense):
        turnovers_defense = 0

    # Own turnover in last 10 plays = 0 points (momentum killer)
    if turnovers_offense > 0:
        return 0

    # Opponent turnover in last 10 plays = 15 points (momentum boost)
    if turnovers_defense > 0:
        return WEIGHTS['turnover_impact']

    # No recent turnovers = neutral (7.5 points)
    return WEIGHTS['turnover_impact'] / 2


def calculate_momentum(row, season_avg_ypp):
    """
    Calculate offensive momentum score for a single play.

    Args:
        row: DataFrame row with game context columns
        season_avg_ypp: Dict mapping team -> season average yards per play

    Returns:
        float: Momentum score (0-100)
    """
    # Get current team
    team = row.get('posteam', None)
    if pd.isna(team):
        return 50.0  # Neutral if no team info

    # Get season average for this team
    team_season_avg = season_avg_ypp.get(team, 5.5)  # Default to league average ~5.5

    # Calculate each component
    recent_success = calculate_recent_success_score(
        row.get('off_success_rate', np.nan)
    )

    drive_efficiency = calculate_drive_efficiency_score(
        row.get('drive_efficiency', np.nan),
        team_season_avg
    )

    scoring_recency = calculate_scoring_recency_score(
        row.get('time_since_last_score', np.nan),
        row.get('last_score_team', None),
        team
    )

    turnover_impact = calculate_turnover_impact_score(
        row.get('turnovers_last_10_plays_offense', 0),
        row.get('turnovers_last_10_plays_defense', 0)
    )

    # Sum all components
    total_score = (
        recent_success +
        drive_efficiency +
        scoring_recency +
        turnover_impact
    )

    return total_score


def calculate_season_averages(plays_df):
    """
    Calculate season average yards per play for each team.

    Args:
        plays_df: DataFrame with play-by-play data including posteam and yards_gained

    Returns:
        dict: Mapping of team -> average yards per play
    """
    logger.info("Calculating season average yards per play for each team...")

    if 'posteam' not in plays_df.columns or 'yards_gained' not in plays_df.columns:
        logger.warning("Missing required columns for season averages")
        return {}

    # Filter out plays with missing data
    valid_plays = plays_df[
        plays_df['posteam'].notna() &
        plays_df['yards_gained'].notna()
    ].copy()

    # Calculate average yards per play for each team
    team_averages = valid_plays.groupby('posteam')['yards_gained'].mean().to_dict()

    logger.info(f"Calculated averages for {len(team_averages)} teams")

    # Log some examples
    for team in sorted(list(team_averages.keys()))[:5]:
        logger.info(f"  {team}: {team_averages[team]:.2f} yards/play")

    return team_averages


def add_momentum_scores(plays_df):
    """
    Add momentum score column to plays dataframe.

    Args:
        plays_df: DataFrame with game context columns

    Returns:
        DataFrame: Original dataframe with momentum_score column added
    """
    logger.info("Adding momentum scores to plays...")

    result = plays_df.copy()

    # Calculate season averages
    season_avg_ypp = calculate_season_averages(plays_df)

    # Calculate momentum for each play
    result['momentum_score'] = result.apply(
        lambda row: calculate_momentum(row, season_avg_ypp),
        axis=1
    )

    logger.info("Momentum scores added")
    logger.info(f"  Mean: {result['momentum_score'].mean():.1f}")
    logger.info(f"  Median: {result['momentum_score'].median():.1f}")
    logger.info(f"  Std: {result['momentum_score'].std():.1f}")
    logger.info(f"  Min: {result['momentum_score'].min():.1f}")
    logger.info(f"  Max: {result['momentum_score'].max():.1f}")

    return result


def get_momentum_category(score):
    """
    Categorize momentum score.

    Args:
        score: Momentum score (0-100)

    Returns:
        str: Category label
    """
    if pd.isna(score):
        return 'unknown'
    elif score >= 76:
        return 'hot'
    elif score >= 51:
        return 'good'
    elif score >= 26:
        return 'average'
    else:
        return 'cold'


def analyze_momentum_distribution(plays_df):
    """
    Analyze distribution of momentum scores.

    Args:
        plays_df: DataFrame with momentum_score column

    Returns:
        DataFrame: Summary statistics by momentum category
    """
    if 'momentum_score' not in plays_df.columns:
        logger.error("No momentum_score column found")
        return pd.DataFrame()

    # Add category
    plays_with_category = plays_df.copy()
    plays_with_category['momentum_category'] = plays_with_category['momentum_score'].apply(
        get_momentum_category
    )

    # Analyze by category
    summary = plays_with_category.groupby('momentum_category').agg({
        'momentum_score': ['count', 'mean', 'min', 'max'],
        'yards_gained': 'mean' if 'yards_gained' in plays_with_category.columns else 'count',
        'first_down': 'mean' if 'first_down' in plays_with_category.columns else 'count'
    }).round(2)

    return summary


def calculate_momentum_score(recent_plays=None, score_differential=None):
    """
    Legacy function for backward compatibility.

    Note: This is deprecated. Use calculate_momentum() with game context instead.

    Args:
        recent_plays: List of recent play outcomes (deprecated)
        score_differential: Current point differential (deprecated)

    Returns:
        float: Momentum score (50.0 neutral)
    """
    logger.warning("calculate_momentum_score() is deprecated. Use calculate_momentum() instead.")
    return 50.0


if __name__ == "__main__":
    """
    Test momentum calculations.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from ingestion.play_by_play import load_pbp_data
    from models.game_context import add_game_context

    logger.info("="*60)
    logger.info("MOMENTUM CALCULATION TEST")
    logger.info("="*60)

    # Load sample data
    logger.info("Loading 2023 season...")
    pbp = load_pbp_data(seasons=[2023])

    # Get first game
    first_game = pbp['game_id'].iloc[0]
    game = pbp[pbp['game_id'] == first_game].copy()

    logger.info(f"Processing game: {first_game}")

    # Add game context
    game_with_context = add_game_context(game)

    # Add momentum scores
    game_with_momentum = add_momentum_scores(game_with_context)

    # Show examples
    logger.info("\nExample plays with momentum:")
    display_cols = [
        'posteam', 'down', 'ydstogo',
        'off_success_rate', 'drive_efficiency',
        'time_since_last_score', 'momentum_score'
    ]
    available_cols = [col for col in display_cols if col in game_with_momentum.columns]
    print(game_with_momentum[available_cols].head(20))

    # Analyze distribution
    logger.info("\n" + "="*60)
    logger.info("MOMENTUM DISTRIBUTION")
    logger.info("="*60)
    summary = analyze_momentum_distribution(game_with_momentum)
    print(summary)
