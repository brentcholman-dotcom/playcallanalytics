"""
Play-by-Play Data Loading

This module loads historical NFL play-by-play data using nfl_data_py
(Python wrapper for nflfastR) for analysis and model training.
"""

import logging
import os
from pathlib import Path
import pandas as pd
import nfl_data_py as nfl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define relevant columns to filter
RELEVANT_COLUMNS = [
    # Game identifiers
    'game_id', 'season', 'week', 'home_team', 'away_team', 'game_date',
    # Situation
    'down', 'ydstogo', 'yardline_100', 'game_seconds_remaining',
    'quarter', 'qtr', 'half_seconds_remaining',
    # Score
    'home_score', 'away_score', 'score_differential', 'posteam_score', 'defteam_score',
    # Play info
    'play_type', 'yards_gained', 'first_down', 'touchdown', 'turnover',
    'fumble', 'interception', 'fumble_lost', 'fourth_down_converted',
    'fourth_down_failed',
    # Context
    'posteam', 'defteam', 'posteam_type', 'side_of_field',
    # Existing analytics
    'wp', 'wpa', 'ep', 'epa', 'vegas_wp', 'vegas_wpa',
    # Additional context
    'roof', 'surface', 'temp', 'wind',
    'stadium', 'stadium_id', 'weather',
    # Play description
    'desc', 'play_id'
]


def load_pbp_data(seasons=None, columns=None, include_playoffs=True):
    """
    Load play-by-play data for specified seasons from nflfastR.

    Args:
        seasons: List of seasons (e.g., [2020, 2021, 2022]).
                 If None, loads 2018-2024.
        columns: Optional list of columns to load. If None, loads RELEVANT_COLUMNS.
        include_playoffs: Boolean to include playoff games (default: True)

    Returns:
        DataFrame: Play-by-play data with validation
    """
    if seasons is None:
        seasons = list(range(2018, 2025))  # 2018-2024

    logger.info(f"Loading play-by-play data for seasons: {seasons}")
    logger.info(f"Include playoffs: {include_playoffs}")

    try:
        # Load data from nfl_data_py
        pbp_data = nfl.import_pbp_data(seasons, columns=None)
        logger.info(f"Loaded {len(pbp_data):,} plays from nflfastR")

        # Validate data
        if pbp_data is None or pbp_data.empty:
            logger.error("No data loaded from nflfastR")
            return pd.DataFrame()

        # Filter to regular season and playoffs (exclude preseason)
        if 'season_type' in pbp_data.columns:
            if include_playoffs:
                pbp_data = pbp_data[pbp_data['season_type'].isin(['REG', 'POST'])]
                logger.info(f"Filtered to regular season and playoffs: {len(pbp_data):,} plays")
            else:
                pbp_data = pbp_data[pbp_data['season_type'] == 'REG']
                logger.info(f"Filtered to regular season only: {len(pbp_data):,} plays")

        # Filter to relevant columns if specified
        if columns is not None:
            available_cols = [col for col in columns if col in pbp_data.columns]
            missing_cols = set(columns) - set(available_cols)
            if missing_cols:
                logger.warning(f"Columns not found in data: {missing_cols}")
            pbp_data = pbp_data[available_cols]
        else:
            # Use default relevant columns
            available_cols = [col for col in RELEVANT_COLUMNS if col in pbp_data.columns]
            missing_cols = set(RELEVANT_COLUMNS) - set(available_cols)
            if missing_cols:
                logger.warning(f"Default columns not found: {missing_cols}")
            pbp_data = pbp_data[available_cols]

        logger.info(f"Final dataset shape: {pbp_data.shape}")
        logger.info(f"Columns included: {len(pbp_data.columns)}")

        # Basic validation
        _validate_pbp_data(pbp_data)

        return pbp_data

    except Exception as e:
        logger.error(f"Error loading play-by-play data: {str(e)}", exc_info=True)
        raise


