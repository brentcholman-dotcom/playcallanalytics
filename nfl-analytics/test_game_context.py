"""
Test script for game context calculations.

This script demonstrates and validates the rolling context calculations.
"""

import sys
from pathlib import Path
import pandas as pd

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from ingestion.play_by_play import load_pbp_data
from models.game_context import (
    add_game_context,
    process_all_games_with_context,
    get_context_summary,
    calculate_recent_offensive_history,
    calculate_recent_defensive_history,
    calculate_drive_context,
    calculate_scoring_context,
    calculate_turnover_context
)


def test_single_game_context():
    """Test context calculation for a single game."""
    print("\n" + "="*60)
    print("TEST 1: Single Game Context")
    print("="*60)

    # Load a small sample
    print("Loading 2023 season data...")
    pbp_data = load_pbp_data(seasons=[2023])

    # Get first game
    first_game_id = pbp_data['game_id'].iloc[0]
    game_plays = pbp_data[pbp_data['game_id'] == first_game_id].copy()

    print(f"\nGame ID: {first_game_id}")
    print(f"Total plays: {len(game_plays)}")

    # Add context
    print("\nAdding game context...")
    game_with_context = add_game_context(game_plays)

    print(f"Columns added: {len(game_with_context.columns) - len(game_plays.columns)}")

    # Show new columns
    new_cols = set(game_with_context.columns) - set(game_plays.columns)
    print(f"\nNew context columns:")
    for col in sorted(new_cols):
        print(f"  - {col}")

    # Show sample data
    print("\nSample plays with context:")
    sample_cols = [
        'posteam', 'down', 'ydstogo', 'yards_gained',
        'off_success_rate', 'off_yards_per_play', 'plays_this_drive'
    ]
    available_cols = [col for col in sample_cols if col in game_with_context.columns]
    print(game_with_context[available_cols].head(15))

    return game_with_context


def test_offensive_history():
    """Test offensive history calculations."""
    print("\n" + "="*60)
    print("TEST 2: Offensive History Calculation")
    print("="*60)

    pbp_data = load_pbp_data(seasons=[2023])
    first_game_id = pbp_data['game_id'].iloc[0]
    game_plays = pbp_data[pbp_data['game_id'] == first_game_id].copy()

    print("Calculating offensive history...")
    result = calculate_recent_offensive_history(game_plays, window=5)

    print("\nOffensive metrics summary:")
    metrics = ['off_success_rate', 'off_yards_per_play', 'off_explosive_plays']
    print(result[metrics].describe())

    # Show how metrics evolve
    print("\nFirst 10 plays with offensive history:")
    display_cols = ['posteam', 'yards_gained', 'off_success_rate', 'off_yards_per_play']
    available_cols = [col for col in display_cols if col in result.columns]
    print(result[available_cols].head(10))

    return result


def test_drive_context():
    """Test drive context calculations."""
    print("\n" + "="*60)
    print("TEST 3: Drive Context Calculation")
    print("="*60)

    pbp_data = load_pbp_data(seasons=[2023])
    first_game_id = pbp_data['game_id'].iloc[0]
    game_plays = pbp_data[pbp_data['game_id'] == first_game_id].copy()

    print("Calculating drive context...")
    result = calculate_drive_context(game_plays)

    print("\nDrive metrics summary:")
    metrics = ['plays_this_drive', 'yards_this_drive', 'drive_efficiency']
    print(result[metrics].describe())

    # Show drive progression
    print("\nExample drive progression (first 20 plays):")
    display_cols = [
        'posteam', 'down', 'ydstogo', 'yards_gained',
        'plays_this_drive', 'yards_this_drive', 'drive_efficiency'
    ]
    available_cols = [col for col in display_cols if col in result.columns]
    print(result[available_cols].head(20))

    return result


def test_scoring_context():
    """Test scoring and momentum calculations."""
    print("\n" + "="*60)
    print("TEST 4: Scoring & Momentum Context")
    print("="*60)

    pbp_data = load_pbp_data(seasons=[2023])
    first_game_id = pbp_data['game_id'].iloc[0]
    game_plays = pbp_data[pbp_data['game_id'] == first_game_id].copy()

    print("Calculating scoring context...")
    result = calculate_scoring_context(game_plays)

    print("\nScoring metrics summary:")
    print(f"Plays with momentum shift: {result['momentum_shift'].sum()}")
    print(f"Average time since last score: {result['time_since_last_score'].mean():.1f} seconds")

    # Show scoring plays
    if 'touchdown' in result.columns:
        scoring_plays = result[result['touchdown'] == 1]
        print(f"\nTotal touchdowns: {len(scoring_plays)}")

    return result


