"""
Test script for momentum scoring algorithm.

This script demonstrates and validates the momentum calculations.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from ingestion.play_by_play import load_pbp_data
from models.game_context import add_game_context
from models.momentum import (
    calculate_momentum,
    add_momentum_scores,
    get_momentum_category,
    analyze_momentum_distribution,
    calculate_season_averages,
    calculate_recent_success_score,
    calculate_drive_efficiency_score,
    calculate_scoring_recency_score,
    calculate_turnover_impact_score
)


def test_component_calculations():
    """Test individual momentum components."""
    print("\n" + "="*60)
    print("TEST 1: Individual Component Calculations")
    print("="*60)

    print("\n1. Recent Success Score (0-40 points):")
    for rate in [0.0, 0.25, 0.5, 0.75, 1.0]:
        score = calculate_recent_success_score(rate)
        print(f"   Success rate {rate:.0%} = {score:.1f} points")

    print("\n2. Drive Efficiency Score (0-25 points):")
    season_avg = 5.5
    for efficiency in [2.75, 4.125, 5.5, 6.875, 8.25]:
        score = calculate_drive_efficiency_score(efficiency, season_avg)
        ratio = efficiency / season_avg
        print(f"   {efficiency:.2f} yds/play ({ratio:.1%} of avg) = {score:.1f} points")

    print("\n3. Scoring Recency Score (0-20 points):")
    for time, desc in [(60, "1 min"), (150, "2.5 min"), (350, "5.8 min"), (700, "11.7 min")]:
        score = calculate_scoring_recency_score(time, 'BUF', 'BUF')
        print(f"   Team scored {desc} ago = {score:.1f} points")

    print("\n4. Turnover Impact Score (0-15 points):")
    scenarios = [
        (0, 0, "No recent turnovers"),
        (1, 0, "Own turnover"),
        (0, 1, "Forced turnover"),
        (1, 1, "Both teams had turnover")
    ]
    for off_to, def_to, desc in scenarios:
        score = calculate_turnover_impact_score(off_to, def_to)
        print(f"   {desc} = {score:.1f} points")


def test_single_game_momentum():
    """Test momentum calculation for a single game."""
    print("\n" + "="*60)
    print("TEST 2: Single Game Momentum")
    print("="*60)

    # Load sample data
    print("Loading 2023 season...")
    pbp = load_pbp_data(seasons=[2023])

    # Get first game
    first_game = pbp['game_id'].iloc[0]
    game = pbp[pbp['game_id'] == first_game].copy()

    print(f"\nProcessing game: {first_game}")
    print(f"Total plays: {len(game)}")

    # Add game context
    print("\nAdding game context...")
    game_with_context = add_game_context(game)

    # Add momentum scores
    print("Calculating momentum scores...")
    game_with_momentum = add_momentum_scores(game_with_context)

    # Show examples
    print("\nSample plays with momentum scores:")
    display_cols = [
        'posteam', 'down', 'ydstogo', 'yards_gained',
        'off_success_rate', 'drive_efficiency',
        'momentum_score'
    ]
    available_cols = [col for col in display_cols if col in game_with_momentum.columns]
    print(game_with_momentum[available_cols].head(20))

    # Show momentum distribution
    print("\nMomentum score statistics:")
    print(game_with_momentum['momentum_score'].describe())

    return game_with_momentum


def test_momentum_categories():
    """Test momentum categorization."""
    print("\n" + "="*60)
    print("TEST 3: Momentum Categories")
    print("="*60)

    # Load and process data
    pbp = load_pbp_data(seasons=[2023])
    first_game = pbp['game_id'].iloc[0]
    game = pbp[pbp['game_id'] == first_game].copy()
    game_with_context = add_game_context(game)
    game_with_momentum = add_momentum_scores(game_with_context)

    # Add categories
    game_with_momentum['momentum_category'] = game_with_momentum['momentum_score'].apply(
        get_momentum_category
    )

    # Show distribution
    print("\nMomentum category distribution:")
    print(game_with_momentum['momentum_category'].value_counts().sort_index())

    # Show examples from each category
    print("\nExample plays from each category:")
    for category in ['cold', 'average', 'good', 'hot']:
        plays = game_with_momentum[game_with_momentum['momentum_category'] == category]
        if not plays.empty:
            example = plays.iloc[0]
            print(f"\n{category.upper()}:")
            print(f"  Momentum Score: {example['momentum_score']:.1f}")
            print(f"  Team: {example.get('posteam', 'N/A')}")
            print(f"  Success Rate: {example.get('off_success_rate', np.nan):.1%}")
            print(f"  Drive Efficiency: {example.get('drive_efficiency', np.nan):.2f}")

    return game_with_momentum


def test_momentum_vs_outcomes():
    """Test relationship between momentum and play outcomes."""
    print("\n" + "="*60)
    print("TEST 4: Momentum vs Play Outcomes")
    print("="*60)

    # Load and process data
    pbp = load_pbp_data(seasons=[2023])
    first_game = pbp['game_id'].iloc[0]
    game = pbp[pbp['game_id'] == first_game].copy()
    game_with_context = add_game_context(game)
    game_with_momentum = add_momentum_scores(game_with_context)

    # Add categories
    game_with_momentum['momentum_category'] = game_with_momentum['momentum_score'].apply(
        get_momentum_category
    )

    # Analyze outcomes by momentum
    if 'yards_gained' in game_with_momentum.columns:
        print("\nAverage yards gained by momentum category:")
        yds_by_momentum = game_with_momentum.groupby('momentum_category')['yards_gained'].mean()
        for cat, yds in yds_by_momentum.items():
            print(f"  {cat:10s}: {yds:6.2f} yards")

    if 'first_down' in game_with_momentum.columns:
        print("\nFirst down rate by momentum category:")
        fd_by_momentum = game_with_momentum.groupby('momentum_category')['first_down'].mean()
        for cat, rate in fd_by_momentum.items():
            print(f"  {cat:10s}: {rate:6.1%}")

    return game_with_momentum


def test_multiple_games():
    """Test momentum across multiple games."""
    print("\n" + "="*60)
    print("TEST 5: Multiple Games Analysis")
    print("="*60)

    # Load data
    print("Loading 2023 season...")
    pbp = load_pbp_data(seasons=[2023])

    # Process first 3 games
    games = pbp['game_id'].unique()[:3]
    print(f"\nProcessing {len(games)} games...")

    all_games = []
    for i, game_id in enumerate(games, 1):
        print(f"  Game {i}/{len(games)}: {game_id}")
        game = pbp[pbp['game_id'] == game_id].copy()
        game_with_context = add_game_context(game)
        game_with_momentum = add_momentum_scores(game_with_context)
        all_games.append(game_with_momentum)

    # Combine
    combined = pd.concat(all_games, ignore_index=True)

    print(f"\nCombined dataset: {len(combined):,} plays")

    # Overall statistics
    print("\nOverall momentum statistics:")
    print(combined['momentum_score'].describe())

    # Distribution analysis
    print("\n" + "="*60)
    print("MOMENTUM DISTRIBUTION ANALYSIS")
    print("="*60)
    summary = analyze_momentum_distribution(combined)
    print(summary)

    return combined


def test_extreme_scenarios():
    """Test momentum in extreme scenarios."""
    print("\n" + "="*60)
    print("TEST 6: Extreme Scenarios")
    print("="*60)

    # Create mock data for extreme scenarios
    season_avg_ypp = {'TEST': 5.5}

    print("\n1. Perfect offensive performance:")
    perfect_row = pd.Series({
        'posteam': 'TEST',
        'off_success_rate': 1.0,  # 100% success
        'drive_efficiency': 8.25,  # 50% above average
        'time_since_last_score': 60,  # Just scored
        'last_score_team': 'TEST',
        'turnovers_last_10_plays_offense': 0,
        'turnovers_last_10_plays_defense': 1  # Forced turnover
    })
    perfect_score = calculate_momentum(perfect_row, season_avg_ypp)
    print(f"   Momentum Score: {perfect_score:.1f}/100")
    print(f"   Category: {get_momentum_category(perfect_score)}")

    print("\n2. Terrible offensive performance:")
    terrible_row = pd.Series({
        'posteam': 'TEST',
        'off_success_rate': 0.0,  # 0% success
        'drive_efficiency': 2.75,  # 50% below average
        'time_since_last_score': 60,  # Opponent just scored
        'last_score_team': 'OPP',
        'turnovers_last_10_plays_offense': 1,  # Just turned it over
        'turnovers_last_10_plays_defense': 0
    })
    terrible_score = calculate_momentum(terrible_row, season_avg_ypp)
    print(f"   Momentum Score: {terrible_score:.1f}/100")
    print(f"   Category: {get_momentum_category(terrible_score)}")

    print("\n3. Average performance:")
    average_row = pd.Series({
        'posteam': 'TEST',
        'off_success_rate': 0.5,  # 50% success
        'drive_efficiency': 5.5,  # At average
        'time_since_last_score': 700,  # Long time ago
        'last_score_team': 'TEST',
        'turnovers_last_10_plays_offense': 0,
        'turnovers_last_10_plays_defense': 0
    })
    average_score = calculate_momentum(average_row, season_avg_ypp)
    print(f"   Momentum Score: {average_score:.1f}/100")
    print(f"   Category: {get_momentum_category(average_score)}")


def test_fourth_down_momentum():
    """Test momentum specifically for 4th down situations."""
    print("\n" + "="*60)
    print("TEST 7: 4th Down Momentum Analysis")
    print("="*60)

    # Load data
    pbp = load_pbp_data(seasons=[2023])

    # Filter to 4th downs
    fourth_downs = pbp[pbp['down'] == 4].copy()
    print(f"\nTotal 4th down plays: {len(fourth_downs):,}")

    # Add context and momentum to first game with 4th downs
    game_ids_with_4th = fourth_downs['game_id'].unique()
    if len(game_ids_with_4th) > 0:
        first_game = game_ids_with_4th[0]
        print(f"Processing game: {first_game}")

        game = pbp[pbp['game_id'] == first_game].copy()
        game_with_context = add_game_context(game)
        game_with_momentum = add_momentum_scores(game_with_context)

        # Filter to 4th downs
        game_4th_downs = game_with_momentum[game_with_momentum['down'] == 4].copy()
        print(f"4th down plays in this game: {len(game_4th_downs)}")

        # Show momentum on 4th downs
        print("\n4th down plays with momentum:")
        display_cols = [
            'posteam', 'ydstogo', 'yardline_100',
            'off_success_rate', 'momentum_score'
        ]
        available_cols = [col for col in display_cols if col in game_4th_downs.columns]
        print(game_4th_downs[available_cols].head(10))

        # Momentum distribution on 4th downs
        print("\nMomentum statistics for 4th downs:")
        print(game_4th_downs['momentum_score'].describe())


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("MOMENTUM SCORING TEST SUITE")
    print("="*60)

    try:
        # Test 1: Component calculations
        test_component_calculations()

        # Test 2: Single game
        test_single_game_momentum()

        # Test 3: Categories
        test_momentum_categories()

        # Test 4: Outcomes
        test_momentum_vs_outcomes()

        # Test 5: Multiple games
        test_multiple_games()

        # Test 6: Extreme scenarios
        test_extreme_scenarios()

        # Test 7: 4th downs
        test_fourth_down_momentum()

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