def filter_fourth_down_plays(pbp_data):
    """
    Filter dataset to 4th down plays only and classify decisions.

    Args:
        pbp_data: Play-by-play DataFrame

    Returns:
        DataFrame: Filtered 4th down plays with decision classification
    """
    logger.info("Filtering to 4th down plays...")

    if pbp_data is None or pbp_data.empty:
        logger.error("Input data is empty")
        return pd.DataFrame()

    # Filter to 4th down
    fourth_down = pbp_data[pbp_data['down'] == 4].copy()
    logger.info(f"Found {len(fourth_down):,} 4th down plays")

    if fourth_down.empty:
        logger.warning("No 4th down plays found in dataset")
        return pd.DataFrame()

    # Classify decision type
    fourth_down['decision'] = _classify_fourth_down_decision(fourth_down)

    # Track outcome
    fourth_down['converted'] = fourth_down.apply(_determine_conversion, axis=1)

    # Add additional context
    fourth_down['success'] = fourth_down.apply(_determine_success, axis=1)

    # Log decision breakdown
    decision_counts = fourth_down['decision'].value_counts()
    logger.info(f"4th down decision breakdown:\n{decision_counts}")

    conversion_rate = fourth_down['converted'].mean() if 'converted' in fourth_down.columns else 0
    logger.info(f"Overall conversion rate: {conversion_rate:.2%}")

    return fourth_down


def _classify_fourth_down_decision(df):
    """
    Classify 4th down decisions into: went_for_it, punted, kicked_fg.

    Args:
        df: DataFrame of 4th down plays

    Returns:
        Series: Decision classification
    """
    decisions = pd.Series('unknown', index=df.index)

    if 'play_type' in df.columns:
        # Field goal attempts
        decisions[df['play_type'].isin(['field_goal', 'extra_point'])] = 'kicked_fg'

        # Punts
        decisions[df['play_type'] == 'punt'] = 'punted'

        # Going for it (run, pass, or other offensive play)
        went_for_it_types = ['run', 'pass', 'qb_kneel', 'qb_spike']
        decisions[df['play_type'].isin(went_for_it_types)] = 'went_for_it'

    # Log any unknown decisions
    unknown_count = (decisions == 'unknown').sum()
    if unknown_count > 0:
        logger.warning(f"Could not classify {unknown_count} 4th down plays")

    return decisions


def _determine_conversion(row):
    """
    Determine if a 4th down attempt was converted.

    Args:
        row: DataFrame row

    Returns:
        bool or None: True if converted, False if not, None if N/A
    """
    # Only applies to "went_for_it" decisions
    if 'decision' not in row.index or row['decision'] != 'went_for_it':
        return None

    # Check fourth_down_converted column if available
    if 'fourth_down_converted' in row.index and pd.notna(row['fourth_down_converted']):
        return bool(row['fourth_down_converted'])

    # Check fourth_down_failed column if available
    if 'fourth_down_failed' in row.index and pd.notna(row['fourth_down_failed']):
        return not bool(row['fourth_down_failed'])

    # Fallback: check if first down was achieved
    if 'first_down' in row.index and pd.notna(row['first_down']):
        return bool(row['first_down'])

    # Fallback: check yards gained vs yards to go
    if 'yards_gained' in row.index and 'ydstogo' in row.index:
        if pd.notna(row['yards_gained']) and pd.notna(row['ydstogo']):
            return row['yards_gained'] >= row['ydstogo']

    return None


def _determine_success(row):
    """
    Determine if the play was successful (more flexible than conversion).

    Args:
        row: DataFrame row

    Returns:
        bool or None: True if successful outcome
    """
    decision = row.get('decision', 'unknown')

    if decision == 'went_for_it':
        # Conversion or touchdown
        converted = row.get('converted', None)
        touchdown = row.get('touchdown', 0)
        if converted is True or touchdown == 1:
            return True
        elif converted is False:
            return False
        return None

    elif decision == 'kicked_fg':
        # Would need field_goal_result column to determine
        # For now, just return None
        return None

    elif decision == 'punted':
        # Punt success is complex - could measure by field position change
        # For now, return None
        return None

    return None


def _validate_pbp_data(pbp_data):
    """
    Validate play-by-play data for completeness and quality.

    Args:
        pbp_data: DataFrame to validate

    Raises:
        ValueError: If critical validation fails
    """
    logger.info("Validating play-by-play data...")

    # Check for required columns
    required_cols = ['game_id', 'season', 'down', 'play_type']
    missing_required = [col for col in required_cols if col not in pbp_data.columns]
    if missing_required:
        raise ValueError(f"Missing required columns: {missing_required}")

    # Check for null values in critical columns
    for col in required_cols:
        null_count = pbp_data[col].isna().sum()
        if null_count > 0:
            logger.warning(f"Column '{col}' has {null_count:,} null values ({null_count/len(pbp_data):.2%})")

    # Check season range
    if 'season' in pbp_data.columns:
        seasons = pbp_data['season'].unique()
        logger.info(f"Seasons present: {sorted(seasons)}")
        if pbp_data['season'].min() < 2000 or pbp_data['season'].max() > 2030:
            logger.warning(f"Unusual season range: {pbp_data['season'].min()} to {pbp_data['season'].max()}")

    # Check down values
    if 'down' in pbp_data.columns:
        valid_downs = pbp_data['down'].isin([1, 2, 3, 4]).sum()
        logger.info(f"Valid down values: {valid_downs:,} / {len(pbp_data):,}")

    logger.info("Validation complete")


