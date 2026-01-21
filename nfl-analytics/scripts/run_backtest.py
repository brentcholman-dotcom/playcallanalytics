#!/usr/bin/env python3
"""
Run Backtest Script

This script runs a comprehensive backtest of the context-aware 4th down model
against static analytics, showing where contextual factors add value.
"""

import sys
from pathlib import Path
import json
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.play_by_play import load_pbp_data
from models import ConversionModel, build_base_rate_table
from backtesting.validator import BacktestRunner, BacktestResults, generate_report
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run comprehensive backtest."""

    logger.info("="*80)
    logger.info("CONTEXT-AWARE 4TH DOWN MODEL BACKTEST")
    logger.info("="*80)

    # Step 1: Load play-by-play data
    logger.info("\n[1/6] Loading play-by-play data...")
    try:
        # Load training data (2018-2021) and test data (2022-2023)
        train_seasons = [2018, 2019, 2020, 2021]
        test_seasons = [2022, 2023]

        logger.info(f"Loading training data: {train_seasons}")
        train_data = load_pbp_data(seasons=train_seasons)
        logger.info(f"  Loaded {len(train_data):,} plays")

        logger.info(f"Loading test data: {test_seasons}")
        test_data = load_pbp_data(seasons=test_seasons)
        logger.info(f"  Loaded {len(test_data):,} plays")

    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return

    # Step 2: Build base rate table
    logger.info("\n[2/6] Building base rate table from historical conversions...")
    try:
        base_rate_table = build_base_rate_table(train_data)
        logger.info(f"  Built table with {len(base_rate_table)} entries")

        # Show sample rates
        logger.info("  Sample base rates:")
        for yards in [1, 2, 5, 10]:
            for zone in ['red_zone', 'opp_side']:
                rate = base_rate_table.get((yards, zone))
                if rate:
                    logger.info(f"    {yards} yards, {zone}: {rate:.1%}")

    except Exception as e:
        logger.error(f"Error building base rate table: {e}")
        return

    # Step 3: Initialize ConversionModel
    logger.info("\n[3/6] Initializing ConversionModel...")
    model = ConversionModel(base_rate_table)
    logger.info(f"  Model initialized with {len(base_rate_table)} base rates")

    # Step 4: Run backtest
    logger.info("\n[4/6] Running backtest on 2022-2023 seasons...")
    logger.info("  This may take a few minutes...")

    try:
        runner = BacktestRunner(model)
        results = runner.run_backtest(test_data, seasons=test_seasons)
        logger.info(f"  Successfully processed {len(results.plays)} 4th down plays")

    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 5: Generate detailed report
    logger.info("\n[5/6] Generating detailed analysis report...")

    # Summary statistics
    logger.info("\n" + "="*80)
    logger.info("SUMMARY STATISTICS")
    logger.info("="*80)
    stats = results.summary_stats()
    logger.info(f"Total 4th down plays analyzed: {stats['total_plays']:,}")
    logger.info(f"Seasons: {', '.join(map(str, stats['seasons']))}")
    logger.info(f"Average conversion probability: {stats['avg_conversion_prob']:.1%}")
    logger.info(f"Agreement with coaches: {stats['agreement_rate']:.1%}")

    logger.info("\nOur Recommendations:")
    for decision, count in stats['recommendations'].items():
        pct = count / stats['total_plays'] * 100
        logger.info(f"  {decision}: {count:,} ({pct:.1f}%)")

    logger.info("\nActual Coach Decisions:")
    for decision, count in stats['actual_decisions'].items():
        pct = count / stats['total_plays'] * 100
        logger.info(f"  {decision}: {count:,} ({pct:.1f}%)")

    # Accuracy vs static
    logger.info("\n" + "="*80)
    logger.info("ACCURACY VS STATIC MODEL")
    logger.info("="*80)
    accuracy = results.accuracy_vs_static()
    if accuracy.get('valid_comparisons', 0) > 0:
        logger.info(f"Plays where we disagreed with static model: {accuracy['disagreements']:,}")
        logger.info(f"Valid comparisons (clear outcomes): {accuracy['valid_comparisons']:,}")
        logger.info(f"Our accuracy (on disagreements): {accuracy['our_accuracy']:.1%}")
        logger.info(f"Static accuracy (on disagreements): {accuracy['static_accuracy']:.1%}")
        logger.info(f"IMPROVEMENT: {accuracy['improvement']:+.1%}")

        if accuracy['improvement'] > 0:
            logger.info("✓ Context-aware model outperforms static model!")
        elif accuracy['improvement'] < 0:
            logger.info("✗ Static model outperforms context-aware model")
        else:
            logger.info("= Models perform equally")
    else:
        logger.info("Insufficient data for comparison (no disagreements or unclear outcomes)")

    # Value added
    logger.info("\n" + "="*80)
    logger.info("VALUE ADDED ANALYSIS")
    logger.info("="*80)
    value = results.value_added()
    if value.get('total_plays', 0) > 0:
        logger.info(f"Plays with WPA data: {value['total_plays']:,}")
        logger.info(f"\nWhen coach FOLLOWED our recommendation:")
        logger.info(f"  Count: {value['followed_count']:,}")
        logger.info(f"  Average WPA: {value['followed_avg_wpa']:+.4f}")
        logger.info(f"  Total WPA: {value['followed_sum_wpa']:+.2f}")
        logger.info(f"\nWhen coach DID NOT follow our recommendation:")
        logger.info(f"  Count: {value['not_followed_count']:,}")
        logger.info(f"  Average WPA: {value['not_followed_avg_wpa']:+.4f}")
        logger.info(f"  Total WPA: {value['not_followed_sum_wpa']:+.2f}")
        logger.info(f"\nDIFFERENCE: {value['value_difference']:+.4f} WPA per play")

        if value['value_difference'] > 0:
            logger.info("✓ Following our recommendations added value!")
        else:
            logger.info("✗ Not following our recommendations was better")
    else:
        logger.info("No WPA data available for value analysis")

    # Calibration check
    logger.info("\n" + "="*80)
    logger.info("CALIBRATION CHECK")
    logger.info("="*80)
    logger.info("(Are our predicted probabilities accurate?)")
    calibration = results.calibration_check()
    if not calibration.empty:
        logger.info("\n{:<15} {:<12} {:<12} {:<8} {:<8}".format(
            "Prob Range", "Predicted", "Actual", "Count", "Error"
        ))
        logger.info("-" * 60)
        for _, row in calibration.iterrows():
            logger.info("{:<15} {:<12.1%} {:<12.1%} {:<8} {:<8.3f}".format(
                row['prob_bin'],
                row['predicted_prob'],
                row['actual_rate'],
                int(row['count']),
                row['error']
            ))

        mean_error = calibration['error'].mean()
        logger.info(f"\nMean Absolute Error: {mean_error:.3f}")
        if mean_error < 0.05:
            logger.info("✓ Excellent calibration!")
        elif mean_error < 0.10:
            logger.info("✓ Good calibration")
        else:
            logger.info("⚠ Calibration needs improvement")
    else:
        logger.info("Insufficient data for calibration analysis")

    # Modifier impact
    logger.info("\n" + "="*80)
    logger.info("MODIFIER IMPACT ANALYSIS")
    logger.info("="*80)
    logger.info("(Which contextual factors predict success best?)")
    modifiers = results.modifier_impact()
    if not modifiers.empty:
        logger.info("\n{:<15} {:<25} {:<12} {:<10}".format(
            "Modifier", "Correlation w/ Success", "Mean Value", "Std Dev"
        ))
        logger.info("-" * 65)
        for _, row in modifiers.iterrows():
            logger.info("{:<15} {:<25} {:<12} {:<10}".format(
                row['modifier'].title(),
                f"{row['correlation']:+.3f}",
                f"{row['mean_value']:+.3f}",
                f"{row['std_value']:.3f}"
            ))

        # Highlight strongest predictor
        strongest = modifiers.iloc[0]
        logger.info(f"\n✓ Strongest predictor: {strongest['modifier'].title()} "
                   f"(correlation: {strongest['correlation']:+.3f})")
    else:
        logger.info("Insufficient data for modifier analysis")

    # Coach behavior
    logger.info("\n" + "="*80)
    logger.info("COACH BEHAVIOR ANALYSIS")
    logger.info("="*80)
    coach_behavior = results.coach_behavior_analysis()
    logger.info(f"Overall coach decisions:")
    logger.info(f"  Go for it: {coach_behavior['go_for_it_rate']:.1%}")
    logger.info(f"  Punt: {coach_behavior['punt_rate']:.1%}")
    logger.info(f"  Field goal: {coach_behavior['fg_rate']:.1%}")

    for rec in ['go_for_it', 'punt', 'field_goal']:
        key = f'when_we_recommend_{rec}'
        if key in coach_behavior:
            data = coach_behavior[key]
            logger.info(f"\nWhen we recommend {rec.replace('_', ' ')}:")
            logger.info(f"  Total recommendations: {data['count']}")
            logger.info(f"  Coach followed: {data['coach_followed_pct']:.1%}")
            logger.info(f"  Success rate when followed: {data['success_rate_when_followed']:.1%}")

    # Top 10 most impactful plays
    logger.info("\n" + "="*80)
    logger.info("TOP 10 MOST IMPACTFUL PLAYS (Where We Differed from Static)")
    logger.info("="*80)

    # Find plays where we disagreed and have WPA
    disagreements = results.plays[
        (results.plays['our_recommendation'] != results.plays['static_recommendation']) &
        (results.plays['wpa'].notna())
    ].copy()

    if len(disagreements) > 0:
        # Sort by absolute WPA
        disagreements['abs_wpa'] = disagreements['wpa'].abs()
        top_plays = disagreements.nlargest(10, 'abs_wpa')

        for idx, (_, play) in enumerate(top_plays.iterrows(), 1):
            logger.info(f"\n{idx}. {play['game_id']} - {play['posteam']}")
            logger.info(f"   Situation: {int(play['yards_to_go'])} yards to go at "
                       f"{int(play['yardline_100'])} yard line")
            logger.info(f"   Score diff: {int(play['score_differential']):+d}, "
                       f"Time: {int(play['time_remaining'])}s")
            logger.info(f"   Our rec: {play['our_recommendation']} "
                       f"(prob: {play['our_conversion_prob']:.1%})")
            logger.info(f"   Static rec: {play['static_recommendation']}")
            logger.info(f"   Coach did: {play['actual_decision']}")
            logger.info(f"   Outcome: {play['actual_outcome']}")
            logger.info(f"   WPA: {play['wpa']:+.3f}")
            logger.info(f"   Context: momentum={play['momentum_modifier']:+.3f}, "
                       f"weather={play['weather_modifier']:+.3f}, "
                       f"fatigue={play['fatigue_modifier']:+.3f}")
    else:
        logger.info("No plays with both disagreements and WPA data")

    # Step 6: Save results
    logger.info("\n[6/6] Saving results...")

    output_dir = Path(__file__).parent.parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save detailed results as JSON
    results_json = {
        'summary': stats,
        'accuracy_vs_static': accuracy,
        'value_added': value,
        'calibration': calibration.to_dict('records') if not calibration.empty else [],
        'modifier_impact': modifiers.to_dict('records') if not modifiers.empty else [],
        'coach_behavior': coach_behavior
    }

    json_path = output_dir / "backtest_results.json"
    with open(json_path, 'w') as f:
        json.dump(results_json, f, indent=2, default=str)
    logger.info(f"  Results saved to: {json_path}")

    # Save markdown report
    report_path = output_dir / "backtest_report.md"
    report = generate_report(results, str(report_path))
    logger.info(f"  Report saved to: {report_path}")

    # Save full plays DataFrame
    csv_path = output_dir / "backtest_plays.csv"
    results.plays.to_csv(csv_path, index=False)
    logger.info(f"  Play-by-play results saved to: {csv_path}")

    # Final summary
    logger.info("\n" + "="*80)
    logger.info("BACKTEST COMPLETE")
    logger.info("="*80)
    logger.info("\nKey Findings:")

    if accuracy.get('valid_comparisons', 0) > 0:
        logger.info(f"1. Accuracy improvement over static: {accuracy['improvement']:+.1%}")

    if value.get('total_plays', 0) > 0:
        logger.info(f"2. Value difference when followed: {value['value_difference']:+.4f} WPA/play")

    if not calibration.empty:
        logger.info(f"3. Mean calibration error: {calibration['error'].mean():.3f}")

    if not modifiers.empty:
        strongest = modifiers.iloc[0]
        logger.info(f"4. Strongest predictor: {strongest['modifier'].title()} "
                   f"({strongest['correlation']:+.3f})")

    logger.info(f"\nAll results saved to: {output_dir}")
    logger.info("\n✓ Backtest completed successfully!")


if __name__ == "__main__":
    main()
