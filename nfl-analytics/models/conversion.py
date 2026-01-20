"""
Final Conversion Probability Calculator

This module integrates all contextual factors (momentum, weather, fatigue,
injuries, crowd noise) to produce a final 4th down conversion probability.
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# FIELD POSITION ZONES
# ==============================================================================

def get_field_position_zone(yardline_100: int) -> str:
    """
    Get field position zone from yards to endzone.

    Args:
        yardline_100: Yards to opponent's endzone (0-100)

    Returns:
        str: Zone identifier
    """
    if yardline_100 >= 80:
        return 'own_territory'      # Own 1-20 yard line
    elif yardline_100 >= 50:
        return 'own_side'            # Own 21-50
    elif yardline_100 >= 21:
        return 'opp_side'            # Opp 49-21
    else:
        return 'red_zone'            # Red zone (opp 20-1)


# ==============================================================================
# BASE RATE TABLE BUILDER
# ==============================================================================

def build_base_rate_table(play_by_play_df: pd.DataFrame) -> Dict[Tuple[int, str], float]:
    """
    Build base conversion rate lookup table from historical data.

    Args:
        play_by_play_df: DataFrame with 4th down plays

    Returns:
        dict: (yards_to_go, field_zone) -> conversion_rate
    """
    logger.info("Building base rate table from historical data...")

    # Filter to 4th down attempts (not punts/FGs)
    fourth_downs = play_by_play_df[play_by_play_df['down'] == 4].copy()

    # Filter to go-for-it attempts
    go_for_it = fourth_downs[
        (fourth_downs['play_type'].isin(['run', 'pass'])) &
        (~fourth_downs['play_type'].isin(['punt', 'field_goal']))
    ].copy()

    if len(go_for_it) == 0:
        logger.warning("No 4th down go-for-it attempts found")
        return {}

    # Categorize yards to go (1-10+)
    def categorize_ydstogo(yards):
        if pd.isna(yards):
            return 10
        if yards >= 10:
            return 10
        return int(yards)

    go_for_it['ydstogo_cat'] = go_for_it['ydstogo'].apply(categorize_ydstogo)

    # Get field position zone
    go_for_it['field_zone'] = go_for_it['yardline_100'].apply(
        lambda x: get_field_position_zone(x) if not pd.isna(x) else 'own_side'
    )

    # Determine conversion (first down or touchdown)
    def is_converted(row):
        if pd.isna(row.get('first_down_rush')) and pd.isna(row.get('first_down_pass')):
            # Fallback: check if gained enough yards
            yards_gained = row.get('yards_gained', 0)
            ydstogo = row.get('ydstogo', 10)
            return yards_gained >= ydstogo
        return row.get('first_down_rush', 0) == 1 or row.get('first_down_pass', 0) == 1

    go_for_it['converted'] = go_for_it.apply(is_converted, axis=1)

    # Build rate table
    base_rate_table = {}

    for yards in range(1, 11):
        for zone in ['own_territory', 'own_side', 'opp_side', 'red_zone']:
            subset = go_for_it[
                (go_for_it['ydstogo_cat'] == yards) &
                (go_for_it['field_zone'] == zone)
            ]

            if len(subset) >= 10:  # Minimum sample size
                conversion_rate = subset['converted'].mean()
                base_rate_table[(yards, zone)] = conversion_rate
                logger.debug(f"{yards} yards, {zone}: {conversion_rate:.3f} (n={len(subset)})")

    logger.info(f"Built base rate table with {len(base_rate_table)} entries")
    return base_rate_table


def get_base_rate(
    yards_to_go: int,
    yardline_100: int,
    base_rate_table: Dict[Tuple[int, str], float]
) -> float:
    """
    Get base conversion rate from table.

    Args:
        yards_to_go: Yards needed for first down
        yardline_100: Yards to opponent's endzone
        base_rate_table: Base rate lookup table

    Returns:
        float: Base conversion rate
    """
    # Categorize yards to go
    yards_cat = min(10, max(1, int(yards_to_go))) if not pd.isna(yards_to_go) else 10

    # Get field zone
    field_zone = get_field_position_zone(yardline_100)

    # Lookup base rate
    key = (yards_cat, field_zone)
    base_rate = base_rate_table.get(key)

    if base_rate is None:
        # Fallback: try same yards, different zone
        for zone in ['red_zone', 'opp_side', 'own_side', 'own_territory']:
            fallback_key = (yards_cat, zone)
            if fallback_key in base_rate_table:
                base_rate = base_rate_table[fallback_key]
                logger.debug(f"Using fallback zone {zone} for {yards_cat} yards")
                break

    if base_rate is None:
        # Ultimate fallback: overall average
        if base_rate_table:
            base_rate = np.mean(list(base_rate_table.values()))
            logger.warning(f"Using overall average base rate: {base_rate:.3f}")
        else:
            base_rate = 0.50  # Default 50%
            logger.warning("No base rate data available, using 50%")

    return base_rate


# ==============================================================================
# MODIFIER CALCULATIONS
# ==============================================================================

def calculate_momentum_modifier(momentum_score: float) -> float:
    """
    Convert momentum score to probability modifier.

    Args:
        momentum_score: Momentum score (0-100)

    Returns:
        float: Modifier (e.g., 0.04 for +4%)
    """
    if pd.isna(momentum_score):
        return 0.0

    # (momentum - 50) / 500
    # momentum 70 = +4%, momentum 30 = -4%
    modifier = (momentum_score - 50.0) / 500.0

    return modifier


def combine_modifiers(
    momentum_score: float = 50.0,
    weather_modifier: float = 1.0,
    fatigue_modifier: float = 1.0,
    injury_modifier: float = 1.0,
    crowd_modifier: float = 1.0
) -> Dict[str, float]:
    """
    Combine all modifiers into impact percentages.

    Args:
        momentum_score: Momentum score (0-100)
        weather_modifier: Weather multiplier (1.0 = no impact)
        fatigue_modifier: Fatigue multiplier (1.0 = no impact)
        injury_modifier: Injury multiplier (1.0 = no impact)
        crowd_modifier: Crowd noise multiplier (1.0 = no impact)

    Returns:
        dict: Individual modifiers as percentages
    """
    # Convert momentum score to modifier
    momentum_mod = calculate_momentum_modifier(momentum_score)

    # Convert multipliers to additive modifiers
    weather_mod = weather_modifier - 1.0
    fatigue_mod = fatigue_modifier - 1.0
    injury_mod = injury_modifier - 1.0
    crowd_mod = crowd_modifier - 1.0

    return {
        'momentum': momentum_mod,
        'weather': weather_mod,
        'fatigue': fatigue_mod,
        'injury': injury_mod,
        'crowd': crowd_mod
    }


# ==============================================================================
# CONFIDENCE SCORING
# ==============================================================================

def calculate_confidence(
    base_rate: float,
    sample_size: int,
    modifier_magnitude: float
) -> str:
    """
    Calculate confidence level for prediction.

    Args:
        base_rate: Base conversion rate
        sample_size: Sample size for base rate (if available)
        modifier_magnitude: Total modifier magnitude

    Returns:
        str: 'high', 'medium', or 'low'
    """
    # Start with medium confidence
    confidence_score = 50

    # Adjust based on base rate extremes (more confident at extremes)
    if base_rate < 0.2 or base_rate > 0.8:
        confidence_score += 20

    # Adjust based on sample size (if provided)
    if sample_size > 0:
        if sample_size >= 50:
            confidence_score += 20
        elif sample_size >= 20:
            confidence_score += 10
        else:
            confidence_score -= 10

    # Adjust based on modifier magnitude
    # Large modifiers mean more uncertainty
    if abs(modifier_magnitude) > 0.15:
        confidence_score -= 20
    elif abs(modifier_magnitude) > 0.10:
        confidence_score -= 10

    # Convert to category
    if confidence_score >= 70:
        return 'high'
    elif confidence_score >= 40:
        return 'medium'
    else:
        return 'low'


# ==============================================================================
# MAIN CONVERSION PROBABILITY CALCULATOR
# ==============================================================================

def calculate_conversion_probability(
    yards_to_go: int,
    yardline_100: int,
    base_rate_table: Dict[Tuple[int, str], float],
    momentum_score: float = 50.0,
    weather_modifier: float = 1.0,
    fatigue_modifier: float = 1.0,
    injury_modifier: float = 1.0,
    crowd_modifier: float = 1.0,
    sample_size: int = 0
) -> Dict[str, float]:
    """
    Calculate final 4th down conversion probability with all modifiers.

    Args:
        yards_to_go: Yards needed for first down
        yardline_100: Yards to opponent's endzone
        base_rate_table: Base rate lookup table
        momentum_score: Momentum score (0-100)
        weather_modifier: Weather multiplier
        fatigue_modifier: Fatigue multiplier
        injury_modifier: Injury multiplier
        crowd_modifier: Crowd noise multiplier
        sample_size: Sample size for base rate (optional)

    Returns:
        dict: {
            'base_rate': float,
            'momentum_modifier': float,
            'weather_modifier': float,
            'fatigue_modifier': float,
            'injury_modifier': float,
            'crowd_modifier': float,
            'total_modifier': float,
            'final_probability': float,
            'confidence': str
        }
    """
    # Get base rate
    base_rate = get_base_rate(yards_to_go, yardline_100, base_rate_table)

    # Calculate individual modifiers
    modifiers = combine_modifiers(
        momentum_score=momentum_score,
        weather_modifier=weather_modifier,
        fatigue_modifier=fatigue_modifier,
        injury_modifier=injury_modifier,
        crowd_modifier=crowd_modifier
    )

    # Sum modifiers
    total_modifier = sum(modifiers.values())

    # Apply formula: BASE_RATE * (1 + sum of modifiers)
    final_probability = base_rate * (1.0 + total_modifier)

    # Clamp between 0.05 and 0.95
    final_probability = max(0.05, min(0.95, final_probability))

    # Calculate confidence
    confidence = calculate_confidence(base_rate, sample_size, total_modifier)

    logger.info(f"Conversion probability: base={base_rate:.3f}, "
               f"modifiers={total_modifier:+.3f}, final={final_probability:.3f}, "
               f"confidence={confidence}")

    return {
        'base_rate': base_rate,
        'momentum_modifier': modifiers['momentum'],
        'weather_modifier': modifiers['weather'],
        'fatigue_modifier': modifiers['fatigue'],
        'injury_modifier': modifiers['injury'],
        'crowd_modifier': modifiers['crowd'],
        'total_modifier': total_modifier,
        'final_probability': final_probability,
        'confidence': confidence
    }


# ==============================================================================
# CONVERSION MODEL CLASS
# ==============================================================================

class ConversionModel:
    """
    Main conversion probability model that integrates all contextual factors.
    """

    def __init__(self, base_rate_table: Optional[Dict] = None):
        """
        Initialize conversion model.

        Args:
            base_rate_table: Pre-built base rate table (optional)
        """
        self.base_rate_table = base_rate_table or {}
        logger.info(f"Initialized ConversionModel with {len(self.base_rate_table)} base rates")

    def load_base_rates_from_data(self, play_by_play_df: pd.DataFrame):
        """
        Build base rate table from play-by-play data.

        Args:
            play_by_play_df: DataFrame with 4th down plays
        """
        self.base_rate_table = build_base_rate_table(play_by_play_df)
        logger.info(f"Loaded {len(self.base_rate_table)} base rates from data")

    def save_base_rates(self, filepath: str):
        """
        Save base rate table to disk.

        Args:
            filepath: Path to save pickle file
        """
        with open(filepath, 'wb') as f:
            pickle.dump(self.base_rate_table, f)
        logger.info(f"Saved base rates to {filepath}")

    def load_base_rates(self, filepath: str):
        """
        Load base rate table from disk.

        Args:
            filepath: Path to pickle file
        """
        with open(filepath, 'rb') as f:
            self.base_rate_table = pickle.load(f)
        logger.info(f"Loaded {len(self.base_rate_table)} base rates from {filepath}")

    def predict(
        self,
        yards_to_go: int,
        yardline_100: int,
        momentum_score: float = 50.0,
        weather_modifier: float = 1.0,
        fatigue_modifier: float = 1.0,
        injury_modifier: float = 1.0,
        crowd_modifier: float = 1.0
    ) -> Dict[str, float]:
        """
        Predict conversion probability for a 4th down situation.

        Args:
            yards_to_go: Yards needed for first down
            yardline_100: Yards to opponent's endzone
            momentum_score: Momentum score (0-100)
            weather_modifier: Weather multiplier
            fatigue_modifier: Fatigue multiplier
            injury_modifier: Injury multiplier
            crowd_modifier: Crowd noise multiplier

        Returns:
            dict: Prediction with all components
        """
        if not self.base_rate_table:
            logger.warning("No base rate table loaded, using defaults")

        return calculate_conversion_probability(
            yards_to_go=yards_to_go,
            yardline_100=yardline_100,
            base_rate_table=self.base_rate_table,
            momentum_score=momentum_score,
            weather_modifier=weather_modifier,
            fatigue_modifier=fatigue_modifier,
            injury_modifier=injury_modifier,
            crowd_modifier=crowd_modifier
        )

    def predict_from_context(
        self,
        game_context: Dict,
        momentum_score: Optional[float] = None,
        weather_modifier: Optional[float] = None,
        fatigue_modifier: Optional[float] = None,
        injury_modifier: Optional[float] = None,
        crowd_modifier: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Predict from game context dictionary.

        Args:
            game_context: Dictionary with game state
            momentum_score: Override momentum (optional)
            weather_modifier: Override weather (optional)
            fatigue_modifier: Override fatigue (optional)
            injury_modifier: Override injury (optional)
            crowd_modifier: Override crowd (optional)

        Returns:
            dict: Prediction with all components
        """
        # Extract from context
        yards_to_go = game_context.get('ydstogo', 10)
        yardline_100 = game_context.get('yardline_100', 50)

        # Use provided modifiers or extract from context
        momentum = momentum_score if momentum_score is not None else game_context.get('momentum_score', 50.0)
        weather = weather_modifier if weather_modifier is not None else game_context.get('weather_modifier', 1.0)
        fatigue = fatigue_modifier if fatigue_modifier is not None else game_context.get('fatigue_modifier', 1.0)
        injury = injury_modifier if injury_modifier is not None else game_context.get('injury_modifier', 1.0)
        crowd = crowd_modifier if crowd_modifier is not None else game_context.get('crowd_modifier', 1.0)

        return self.predict(
            yards_to_go=yards_to_go,
            yardline_100=yardline_100,
            momentum_score=momentum,
            weather_modifier=weather,
            fatigue_modifier=fatigue,
            injury_modifier=injury,
            crowd_modifier=crowd
        )