def enrich_play_context(pbp_data):
    """
    Add contextual features to play data.

    Args:
        pbp_data: Play-by-play DataFrame

    Returns:
        DataFrame: Enriched play data with additional context
    """
    logger.info("Enriching play data with contextual features...")

    enriched = pbp_data.copy()

    # Add time-based features
    if 'game_seconds_remaining' in enriched.columns:
        enriched['game_minutes_remaining'] = enriched['game_seconds_remaining'] / 60
        enriched['is_final_two_minutes'] = enriched['game_seconds_remaining'] <= 120

    if 'half_seconds_remaining' in enriched.columns:
        enriched['is_final_two_minutes_half'] = enriched['half_seconds_remaining'] <= 120

    # Add field position categories
    if 'yardline_100' in enriched.columns:
        enriched['field_position_category'] = pd.cut(
            enriched['yardline_100'],
            bins=[0, 20, 40, 60, 80, 100],
            labels=['red_zone', 'plus_territory', 'midfield', 'own_territory', 'deep_own']
        )

    # Add score differential categories
    if 'score_differential' in enriched.columns:
        enriched['score_situation'] = pd.cut(
            enriched['score_differential'],
            bins=[-100, -17, -9, -3, 3, 9, 17, 100],
            labels=['down_big', 'down_two_scores', 'down_one_score', 'close',
                    'up_one_score', 'up_two_scores', 'up_big']
        )

    # Add distance categories
    if 'ydstogo' in enriched.columns:
        enriched['distance_category'] = pd.cut(
            enriched['ydstogo'],
            bins=[0, 2, 4, 7, 100],
            labels=['short', 'medium', 'long', 'very_long']
        )

    logger.info(f"Added {len(enriched.columns) - len(pbp_data.columns)} new contextual features")

    return enriched


def save_processed_data(data, filename, output_dir='data/processed'):
    """
    Save processed data to file.

    Args:
        data: DataFrame to save
        filename: Name of output file (without extension)
        output_dir: Output directory path (default: data/processed)

    Returns:
        str: Path to saved file
    """
    # Get the project root (nfl-analytics directory)
    project_root = Path(__file__).parent.parent
    output_path = project_root / output_dir

    # Create directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    # Save to CSV and parquet for efficiency
    csv_file = output_path / f"{filename}.csv"
    parquet_file = output_path / f"{filename}.parquet"

    logger.info(f"Saving data to {output_path}")

    try:
        # Save as CSV
        data.to_csv(csv_file, index=False)
        logger.info(f"Saved CSV: {csv_file} ({os.path.getsize(csv_file) / 1024 / 1024:.2f} MB)")

        # Save as parquet (more efficient for large datasets)
        data.to_parquet(parquet_file, index=False)
        logger.info(f"Saved Parquet: {parquet_file} ({os.path.getsize(parquet_file) / 1024 / 1024:.2f} MB)")

        return str(parquet_file)

    except Exception as e:
        logger.error(f"Error saving data: {str(e)}", exc_info=True)
        raise


def load_and_process_fourth_downs(seasons=None, save=True):
    """
    Complete pipeline: load data, filter 4th downs, enrich, and save.

    Args:
        seasons: List of seasons to process (default: 2018-2024)
        save: Whether to save processed data (default: True)

    Returns:
        DataFrame: Processed 4th down data
    """
    logger.info("Starting complete 4th down processing pipeline...")

    # Load data
    pbp_data = load_pbp_data(seasons=seasons)

    # Filter to 4th downs
    fourth_downs = filter_fourth_down_plays(pbp_data)

    # Enrich with context
    fourth_downs_enriched = enrich_play_context(fourth_downs)

    # Save if requested
    if save and not fourth_downs_enriched.empty:
        seasons_str = f"{min(seasons)}-{max(seasons)}" if seasons else "2018-2024"
        filename = f"fourth_downs_{seasons_str}"
        save_processed_data(fourth_downs_enriched, filename)

    logger.info("Pipeline complete!")
    logger.info(f"Final dataset: {fourth_downs_enriched.shape}")

    return fourth_downs_enriched