def test_turnover_context():
    """Test turnover context calculations."""
    print("\n" + "="*60)
    print("TEST 5: Turnover Context")
    print("="*60)

    pbp_data = load_pbp_data(seasons=[2023])
    first_game_id = pbp_data['game_id'].iloc[0]
    game_plays = pbp_data[pbp_data['game_id'] == first_game_id].copy()

    print("Calculating turnover context...")
    result = calculate_turnover_context(game_plays, window=10)

    print("\nTurnover metrics summary:")
    metrics = [
        'turnovers_last_10_plays_offense',
        'turnovers_last_10_plays_defense',
        'time_since_turnover'
    ]
    print(result[metrics].describe())

    # Show turnovers
    if 'turnover' in result.columns:
        turnovers = result[result['turnover'] == 1]
        print(f"\nTotal turnovers: {len(turnovers)}")

    return result


def test_full_pipeline_small():
    """Test the full pipeline with a small dataset."""
    print("\n" + "="*60)
    print("TEST 6: Full Pipeline (2023 Season)")
    print("="*60)

    print("Running full context pipeline...")
    result = process_all_games_with_context(seasons=[2023], save=True)

    print(f"\nFinal dataset shape: {result.shape}")
    print(f"Total games processed: {result['game_id'].nunique()}")
    print(f"Total plays: {len(result):,}")

    # Get summary
    print("\n" + "="*60)
    print("CONTEXT SUMMARY STATISTICS")
    print("="*60)
    summary = get_context_summary(result)
    print(summary)

    # Show some interesting examples
    print("\n" + "="*60)
    print("EXAMPLE: High Success Rate Offenses")
    print("="*60)
    high_success = result[result['off_success_rate'] >= 0.8]
    if not high_success.empty:
        example_cols = [
            'posteam', 'down', 'ydstogo',
            'off_success_rate', 'off_yards_per_play', 'off_explosive_plays'
        ]
        available_cols = [col for col in example_cols if col in high_success.columns]
        print(high_success[available_cols].head(10))

    print("\n" + "="*60)
    print("EXAMPLE: Momentum Shifts")
    print("="*60)
    momentum_shifts = result[result['momentum_shift'] == True]
    if not momentum_shifts.empty:
        print(f"Total plays with momentum shifts: {len(momentum_shifts):,}")
        example_cols = [
            'game_id', 'posteam', 'score_differential',
            'time_since_last_score', 'last_score_team'
        ]
        available_cols = [col for col in example_cols if col in momentum_shifts.columns]
        print(momentum_shifts[available_cols].head(10))

    return result


def test_context_quality():
    """Test data quality of context features."""
    print("\n" + "="*60)
    print("TEST 7: Context Data Quality")
    print("="*60)

    # Load processed data if it exists
    from pathlib import Path
    parquet_file = Path(__file__).parent / 'data' / 'processed' / 'plays_with_context.parquet'

    if parquet_file.exists():
        print(f"Loading existing data from {parquet_file}...")
        result = pd.read_parquet(parquet_file)
    else:
        print("No existing data found, running pipeline...")
        result = process_all_games_with_context(seasons=[2023], save=True)

    print(f"\nDataset shape: {result.shape}")

    # Check for nulls
    context_cols = [
        'off_success_rate', 'off_yards_per_play', 'off_explosive_plays',
        'def_success_rate', 'def_yards_per_play',
        'plays_this_drive', 'yards_this_drive', 'drive_efficiency',
        'time_since_last_score', 'momentum_shift',
        'turnovers_last_10_plays_offense', 'turnovers_last_10_plays_defense'
    ]

    print("\nNull values in context columns:")
    for col in context_cols:
        if col in result.columns:
            null_count = result[col].isna().sum()
            null_pct = null_count / len(result) * 100
            print(f"  {col:40s}: {null_count:8,} ({null_pct:5.2f}%)")

    # Check ranges
    print("\nValue ranges for numeric columns:")
    numeric_cols = [
        'off_success_rate', 'off_yards_per_play', 'def_success_rate',
        'def_yards_per_play', 'drive_efficiency'
    ]
    for col in numeric_cols:
        if col in result.columns:
            min_val = result[col].min()
            max_val = result[col].max()
            mean_val = result[col].mean()
            print(f"  {col:40s}: [{min_val:7.2f}, {max_val:7.2f}] (mean: {mean_val:6.2f})")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("GAME CONTEXT TEST SUITE")
    print("="*60)

    try:
        # Test 1: Single game
        test_single_game_context()

        # Test 2: Offensive history
        test_offensive_history()

        # Test 3: Drive context
        test_drive_context()

        # Test 4: Scoring context
        test_scoring_context()

        # Test 5: Turnover context
        test_turnover_context()

        # Test 6: Full pipeline
        test_full_pipeline_small()

        # Test 7: Data quality
        test_context_quality()

        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
