"""
Test script for play-by-play data ingestion.

This script demonstrates the usage of the data ingestion functions
and can be used to verify the implementation works correctly.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import from ingestion
sys.path.insert(0, str(Path(__file__).parent))

from ingestion.play_by_play import (
    load_pbp_data,
    filter_fourth_down_plays,
    enrich_play_context,
    save_processed_data,
    load_and_process_fourth_downs
)


def test_single_season():
    """Test loading a single season of data."""
    print("\n" + "="*60)
    print("TEST 1: Loading single season (2023)")
    print("="*60)

    # Load just 2023 season to keep it quick
    pbp_data = load_pbp_data(seasons=[2023])

    print(f"\nDataset shape: {pbp_data.shape}")
    print(f"Columns: {list(pbp_data.columns)}")
    print(f"\nFirst few rows:")
    print(pbp_data.head())

    return pbp_data


def test_fourth_down_filtering(pbp_data):
    """Test filtering to 4th down plays."""
    print("\n" + "="*60)
    print("TEST 2: Filtering to 4th down plays")
    print("="*60)

    fourth_downs = filter_fourth_down_plays(pbp_data)

    print(f"\n4th down plays shape: {fourth_downs.shape}")
    print(f"\nDecision breakdown:")
    print(fourth_downs['decision'].value_counts())

    print(f"\nConversion statistics:")
    went_for_it = fourth_downs[fourth_downs['decision'] == 'went_for_it']
    if not went_for_it.empty:
        conversions = went_for_it['converted'].value_counts()
        print(conversions)
        conversion_rate = went_for_it['converted'].sum() / len(went_for_it)
        print(f"Conversion rate: {conversion_rate:.2%}")

    return fourth_downs


def test_enrichment(fourth_downs):
    """Test data enrichment."""
    print("\n" + "="*60)
    print("TEST 3: Enriching data with contextual features")
    print("="*60)

    enriched = enrich_play_context(fourth_downs)

    print(f"\nOriginal columns: {len(fourth_downs.columns)}")
    print(f"Enriched columns: {len(enriched.columns)}")
    print(f"New columns added: {len(enriched.columns) - len(fourth_downs.columns)}")

    new_cols = set(enriched.columns) - set(fourth_downs.columns)
    print(f"\nNew contextual features: {new_cols}")

    # Show some examples
    if 'field_position_category' in enriched.columns:
        print(f"\nField position breakdown:")
        print(enriched['field_position_category'].value_counts())

    if 'distance_category' in enriched.columns:
        print(f"\nDistance category breakdown:")
        print(enriched['distance_category'].value_counts())

    return enriched


def test_full_pipeline():
    """Test the complete pipeline."""
    print("\n" + "="*60)
    print("TEST 4: Running complete pipeline (2022-2023)")
    print("="*60)

    # Run complete pipeline for 2 seasons
    result = load_and_process_fourth_downs(
        seasons=[2022, 2023],
        save=True
    )

    print(f"\nFinal processed data shape: {result.shape}")
    print(f"\nSample of processed data:")
    print(result[['game_id', 'season', 'week', 'posteam', 'ydstogo',
                  'decision', 'converted', 'field_position_category']].head(10))

    return result


def test_data_quality(data):
    """Test data quality checks."""
    print("\n" + "="*60)
    print("TEST 5: Data quality checks")
    print("="*60)

    print(f"\nMissing values per column:")
    missing = data.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    print(missing.head(10))

    print(f"\nData types:")
    print(data.dtypes.value_counts())

    print(f"\nMemory usage:")
    memory_mb = data.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"{memory_mb:.2f} MB")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("NFL PLAY-BY-PLAY DATA INGESTION TESTS")
    print("="*60)

    try:
        # Test 1: Load single season
        pbp_data = test_single_season()

        # Test 2: Filter to 4th downs
        fourth_downs = test_fourth_down_filtering(pbp_data)

        # Test 3: Enrich data
        enriched = test_enrichment(fourth_downs)

        # Test 4: Full pipeline
        result = test_full_pipeline()

        # Test 5: Data quality
        test_data_quality(result)

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