# ==============================================================================
# DECISION RECOMMENDATION
# ==============================================================================

def recommend_decision(
    conversion_prob: float,
    field_position: int,
    score_diff: int,
    time_remaining: int,
    yards_to_go: int
) -> Dict[str, any]:
    """
    Recommend go/punt/field goal based on all factors.

    Args:
        conversion_prob: Calculated conversion probability
        field_position: Yards to opponent's endzone (yardline_100)
        score_diff: Point differential (positive = winning)
        time_remaining: Seconds remaining in game
        yards_to_go: Yards needed for first down

    Returns:
        dict: {
            'decision': str ('go_for_it', 'punt', 'field_goal'),
            'confidence': str ('high', 'medium', 'low'),
            'reasoning': str,
            'alternative': str (optional)
        }
    """
    # Determine FG viability
    fg_distance = field_position + 17  # Add endzone and snap distance
    fg_viable = fg_distance <= 55 and field_position <= 40

    # Situational factors
    is_fourth_quarter = time_remaining <= 900
    is_two_minute = time_remaining <= 120
    is_desperate = abs(score_diff) >= 10 and is_fourth_quarter
    is_short_yardage = yards_to_go <= 2

    # Base recommendation thresholds
    go_threshold = 0.45  # Base threshold to go for it

    # Adjust threshold based on situation
    if is_desperate and score_diff < 0:
        go_threshold = 0.35  # More aggressive when trailing
    elif is_two_minute and score_diff < 0:
        go_threshold = 0.40
    elif is_short_yardage:
        go_threshold = 0.50  # More conservative on short yardage

    # Make decision
    if conversion_prob >= go_threshold:
        decision = 'go_for_it'
        confidence = 'high' if conversion_prob >= 0.60 else 'medium'
        reasoning = f"Conversion probability {conversion_prob:.1%} exceeds threshold"

        if fg_viable and conversion_prob < 0.55:
            alternative = 'field_goal'
        else:
            alternative = None

    elif fg_viable:
        decision = 'field_goal'
        confidence = 'high' if fg_distance <= 45 else 'medium'
        reasoning = f"Field goal viable from {fg_distance} yards"
        alternative = 'go_for_it' if conversion_prob >= 0.40 else None

    else:
        decision = 'punt'
        confidence = 'medium'
        reasoning = f"Conversion probability {conversion_prob:.1%} below threshold, FG not viable"
        alternative = 'go_for_it' if conversion_prob >= 0.35 else None

    # Override for desperate situations
    if is_desperate and score_diff < 0 and time_remaining < 300:
        if field_position <= 55:
            decision = 'go_for_it'
            reasoning = "Desperate situation requires aggression"
            confidence = 'low'

    return {
        'decision': decision,
        'confidence': confidence,
        'reasoning': reasoning,
        'alternative': alternative,
        'conversion_probability': conversion_prob
    }


