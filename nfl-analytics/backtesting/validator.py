"""
Backtesting Validator

This module validates model predictions against historical outcomes to measure
improvement over static 4th down models.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# EXPECTED VALUE CALCULATIONS
# ==============================================================================

def calculate_go_for_it_ev(
    conversion_prob: float,
    yardline_100: int,
    score_diff: int,
    time_remaining: int
) -> float:
    """
    Calculate expected value of going for it on 4th down.

    Simplified EV based on field position and win probability impact.

    Args:
        conversion_prob: Probability of converting
        yardline_100: Yards to opponent's endzone
        score_diff: Score differential
        time_remaining: Seconds remaining

    Returns:
        float: Expected value (approximate WPA)
    """
    # Convert success/failure to expected WP delta
    # These are rough approximations
    if yardline_100 <= 10:
        # Red zone
        success_value = 0.08  # High value near goal line
        failure_value = -0.06
    elif yardline_100 <= 30:
        # Opponent territory
        success_value = 0.06
        failure_value = -0.04
    elif yardline_100 <= 50:
        # Midfield
        success_value = 0.04
        failure_value = -0.03
    else:
        # Own territory
        success_value = 0.03
        failure_value = -0.04

    # Adjust for game state
    if abs(score_diff) < 7 and time_remaining < 300:
        # Close game, late
        success_value *= 1.5
        failure_value *= 1.5

    ev = (conversion_prob * success_value) + ((1 - conversion_prob) * failure_value)
    return ev


def calculate_punt_ev(yardline_100: int) -> float:
    """
    Calculate expected value of punting.

    Args:
        yardline_100: Yards to opponent's endzone

    Returns:
        float: Expected value (approximate WPA)
    """
    # Very rough approximation
    # Punting from own territory is safer
    if yardline_100 >= 70:
        return 0.01  # Safe play from deep
    elif yardline_100 >= 50:
        return 0.005  # Neutral from midfield
    else:
        return -0.01  # Giving up opportunity in opponent territory


def calculate_fg_ev(yardline_100: int) -> float:
    """
    Calculate expected value of field goal attempt.

    Args:
        yardline_100: Yards to opponent's endzone

    Returns:
        float: Expected value (approximate WPA)
    """
    fg_distance = yardline_100 + 17

    # FG success probability by distance
    if fg_distance <= 30:
        success_prob = 0.95
    elif fg_distance <= 40:
        success_prob = 0.85
    elif fg_distance <= 50:
        success_prob = 0.70
    elif fg_distance <= 55:
        success_prob = 0.55
    else:
        return -100.0  # Not viable

    # EV of making vs missing
    make_value = 0.04  # 3 points worth
    miss_value = -0.02  # Turnover on downs

    ev = (success_prob * make_value) + ((1 - success_prob) * miss_value)
    return ev


# ==============================================================================
# BACKTEST RESULTS CLASS
# ==============================================================================

@dataclass
class BacktestResults:
    """Container for backtesting results and analysis."""

    plays: pd.DataFrame
    model_name: str = "Context-Aware Model"
    baseline_name: str = "Static Model"

    # Analysis caches
    _accuracy_cache: Dict = field(default_factory=dict, repr=False)
    _calibration_cache: Dict = field(default_factory=dict, repr=False)

    def accuracy_vs_static(self) -> Dict[str, float]:
        """
        Compare accuracy when our model disagreed with static model.

        Returns:
            dict: Accuracy metrics for disagreements
        """
        if 'accuracy' in self._accuracy_cache:
            return self._accuracy_cache['accuracy']

        # Find plays where we disagreed
        disagreements = self.plays[
            self.plays['our_recommendation'] != self.plays['static_recommendation']
        ].copy()

        if len(disagreements) == 0:
            logger.warning("No disagreements between models")
            return {'disagreements': 0}

        # Determine who was "right" based on actual outcome
        # "Right" = recommended action led to positive outcome
        def was_correct(row):
            actual = row['actual_decision']
            outcome = row['actual_outcome']

            # Check if recommendation matched actual decision
            our_match = row['our_recommendation'] == actual
            static_match = row['static_recommendation'] == actual

            # Determine if outcome was positive
            if outcome in ['converted', 'fg_made']:
                positive_outcome = True
            elif outcome in ['failed', 'fg_missed']:
                positive_outcome = False
            else:
                return None, None  # Unclear (punt)

            # We were "right" if we recommended action that led to positive outcome
            # OR if we recommended against action that led to negative outcome
            our_correct = (our_match and positive_outcome) or (not our_match and not positive_outcome)
            static_correct = (static_match and positive_outcome) or (not static_match and not positive_outcome)

            return our_correct, static_correct

        disagreements[['our_correct', 'static_correct']] = disagreements.apply(
            lambda row: pd.Series(was_correct(row)), axis=1
        )

        # Remove unclear cases
        valid = disagreements.dropna(subset=['our_correct', 'static_correct'])

        results = {
            'disagreements': len(disagreements),
            'valid_comparisons': len(valid),
            'our_accuracy': valid['our_correct'].mean() if len(valid) > 0 else 0.0,
            'static_accuracy': valid['static_correct'].mean() if len(valid) > 0 else 0.0,
            'improvement': (valid['our_correct'].mean() - valid['static_correct'].mean()) if len(valid) > 0 else 0.0
        }

        self._accuracy_cache['accuracy'] = results
        return results

    def value_added(self) -> Dict[str, float]:
        """
        Calculate WPA for plays where coach followed our recommendation vs didn't.

        Returns:
            dict: Value added metrics
        """
        # Filter to plays with WPA data
        with_wpa = self.plays[self.plays['wpa'].notna()].copy()

        if len(with_wpa) == 0:
            logger.warning("No WPA data available")
            return {'total_plays': 0}

        # Plays where coach followed our recommendation
        followed = with_wpa[
            with_wpa['our_recommendation'] == with_wpa['actual_decision']
        ]

        # Plays where coach did NOT follow our recommendation
        not_followed = with_wpa[
            with_wpa['our_recommendation'] != with_wpa['actual_decision']
        ]

        results = {
            'total_plays': len(with_wpa),
            'followed_count': len(followed),
            'not_followed_count': len(not_followed),
            'followed_avg_wpa': followed['wpa'].mean() if len(followed) > 0 else 0.0,
            'not_followed_avg_wpa': not_followed['wpa'].mean() if len(not_followed) > 0 else 0.0,
            'value_difference': (followed['wpa'].mean() - not_followed['wpa'].mean()) if len(followed) > 0 and len(not_followed) > 0 else 0.0,
            'followed_sum_wpa': followed['wpa'].sum() if len(followed) > 0 else 0.0,
            'not_followed_sum_wpa': not_followed['wpa'].sum() if len(not_followed) > 0 else 0.0
        }

        return results

    def calibration_check(self, bins: int = 10) -> pd.DataFrame:
        """
        Check if predicted probabilities are well-calibrated.

        Predicted 60% should convert ~60% of the time.

        Args:
            bins: Number of probability bins

        Returns:
            DataFrame: Calibration by bin
        """
        if 'calibration' in self._calibration_cache:
            return self._calibration_cache['calibration']

        # Filter to go-for-it decisions
        go_plays = self.plays[
            self.plays['our_recommendation'] == 'go_for_it'
        ].copy()

        if len(go_plays) == 0:
            logger.warning("No go-for-it recommendations")
            return pd.DataFrame()

        # Create probability bins
        go_plays['prob_bin'] = pd.cut(
            go_plays['our_conversion_prob'],
            bins=bins,
            labels=[f"{i*10}-{(i+1)*10}%" for i in range(bins)]
        )

        # Calculate actual conversion rate per bin
        calibration = go_plays.groupby('prob_bin', observed=True).agg({
            'our_conversion_prob': ['mean', 'count'],
            'actual_outcome': lambda x: (x == 'converted').mean()
        }).round(3)

        calibration.columns = ['predicted_prob', 'count', 'actual_rate']
        calibration = calibration.reset_index()

        # Calculate calibration error
        calibration['error'] = (calibration['predicted_prob'] - calibration['actual_rate']).abs()

        self._calibration_cache['calibration'] = calibration
        return calibration

    def modifier_impact(self) -> pd.DataFrame:
        """
        Analyze which modifiers had biggest predictive value.

        Returns:
            DataFrame: Modifier correlations with success
        """
        # Filter to go-for-it decisions with outcomes
        go_plays = self.plays[
            (self.plays['our_recommendation'] == 'go_for_it') &
            (self.plays['actual_decision'] == 'go_for_it')
        ].copy()

        if len(go_plays) == 0:
            logger.warning("No go-for-it plays to analyze")
            return pd.DataFrame()

        # Create binary success variable
        go_plays['success'] = (go_plays['actual_outcome'] == 'converted').astype(int)

        # Calculate correlations
        modifiers = ['momentum_modifier', 'weather_modifier', 'fatigue_modifier',
                    'injury_modifier', 'crowd_modifier']

        correlations = []
        for mod in modifiers:
            if mod in go_plays.columns:
                corr = go_plays[mod].corr(go_plays['success'])
                correlations.append({
                    'modifier': mod.replace('_modifier', ''),
                    'correlation': corr,
                    'mean_value': go_plays[mod].mean(),
                    'std_value': go_plays[mod].std()
                })

        result = pd.DataFrame(correlations).sort_values('correlation', ascending=False, key=abs)
        return result

    def coach_behavior_analysis(self) -> Dict[str, any]:
        """
        Analyze coach decision patterns.

        Returns:
            dict: Coach behavior metrics
        """
        results = {
            'total_plays': len(self.plays),
            'go_for_it_rate': (self.plays['actual_decision'] == 'go_for_it').mean(),
            'punt_rate': (self.plays['actual_decision'] == 'punt').mean(),
            'fg_rate': (self.plays['actual_decision'] == 'field_goal').mean(),
        }

        # Analyze by our recommendation
        for rec in ['go_for_it', 'punt', 'field_goal']:
            subset = self.plays[self.plays['our_recommendation'] == rec]
            if len(subset) > 0:
                results[f'when_we_recommend_{rec}'] = {
                    'count': len(subset),
                    'coach_followed_pct': (subset['actual_decision'] == rec).mean(),
                    'success_rate_when_followed': (
                        subset[subset['actual_decision'] == rec]['actual_outcome'].isin(['converted', 'fg_made']).mean()
                        if len(subset[subset['actual_decision'] == rec]) > 0 else 0.0
                    )
                }

        return results

    def summary_stats(self) -> Dict[str, any]:
        """
        Get summary statistics.

        Returns:
            dict: Summary statistics
        """
        return {
            'total_plays': len(self.plays),
            'seasons': sorted(self.plays['season'].unique().tolist()) if 'season' in self.plays.columns else [],
            'avg_conversion_prob': self.plays['our_conversion_prob'].mean(),
            'recommendations': self.plays['our_recommendation'].value_counts().to_dict(),
            'actual_decisions': self.plays['actual_decision'].value_counts().to_dict(),
            'agreement_rate': (self.plays['our_recommendation'] == self.plays['actual_decision']).mean()
        }


# ==============================================================================
# BACKTEST RUNNER CLASS
# ==============================================================================

class BacktestRunner:
    """
    Main backtesting engine that compares context-aware model against static baseline.
    """

    def __init__(self, conversion_model):
        """
        Initialize backtest runner.

        Args:
            conversion_model: Trained ConversionModel instance
        """
        self.model = conversion_model
        logger.info("Initialized BacktestRunner")

    def classify_actual_decision(self, row: pd.Series) -> str:
        """
        Classify what the coach actually did.

        Args:
            row: Play data row

        Returns:
            str: 'go_for_it', 'punt', 'field_goal', or 'unknown'
        """
        play_type = row.get('play_type', '')

        if play_type == 'punt':
            return 'punt'
        elif play_type == 'field_goal':
            return 'field_goal'
        elif play_type in ['run', 'pass']:
            return 'go_for_it'
        else:
            return 'unknown'

    def classify_actual_outcome(self, row: pd.Series) -> str:
        """
        Classify the actual outcome of the play.

        Args:
            row: Play data row

        Returns:
            str: Outcome classification
        """
        play_type = row.get('play_type', '')
        decision = self.classify_actual_decision(row)

        if decision == 'go_for_it':
            # Check if converted
            first_down = row.get('first_down_rush', 0) or row.get('first_down_pass', 0)
            touchdown = row.get('touchdown', 0)

            if first_down == 1 or touchdown == 1:
                return 'converted'
            else:
                return 'failed'

        elif decision == 'punt':
            return 'punt'

        elif decision == 'field_goal':
            fg_result = row.get('field_goal_result', '')
            if fg_result == 'made':
                return 'fg_made'
            else:
                return 'fg_missed'

        return 'unknown'

    def get_static_recommendation(self, row: pd.Series) -> str:
        """
        Get static model recommendation (simplified heuristic).

        In real implementation, would use nflfastR's 4th down model.

        Args:
            row: Play data row

        Returns:
            str: Static recommendation
        """
        ydstogo = row.get('ydstogo', 10)
        yardline_100 = row.get('yardline_100', 50)
        score_diff = row.get('score_differential', 0)

        # Simple heuristic (placeholder for real static model)
        fg_distance = yardline_100 + 17

        # 4th and short in opponent territory
        if ydstogo <= 2 and yardline_100 <= 35:
            return 'go_for_it'

        # Field goal range
        if yardline_100 <= 30 and fg_distance <= 50:
            return 'field_goal'

        # Desperate situation
        if score_diff < -7 and yardline_100 <= 50:
            return 'go_for_it'

        # Default: punt
        return 'punt'

    def process_play(self, row: pd.Series) -> Dict:
        """
        Process a single 4th down play.

        Args:
            row: Play data row

        Returns:
            dict: Processed play data
        """
        # Extract basic info
        yards_to_go = row.get('ydstogo', 10)
        yardline_100 = row.get('yardline_100', 50)
        score_diff = row.get('score_differential', 0)
        time_remaining = row.get('game_seconds_remaining', 1800)

        # Get context factors (if available)
        momentum_score = row.get('momentum_score', 50.0)
        weather_modifier = row.get('weather_modifier', 1.0)
        fatigue_modifier = row.get('fatigue_modifier', 1.0)
        injury_modifier = row.get('injury_modifier', 1.0)
        crowd_modifier = row.get('crowd_modifier', 1.0)

        # Get our model's prediction
        prediction = self.model.predict(
            yards_to_go=yards_to_go,
            yardline_100=yardline_100,
            momentum_score=momentum_score,
            weather_modifier=weather_modifier,
            fatigue_modifier=fatigue_modifier,
            injury_modifier=injury_modifier,
            crowd_modifier=crowd_modifier
        )

        conversion_prob = prediction['final_probability']

        # Calculate EV for each option
        go_ev = calculate_go_for_it_ev(conversion_prob, yardline_100, score_diff, time_remaining)
        punt_ev = calculate_punt_ev(yardline_100)
        fg_ev = calculate_fg_ev(yardline_100)

        # Determine our recommendation (highest EV)
        options = {
            'go_for_it': go_ev,
            'punt': punt_ev,
            'field_goal': fg_ev if fg_ev > -50 else -100
        }
        our_recommendation = max(options, key=options.get)

        # Get static recommendation
        static_recommendation = self.get_static_recommendation(row)

        # Get actual decision and outcome
        actual_decision = self.classify_actual_decision(row)
        actual_outcome = self.classify_actual_outcome(row)

        return {
            'game_id': row.get('game_id', ''),
            'season': row.get('season', 0),
            'week': row.get('week', 0),
            'posteam': row.get('posteam', ''),
            'yards_to_go': yards_to_go,
            'yardline_100': yardline_100,
            'score_differential': score_diff,
            'time_remaining': time_remaining,
            'our_recommendation': our_recommendation,
            'our_conversion_prob': conversion_prob,
            'go_ev': go_ev,
            'punt_ev': punt_ev,
            'fg_ev': fg_ev,
            'static_recommendation': static_recommendation,
            'actual_decision': actual_decision,
            'actual_outcome': actual_outcome,
            'momentum_modifier': prediction['momentum_modifier'],
            'weather_modifier': prediction['weather_modifier'],
            'fatigue_modifier': prediction['fatigue_modifier'],
            'injury_modifier': prediction['injury_modifier'],
            'crowd_modifier': prediction['crowd_modifier'],
            'total_modifier': prediction['total_modifier'],
            'wpa': row.get('wpa', np.nan)
        }

    def run_backtest(
        self,
        play_by_play_df: pd.DataFrame,
        seasons: Optional[List[int]] = None
    ) -> BacktestResults:
        """
        Run backtest on historical data.

        Args:
            play_by_play_df: Play-by-play data
            seasons: Seasons to test (None = all)

        Returns:
            BacktestResults: Results object
        """
        logger.info("="*60)
        logger.info("RUNNING BACKTEST")
        logger.info("="*60)

        # Filter to 4th downs
        fourth_downs = play_by_play_df[play_by_play_df['down'] == 4].copy()

        if seasons:
            fourth_downs = fourth_downs[fourth_downs['season'].isin(seasons)]

        logger.info(f"Processing {len(fourth_downs)} 4th down plays from seasons {seasons or 'all'}")

        # Process each play
        results = []
        for idx, row in fourth_downs.iterrows():
            try:
                result = self.process_play(row)
                results.append(result)
            except Exception as e:
                logger.warning(f"Error processing play {idx}: {e}")
                continue

        # Create results DataFrame
        results_df = pd.DataFrame(results)

        logger.info(f"Successfully processed {len(results_df)} plays")

        return BacktestResults(plays=results_df)


# ==============================================================================
# REPORT GENERATION
# ==============================================================================

def generate_report(results: BacktestResults, output_path: Optional[str] = None) -> str:
    """
    Generate comprehensive markdown report of backtest results.

    Args:
        results: BacktestResults object
        output_path: Optional path to save report

    Returns:
        str: Markdown report
    """
    report_lines = []

    # Header
    report_lines.append("# 4th Down Decision Model Backtest Report")
    report_lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"\n**Model:** {results.model_name} vs {results.baseline_name}")

    # Summary statistics
    report_lines.append("\n## Summary Statistics\n")
    stats = results.summary_stats()
    report_lines.append(f"- **Total Plays Analyzed:** {stats['total_plays']:,}")
    report_lines.append(f"- **Seasons:** {', '.join(map(str, stats['seasons']))}")
    report_lines.append(f"- **Average Conversion Probability:** {stats['avg_conversion_prob']:.1%}")
    report_lines.append(f"- **Agreement with Coaches:** {stats['agreement_rate']:.1%}")

    # Recommendations breakdown
    report_lines.append("\n### Our Recommendations")
    for decision, count in stats['recommendations'].items():
        pct = count / stats['total_plays'] * 100
        report_lines.append(f"- {decision}: {count:,} ({pct:.1f}%)")

    report_lines.append("\n### Actual Coach Decisions")
    for decision, count in stats['actual_decisions'].items():
        pct = count / stats['total_plays'] * 100
        report_lines.append(f"- {decision}: {count:,} ({pct:.1f}%)")

    # Accuracy vs static
    report_lines.append("\n## Accuracy vs Static Model\n")
    accuracy = results.accuracy_vs_static()
    if accuracy.get('valid_comparisons', 0) > 0:
        report_lines.append(f"- **Plays where we disagreed:** {accuracy['disagreements']:,}")
        report_lines.append(f"- **Valid comparisons:** {accuracy['valid_comparisons']:,}")
        report_lines.append(f"- **Our accuracy (on disagreements):** {accuracy['our_accuracy']:.1%}")
        report_lines.append(f"- **Static accuracy (on disagreements):** {accuracy['static_accuracy']:.1%}")
        report_lines.append(f"- **Improvement:** {accuracy['improvement']:+.1%}")
    else:
        report_lines.append("*Insufficient data for comparison*")

    # Value added
    report_lines.append("\n## Value Added Analysis\n")
    value = results.value_added()
    if value.get('total_plays', 0) > 0:
        report_lines.append(f"- **Plays where coach followed our rec:** {value['followed_count']:,}")
        report_lines.append(f"- **Average WPA when followed:** {value['followed_avg_wpa']:+.3f}")
        report_lines.append(f"- **Plays where coach didn't follow:** {value['not_followed_count']:,}")
        report_lines.append(f"- **Average WPA when not followed:** {value['not_followed_avg_wpa']:+.3f}")
        report_lines.append(f"- **Difference:** {value['value_difference']:+.3f}")
        report_lines.append(f"- **Total WPA gained (followed):** {value['followed_sum_wpa']:+.2f}")
        report_lines.append(f"- **Total WPA lost (not followed):** {value['not_followed_sum_wpa']:+.2f}")
    else:
        report_lines.append("*No WPA data available*")

    # Calibration
    report_lines.append("\n## Calibration Check\n")
    calibration = results.calibration_check()
    if not calibration.empty:
        report_lines.append("| Probability Range | Predicted | Actual | Count | Error |")
        report_lines.append("|------------------|-----------|---------|-------|-------|")
        for _, row in calibration.iterrows():
            report_lines.append(
                f"| {row['prob_bin']} | {row['predicted_prob']:.1%} | {row['actual_rate']:.1%} | "
                f"{int(row['count'])} | {row['error']:.3f} |"
            )
        report_lines.append(f"\n**Mean Absolute Error:** {calibration['error'].mean():.3f}")
    else:
        report_lines.append("*Insufficient data for calibration analysis*")

    # Modifier impact
    report_lines.append("\n## Modifier Impact Analysis\n")
    modifiers = results.modifier_impact()
    if not modifiers.empty:
        report_lines.append("| Modifier | Correlation with Success | Mean Value | Std Dev |")
        report_lines.append("|----------|-------------------------|------------|---------|")
        for _, row in modifiers.iterrows():
            report_lines.append(
                f"| {row['modifier'].title()} | {row['correlation']:+.3f} | "
                f"{row['mean_value']:+.3f} | {row['std_value']:.3f} |"
            )
    else:
        report_lines.append("*Insufficient data for modifier analysis*")

    # Coach behavior
    report_lines.append("\n## Coach Behavior Analysis\n")
    coach_behavior = results.coach_behavior_analysis()
    report_lines.append(f"- **Overall go-for-it rate:** {coach_behavior['go_for_it_rate']:.1%}")
    report_lines.append(f"- **Overall punt rate:** {coach_behavior['punt_rate']:.1%}")
    report_lines.append(f"- **Overall FG rate:** {coach_behavior['fg_rate']:.1%}")

    for rec in ['go_for_it', 'punt', 'field_goal']:
        key = f'when_we_recommend_{rec}'
        if key in coach_behavior:
            data = coach_behavior[key]
            report_lines.append(f"\n### When We Recommend {rec.replace('_', ' ').title()}")
            report_lines.append(f"- Count: {data['count']}")
            report_lines.append(f"- Coach followed: {data['coach_followed_pct']:.1%}")
            report_lines.append(f"- Success rate when followed: {data['success_rate_when_followed']:.1%}")

    # Combine report
    report = "\n".join(report_lines)

    # Save if path provided
    if output_path:
        Path(output_path).write_text(report)
        logger.info(f"Report saved to {output_path}")

    return report


# ==============================================================================
# CONVENIENCE FUNCTION
# ==============================================================================

def run_backtest(
    conversion_model,
    play_by_play_df: pd.DataFrame,
    seasons: Optional[List[int]] = None,
    save_report: bool = True
) -> BacktestResults:
    """
    Convenience function to run backtest.

    Args:
        conversion_model: Trained ConversionModel
        play_by_play_df: Play-by-play data
        seasons: Seasons to test (default: [2022, 2023])
        save_report: Whether to generate and save report

    Returns:
        BacktestResults: Results object
    """
    if seasons is None:
        seasons = [2022, 2023]

    runner = BacktestRunner(conversion_model)
    results = runner.run_backtest(play_by_play_df, seasons)

    if save_report:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"backtest_report_{timestamp}.md"
        generate_report(results, report_path)
        logger.info(f"Report generated: {report_path}")

    return results


# ==============================================================================
# TESTING
# ==============================================================================

if __name__ == "__main__":
    """
    Test backtesting framework.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from ingestion.play_by_play import load_pbp_data
    from models import ConversionModel, build_base_rate_table

    logger.info("="*60)
    logger.info("BACKTESTING FRAMEWORK TEST")
    logger.info("="*60)

    # Load data
    logger.info("Loading data...")
    pbp = load_pbp_data(seasons=[2022, 2023])

    # Build and train model
    logger.info("Training model...")
    base_rate_table = build_base_rate_table(pbp)
    model = ConversionModel(base_rate_table)

    # Run backtest
    logger.info("\nRunning backtest...")
    results = run_backtest(model, pbp, seasons=[2023], save_report=True)

    # Display results
    logger.info("\n" + "="*60)
    logger.info("BACKTEST RESULTS SUMMARY")
    logger.info("="*60)

    stats = results.summary_stats()
    logger.info(f"\nTotal plays: {stats['total_plays']:,}")
    logger.info(f"Agreement rate: {stats['agreement_rate']:.1%}")

    accuracy = results.accuracy_vs_static()
    if accuracy.get('valid_comparisons', 0) > 0:
        logger.info(f"\nDisagreements: {accuracy['disagreements']}")
        logger.info(f"Our accuracy: {accuracy['our_accuracy']:.1%}")
        logger.info(f"Static accuracy: {accuracy['static_accuracy']:.1%}")
        logger.info(f"Improvement: {accuracy['improvement']:+.1%}")

    value = results.value_added()
    if value.get('total_plays', 0) > 0:
        logger.info(f"\nValue difference: {value['value_difference']:+.3f} WPA")
