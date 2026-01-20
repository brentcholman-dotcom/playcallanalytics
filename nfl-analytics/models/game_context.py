"""
Game Context Calculator

This module builds rolling context for each play in a game, tracking:
- Recent play history (offense and defense)
- Drive context
- Scoring and momentum
- Turnover tracking
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.play_by_play import load_pbp_data, save_processed_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_recent_offensive_history(game_plays, window=5):
    """
    Calculate rolling offensive performance over recent plays.

    Args:
        game_plays: DataFrame of plays for a single game, chronologically ordered
        window: Number of recent plays to consider (default: 5)

    Returns:
        DataFrame: Original data with offensive history columns added
    """
    result = game_plays.copy()

    # Initialize columns
    result['off_success_rate'] = np.nan
    result['off_yards_per_play'] = np.nan
    result['off_explosive_plays'] = 0

    # Process each team's offensive plays
    for team in game_plays['posteam'].dropna().unique():
        team_plays = game_plays['posteam'] == team
        team_indices = game_plays[team_plays].index

        for i, idx in enumerate(team_indices):
            # Get last N plays by this offense (not including current play)
            start_idx = max(0, i - window)
            recent_indices = team_indices[start_idx:i]

            if len(recent_indices) > 0:
                recent_plays = game_plays.loc[recent_indices]

                # Success rate: 40%+ of needed yards
                if 'yards_gained' in recent_plays.columns and 'ydstogo' in recent_plays.columns:
                    successes = (recent_plays['yards_gained'] >= 0.4 * recent_plays['ydstogo']).sum()
                    result.at[idx, 'off_success_rate'] = successes / len(recent_indices)

                # Yards per play
                if 'yards_gained' in recent_plays.columns:
                    result.at[idx, 'off_yards_per_play'] = recent_plays['yards_gained'].mean()

                # Explosive plays (15+ yards)
                if 'yards_gained' in recent_plays.columns:
                    result.at[idx, 'off_explosive_plays'] = (recent_plays['yards_gained'] >= 15).sum()

    return result


def calculate_recent_defensive_history(game_plays, window=5):
    """
    Calculate rolling defensive performance (from offense's perspective).

    Args:
        game_plays: DataFrame of plays for a single game, chronologically ordered
        window: Number of recent plays to consider (default: 5)

    Returns:
        DataFrame: Original data with defensive history columns added
    """
    result = game_plays.copy()

    # Initialize columns
    result['def_success_rate'] = np.nan
    result['def_yards_per_play'] = np.nan

    # Process each team's defensive plays (plays where they are defteam)
    for team in game_plays['defteam'].dropna().unique():
        team_plays = game_plays['defteam'] == team
        team_indices = game_plays[team_plays].index

        for i, idx in enumerate(team_indices):
            # Get last N plays by this defense (not including current play)
            start_idx = max(0, i - window)
            recent_indices = team_indices[start_idx:i]

            if len(recent_indices) > 0:
                recent_plays = game_plays.loc[recent_indices]

                # Success rate allowed by defense
                if 'yards_gained' in recent_plays.columns and 'ydstogo' in recent_plays.columns:
                    successes = (recent_plays['yards_gained'] >= 0.4 * recent_plays['ydstogo']).sum()
                    result.at[idx, 'def_success_rate'] = successes / len(recent_indices)

                # Yards per play allowed
                if 'yards_gained' in recent_plays.columns:
                    result.at[idx, 'def_yards_per_play'] = recent_plays['yards_gained'].mean()

    return result


def calculate_drive_context(game_plays):
    """
    Calculate drive-level context for each play.

    Args:
        game_plays: DataFrame of plays for a single game, chronologically ordered

    Returns:
        DataFrame: Original data with drive context columns added
    """
    result = game_plays.copy()

    # Initialize columns
    result['plays_this_drive'] = 0
    result['yards_this_drive'] = 0.0
    result['drive_efficiency'] = np.nan

    # If we have drive_id or fixed_drive, use that
    if 'fixed_drive' in game_plays.columns:
        drive_col = 'fixed_drive'
    elif 'drive' in game_plays.columns:
        drive_col = 'drive'
    else:
        # Create synthetic drive identifier
        logger.warning("No drive column found, creating synthetic drives")
        result['synthetic_drive'] = (
            (result['posteam'] != result['posteam'].shift()) |
            (result['touchdown'] == 1) |
            (result['turnover'] == 1)
        ).cumsum()
        drive_col = 'synthetic_drive'

    # Group by team and drive
    for (team, drive_id), drive_plays in result.groupby(['posteam', drive_col]):
        if pd.isna(team):
            continue

        drive_indices = drive_plays.index

        for i, idx in enumerate(drive_indices):
            # Count plays so far in this drive (including current)
            result.at[idx, 'plays_this_drive'] = i + 1

            # Calculate yards gained so far (not including current play)
            if i > 0:
                prev_plays = drive_plays.iloc[:i]
                if 'yards_gained' in prev_plays.columns:
                    yards = prev_plays['yards_gained'].sum()
                    result.at[idx, 'yards_this_drive'] = yards
                    result.at[idx, 'drive_efficiency'] = yards / i

    return result


def calculate_scoring_context(game_plays):
    """
    Calculate scoring and momentum context.

    Args:
        game_plays: DataFrame of plays for a single game, chronologically ordered

    Returns:
        DataFrame: Original data with scoring context columns added
    """
    result = game_plays.copy()

    # Initialize columns
    result['time_since_last_score'] = np.nan
    result['last_score_team'] = None
    result['momentum_shift'] = False

    # Track when scores happened
    if 'touchdown' not in result.columns:
        result['touchdown'] = 0

    # Find scoring plays (TD or field goal)
    if 'play_type' in result.columns:
        scoring_plays = (
            (result['touchdown'] == 1) |
            (result['play_type'] == 'field_goal')
        )
    else:
        scoring_plays = result['touchdown'] == 1

    last_score_time = None
    last_score_team = None

    # Track lead changes for momentum shifts
    leader_history = []

    for idx, row in result.iterrows():
        # Update time since last score
        if last_score_time is not None and 'game_seconds_remaining' in result.columns:
            time_diff = last_score_time - row['game_seconds_remaining']
            result.at[idx, 'time_since_last_score'] = time_diff

        # Record last scoring team
        if last_score_team is not None:
            result.at[idx, 'last_score_team'] = last_score_team

        # Check for momentum shift (lead change in last 5 minutes)
        if 'score_differential' in result.columns and 'game_seconds_remaining' in result.columns:
            current_time = row['game_seconds_remaining']

            # Track leader
            if row['score_differential'] > 0:
                current_leader = row['posteam']
            elif row['score_differential'] < 0:
                current_leader = row['defteam']
            else:
                current_leader = 'tied'

            # Check if lead changed in last 5 minutes (300 seconds)
            recent_leaders = [
                (time, leader) for time, leader in leader_history
                if current_time - time <= 300
            ]

            if len(recent_leaders) > 0:
                # Check if leader changed
                prev_leaders = set([leader for _, leader in recent_leaders])
                if len(prev_leaders) > 1 or (current_leader not in prev_leaders and current_leader != 'tied'):
                    result.at[idx, 'momentum_shift'] = True

            leader_history.append((current_time, current_leader))

        # Update if this is a scoring play
        if scoring_plays.loc[idx]:
            if 'game_seconds_remaining' in result.columns:
                last_score_time = row['game_seconds_remaining']
            last_score_team = row['posteam']

    return result


def calculate_turnover_context(game_plays, window=10):
    """
    Calculate turnover context.

    Args:
        game_plays: DataFrame of plays for a single game, chronologically ordered
        window: Number of plays to look back for turnover count (default: 10)

    Returns:
        DataFrame: Original data with turnover context columns added
    """
    result = game_plays.copy()

    # Initialize columns
    result['turnovers_last_10_plays_offense'] = 0
    result['turnovers_last_10_plays_defense'] = 0
    result['time_since_turnover'] = np.nan

    # Ensure turnover column exists
    if 'turnover' not in result.columns:
        result['turnover'] = 0

    # Track turnovers for each team
    home_team = result['home_team'].iloc[0] if 'home_team' in result.columns else None
    away_team = result['away_team'].iloc[0] if 'away_team' in result.columns else None

    last_turnover_time = None

    for i, (idx, row) in enumerate(result.iterrows()):
        # Count turnovers in last N plays
        start_idx = max(0, i - window)
        recent_plays = result.iloc[start_idx:i]

        if len(recent_plays) > 0 and 'turnover' in recent_plays.columns:
            # Turnovers by current offense
            offense_turnovers = recent_plays[
                recent_plays['posteam'] == row['posteam']
            ]['turnover'].sum()
            result.at[idx, 'turnovers_last_10_plays_offense'] = offense_turnovers

            # Turnovers by current defense (turnovers they caused)
            defense_turnovers = recent_plays[
                recent_plays['defteam'] == row['defteam']
            ]['turnover'].sum()
            result.at[idx, 'turnovers_last_10_plays_defense'] = defense_turnovers

        # Time since last turnover (either team)
        if last_turnover_time is not None and 'game_seconds_remaining' in result.columns:
            time_diff = last_turnover_time - row['game_seconds_remaining']
            result.at[idx, 'time_since_turnover'] = time_diff

        # Update if this is a turnover
        if row.get('turnover', 0) == 1:
            if 'game_seconds_remaining' in result.columns:
                last_turnover_time = row['game_seconds_remaining']

    return result


def add_game_context(game_plays):
    """
    Add all rolling context features to a single game's plays.

    Args:
        game_plays: DataFrame of plays for a single game, chronologically ordered

    Returns:
        DataFrame: Plays with all context columns added
    """
    if game_plays.empty:
        return game_plays

    # Ensure chronological order
    if 'play_id' in game_plays.columns:
        game_plays = game_plays.sort_values('play_id')

    # Add each type of context
    logger.debug(f"Calculating offensive history...")
    game_plays = calculate_recent_offensive_history(game_plays)

    logger.debug(f"Calculating defensive history...")
    game_plays = calculate_recent_defensive_history(game_plays)

    logger.debug(f"Calculating drive context...")
    game_plays = calculate_drive_context(game_plays)

    logger.debug(f"Calculating scoring context...")
    game_plays = calculate_scoring_context(game_plays)

    logger.debug(f"Calculating turnover context...")
    game_plays = calculate_turnover_context(game_plays)

    return game_plays


def process_all_games_with_context(seasons=None, save=True):
    """
    Process all games and add rolling context to each play.

    Args:
        seasons: List of seasons to process (default: 2018-2024)
        save: Whether to save results (default: True)

    Returns:
        DataFrame: All plays with context columns
    """
    logger.info("Loading play-by-play data...")
    pbp_data = load_pbp_data(seasons=seasons)

    if pbp_data.empty:
        logger.error("No data loaded")
        return pd.DataFrame()

    logger.info(f"Processing {len(pbp_data):,} plays across {pbp_data['game_id'].nunique():,} games")

    # Process each game separately
    all_games = []
    games = pbp_data['game_id'].unique()

    for i, game_id in enumerate(games, 1):
        if i % 100 == 0:
            logger.info(f"Processing game {i:,} / {len(games):,} ({i/len(games):.1%})")

        game_plays = pbp_data[pbp_data['game_id'] == game_id].copy()
        game_with_context = add_game_context(game_plays)
        all_games.append(game_with_context)

    # Combine all games
    logger.info("Combining all games...")
    result = pd.concat(all_games, ignore_index=True)

    logger.info(f"Final dataset shape: {result.shape}")
    logger.info(f"Context columns added: {len(result.columns) - len(pbp_data.columns)}")

    # Show which columns were added
    new_cols = set(result.columns) - set(pbp_data.columns)
    logger.info(f"New columns: {sorted(new_cols)}")

    # Save if requested
    if save:
        save_processed_data(result, 'plays_with_context')
        logger.info("Saved to data/processed/plays_with_context.parquet")

    return result


def get_context_summary(plays_with_context):
    """
    Generate summary statistics for context features.

    Args:
        plays_with_context: DataFrame with context columns

    Returns:
        DataFrame: Summary statistics
    """
    context_cols = [
        'off_success_rate', 'off_yards_per_play', 'off_explosive_plays',
        'def_success_rate', 'def_yards_per_play',
        'plays_this_drive', 'yards_this_drive', 'drive_efficiency',
        'time_since_last_score', 'momentum_shift',
        'turnovers_last_10_plays_offense', 'turnovers_last_10_plays_defense',
        'time_since_turnover'
    ]

    available_cols = [col for col in context_cols if col in plays_with_context.columns]

    summary = plays_with_context[available_cols].describe()

    # Add additional stats
    for col in available_cols:
        if col in plays_with_context.columns:
            null_pct = plays_with_context[col].isna().sum() / len(plays_with_context)
            summary.loc['null_pct', col] = null_pct

    return summary


if __name__ == "__main__":
    """
    Run context calculation for all games.
    """
    logger.info("="*60)
    logger.info("GAME CONTEXT CALCULATOR")
    logger.info("="*60)

    # Process recent seasons
    seasons = [2022, 2023]
    logger.info(f"Processing seasons: {seasons}")

    result = process_all_games_with_context(seasons=seasons, save=True)

    # Show summary
    logger.info("\n" + "="*60)
    logger.info("CONTEXT SUMMARY")
    logger.info("="*60)

    summary = get_context_summary(result)
    print(summary)

    # Show examples
    logger.info("\n" + "="*60)
    logger.info("EXAMPLE PLAYS WITH CONTEXT")
    logger.info("="*60)

    example_cols = [
        'game_id', 'posteam', 'down', 'ydstogo',
        'off_success_rate', 'off_yards_per_play', 'plays_this_drive',
        'time_since_last_score', 'momentum_shift'
    ]
    available_example_cols = [col for col in example_cols if col in result.columns]

    print(result[available_example_cols].head(20))

    logger.info("\n" + "="*60)
    logger.info("COMPLETE!")
    logger.info("="*60)