# ==============================================================================
# TESTING
# ==============================================================================

if __name__ == "__main__":
    """
    Test conversion probability calculations.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from ingestion.play_by_play import load_pbp_data

    logger.info("="*60)
    logger.info("CONVERSION PROBABILITY MODEL TEST")
    logger.info("="*60)

    # Load sample data
    logger.info("Loading 2023 season...")
    pbp = load_pbp_data(seasons=[2023])

    # Build base rate table
    logger.info("\n" + "="*60)
    logger.info("BUILDING BASE RATE TABLE")
    logger.info("="*60)

    base_rate_table = build_base_rate_table(pbp)
    logger.info(f"Built table with {len(base_rate_table)} entries")

    # Show sample base rates
    logger.info("\nSample base rates:")
    for yards in [1, 2, 5, 10]:
        for zone in ['red_zone', 'opp_side']:
            rate = base_rate_table.get((yards, zone))
            if rate:
                logger.info(f"  {yards} yards, {zone}: {rate:.1%}")

    # Create model
    model = ConversionModel(base_rate_table)

    # Test scenario 1: 4th and 1 in red zone, high momentum
    logger.info("\n" + "="*60)
    logger.info("TEST 1: 4th and 1 in red zone, high momentum")
    logger.info("="*60)

    result = model.predict(
        yards_to_go=1,
        yardline_100=10,  # Red zone
        momentum_score=70,  # High momentum (+4%)
        weather_modifier=1.0,
        fatigue_modifier=1.0,
        injury_modifier=1.0,
        crowd_modifier=1.0
    )

    logger.info(f"Base rate: {result['base_rate']:.3f}")
    logger.info(f"Momentum modifier: {result['momentum_modifier']:+.3f}")
    logger.info(f"Total modifier: {result['total_modifier']:+.3f}")
    logger.info(f"Final probability: {result['final_probability']:.3f}")
    logger.info(f"Confidence: {result['confidence']}")

    # Test scenario 2: 4th and 10, away team at loud stadium
    logger.info("\n" + "="*60)
    logger.info("TEST 2: 4th and 10, bad conditions")
    logger.info("="*60)

    result = model.predict(
        yards_to_go=10,
        yardline_100=65,  # Own side
        momentum_score=30,  # Low momentum (-4%)
        weather_modifier=0.90,  # Bad weather (-10%)
        fatigue_modifier=0.95,  # Offensive fatigue (-5%)
        injury_modifier=0.85,  # Injuries (-15%)
        crowd_modifier=0.92   # Loud crowd (-8%)
    )

    logger.info(f"Base rate: {result['base_rate']:.3f}")
    logger.info(f"Momentum modifier: {result['momentum_modifier']:+.3f}")
    logger.info(f"Weather modifier: {result['weather_modifier']:+.3f}")
    logger.info(f"Fatigue modifier: {result['fatigue_modifier']:+.3f}")
    logger.info(f"Injury modifier: {result['injury_modifier']:+.3f}")
    logger.info(f"Crowd modifier: {result['crowd_modifier']:+.3f}")
    logger.info(f"Total modifier: {result['total_modifier']:+.3f}")
    logger.info(f"Final probability: {result['final_probability']:.3f}")
    logger.info(f"Confidence: {result['confidence']}")

    # Test scenario 3: Decision recommendation
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Decision recommendations")
    logger.info("="*60)

    scenarios = [
        (0.65, 35, 3, 300, 1, "4th and 1 at opp 35, 65% conversion"),
        (0.40, 25, -7, 120, 5, "4th and 5 at opp 25, trailing late"),
        (0.30, 70, 10, 600, 7, "4th and 7 at own 30, winning"),
    ]

    for conv_prob, field_pos, score, time, yards, desc in scenarios:
        logger.info(f"\n{desc}:")
        rec = recommend_decision(conv_prob, field_pos, score, time, yards)
        logger.info(f"  Decision: {rec['decision']}")
        logger.info(f"  Confidence: {rec['confidence']}")
        logger.info(f"  Reasoning: {rec['reasoning']}")
        if rec['alternative']:
            logger.info(f"  Alternative: {rec['alternative']}")
