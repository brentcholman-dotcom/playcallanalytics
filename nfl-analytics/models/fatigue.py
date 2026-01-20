"""
Fatigue Estimation Model

This module calculates fatigue impact on play success probability based on:
- Consecutive plays without change of possession
- Time of possession
- Temperature effects on fatigue
- Timeout reset logic

Fatigue can help or hurt the offense depending on which unit is fatigued.
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


def calculate_consecutive_plays(game_plays, current_index):
    """
    Calculate consecutive plays for each team without change of possession.

    Args:
        game_plays: DataFrame with plays from a single game
        current_index: Index of current play

    Returns:
        tuple: (offensive_consecutive_plays, defensive_consecutive_plays)
    """
    if current_index == 0:
        return 0, 0

    current_play = game_plays.iloc[current_index]
    current_offense = current_play.get('posteam')

    if pd.isna(current_offense):
        return 0, 0

    # Count consecutive plays with same offense (offensive plays)
    offensive_consecutive = 0
    for i in range(current_index - 1, -1, -1):
        prev_play = game_plays.iloc[i]
        if prev_play.get('posteam') == current_offense:
            offensive_consecutive += 1
        else:
            break

    # Count consecutive plays with current team on defense
    # (when opponent had the ball)
    defensive_consecutive = 0
    current_defense = current_play.get('defteam')
    if not pd.isna(current_defense):
        for i in range(current_index - 1, -1, -1):
            prev_play = game_plays.iloc[i]
            prev_offense = prev_play.get('posteam')
            # If previous play was opponent's possession
            if prev_offense == current_defense:
                defensive_consecutive += 1
            elif prev_offense == current_offense:
                # Found start of current drive
                break
            else:
                # Different opponent, still counts as defensive plays
                if not pd.isna(prev_offense):
                    defensive_consecutive += 1

    return offensive_consecutive, defensive_consecutive


def calculate_time_of_possession(game_plays, current_index, team, quarter):
    """
    Calculate time of possession for a team in the current quarter.

    Args:
        game_plays: DataFrame with plays from a single game
        current_index: Index of current play
        team: Team abbreviation
        quarter: Current quarter

    Returns:
        float: Time of possession in minutes
    """
    if pd.isna(team) or pd.isna(quarter):
        return 0.0

    # Filter to plays in current quarter up to current index
    quarter_plays = game_plays.iloc[:current_index + 1].copy()
    quarter_plays = quarter_plays[quarter_plays['qtr'] == quarter]

    if quarter_plays.empty:
        return 0.0

    # Estimate time per play (average ~6 seconds per play)
    team_plays = quarter_plays[quarter_plays['posteam'] == team]
    plays_count = len(team_plays)

    # Rough estimate: 6 seconds per play
    top_seconds = plays_count * 6
    top_minutes = top_seconds / 60.0

    return top_minutes


def calculate_base_fatigue(consecutive_plays, top_minutes):
    """
    Calculate base fatigue score before temperature modifier.

    Args:
        consecutive_plays: Number of consecutive plays
        top_minutes: Time of possession in minutes

    Returns:
        float: Base fatigue score
    """
    if pd.isna(consecutive_plays):
        consecutive_plays = 0
    if pd.isna(top_minutes):
        top_minutes = 0

    base_fatigue = (consecutive_plays * 0.3) + (top_minutes * 0.5)
    return base_fatigue


def calculate_temperature_modifier(temperature):
    """
    Calculate temperature modifier for fatigue.

    High heat increases fatigue impact.

    Args:
        temperature: Temperature in Fahrenheit

    Returns:
        float: Temperature modifier (1.0 or higher)
    """
    if pd.isna(temperature):
        return 1.0

    # 2% more fatigue per degree over 85°F
    temp_modifier = 1.0 + max(0, (temperature - 85) * 0.02)
    return temp_modifier


def convert_fatigue_to_impact(fatigue_score, is_defensive=True):
    """
    Convert fatigue score to percentage impact.

    Defensive fatigue helps offense (positive impact).
    Offensive fatigue hurts offense (negative impact).

    Args:
        fatigue_score: Calculated fatigue score
        is_defensive: True for defensive fatigue, False for offensive

    Returns:
        float: Percentage impact (as decimal, e.g., 0.03 for +3%)
    """
    if pd.isna(fatigue_score):
        return 0.0

    # Impact tiers
    if fatigue_score >= 20:
        impact = 0.07  # 7%
    elif fatigue_score >= 15:
        impact = 0.05  # 5%
    elif fatigue_score >= 10:
        impact = 0.03  # 3%
    elif fatigue_score >= 5:
        impact = 0.015  # 1.5%
    else:
        impact = 0.0  # 0%

    # Defensive fatigue helps offense (positive)
    # Offensive fatigue hurts offense (negative)
    if not is_defensive:
        impact = -impact

    return impact


def apply_timeout_reset(fatigue_score, timeout_called):
    """
    Apply timeout reset to fatigue score.

    Timeouts reduce fatigue by 50%.

    Args:
        fatigue_score: Current fatigue score
        timeout_called: Whether a timeout was called

    Returns:
        float: Adjusted fatigue score
    """
    if pd.isna(fatigue_score):
        return 0.0

    if timeout_called:
        return fatigue_score * 0.5

    return fatigue_score


def calculate_defensive_fatigue(game_plays, current_index, temperature=None):
    """
    Calculate defensive fatigue score (helps offense when high).

    Args:
        game_plays: DataFrame with plays from a single game
        current_index: Index of current play
        temperature: Temperature in Fahrenheit (optional)

    Returns:
        dict: {
            'consecutive_plays': int,
            'top_minutes': float,
            'base_fatigue': float,
            'temp_modifier': float,
            'fatigue_score': float,
            'impact_pct': float
        }
    """
    current_play = game_plays.iloc[current_index]

    # Get consecutive defensive plays
    _, defensive_consecutive = calculate_consecutive_plays(game_plays, current_index)

    # Get defensive team's TOP when they were on offense
    defensive_team = current_play.get('defteam')
    current_quarter = current_play.get('qtr')

    # Calculate TOP for opponent (defensive team when on offense)
    top_minutes = calculate_time_of_possession(
        game_plays, current_index, defensive_team, current_quarter
    )

    # Calculate base fatigue
    base_fatigue = calculate_base_fatigue(defensive_consecutive, top_minutes)

    # Apply temperature modifier
    temp_modifier = calculate_temperature_modifier(temperature)
    fatigue_score = base_fatigue * temp_modifier

    # Convert to impact
    impact_pct = convert_fatigue_to_impact(fatigue_score, is_defensive=True)

    return {
        'consecutive_plays': defensive_consecutive,
        'top_minutes': top_minutes,
        'base_fatigue': base_fatigue,
        'temp_modifier': temp_modifier,
        'fatigue_score': fatigue_score,
        'impact_pct': impact_pct
    }


def calculate_offensive_fatigue(game_plays, current_index, temperature=None):
    """
    Calculate offensive fatigue score (hurts offense when high).

    Args:
        game_plays: DataFrame with plays from a single game
        current_index: Index of current play
        temperature: Temperature in Fahrenheit (optional)

    Returns:
        dict: {
            'consecutive_plays': int,
            'top_minutes': float,
            'base_fatigue': float,
            'temp_modifier': float,
            'fatigue_score': float,
            'impact_pct': float (negative)
        }
    """
    current_play = game_plays.iloc[current_index]

    # Get consecutive offensive plays
    offensive_consecutive, _ = calculate_consecutive_plays(game_plays, current_index)

    # Get offensive team's TOP
    offensive_team = current_play.get('posteam')
    current_quarter = current_play.get('qtr')

    top_minutes = calculate_time_of_possession(
        game_plays, current_index, offensive_team, current_quarter
    )

    # Calculate base fatigue
    base_fatigue = calculate_base_fatigue(offensive_consecutive, top_minutes)

    # Apply temperature modifier
    temp_modifier = calculate_temperature_modifier(temperature)
    fatigue_score = base_fatigue * temp_modifier

    # Convert to impact (negative for offense)
    impact_pct = convert_fatigue_to_impact(fatigue_score, is_defensive=False)

    return {
        'consecutive_plays': offensive_consecutive,
        'top_minutes': top_minutes,
        'base_fatigue': base_fatigue,
        'temp_modifier': temp_modifier,
        'fatigue_score': fatigue_score,
        'impact_pct': impact_pct
    }


def calculate_net_fatigue_modifier(game_plays, current_index, temperature=None,
                                   timeout_called=False):
    """
    Calculate net fatigue modifier combining defensive and offensive fatigue.

    Args:
        game_plays: DataFrame with plays from a single game
        current_index: Index of current play
        temperature: Temperature in Fahrenheit (optional)
        timeout_called: Whether a timeout was just called

    Returns:
        dict: {
            'defensive_fatigue': dict,
            'offensive_fatigue': dict,
            'net_impact_pct': float,
            'fatigue_modifier': float (multiplier)
        }
    """
    # Calculate both types of fatigue
    def_fatigue = calculate_defensive_fatigue(game_plays, current_index, temperature)
    off_fatigue = calculate_offensive_fatigue(game_plays, current_index, temperature)

    # Apply timeout reset if applicable
    if timeout_called:
        def_fatigue['fatigue_score'] = apply_timeout_reset(
            def_fatigue['fatigue_score'], True
        )
        off_fatigue['fatigue_score'] = apply_timeout_reset(
            off_fatigue['fatigue_score'], True
        )

        # Recalculate impact percentages after timeout
        def_fatigue['impact_pct'] = convert_fatigue_to_impact(
            def_fatigue['fatigue_score'], is_defensive=True
        )
        off_fatigue['impact_pct'] = convert_fatigue_to_impact(
            off_fatigue['fatigue_score'], is_defensive=False
        )

    # Net impact = defensive fatigue (helps) + offensive fatigue (hurts)
    net_impact_pct = def_fatigue['impact_pct'] + off_fatigue['impact_pct']

    # Convert to multiplier (1.0 = no impact, >1.0 = helps, <1.0 = hurts)
    fatigue_modifier = 1.0 + net_impact_pct

    return {
        'defensive_fatigue': def_fatigue,
        'offensive_fatigue': off_fatigue,
        'net_impact_pct': net_impact_pct,
        'fatigue_modifier': fatigue_modifier
    }


def add_fatigue_modifiers(plays_df):
    """
    Add fatigue modifier columns to plays dataframe.

    Args:
        plays_df: DataFrame with play data

    Returns:
        DataFrame: Original dataframe with fatigue columns added
    """
    logger.info("Adding fatigue modifiers to plays...")

    result = plays_df.copy()

    # Initialize columns
    result['defensive_fatigue_score'] = 0.0
    result['offensive_fatigue_score'] = 0.0
    result['net_fatigue_impact_pct'] = 0.0
    result['fatigue_modifier'] = 1.0

    # Process each game separately
    games = result['game_id'].unique()

    for game_id in games:
        game_mask = result['game_id'] == game_id
        game_plays = result[game_mask].copy()
        game_plays = game_plays.reset_index(drop=True)

        # Get temperature for this game (if available)
        temp = game_plays['temp'].iloc[0] if 'temp' in game_plays.columns else None

        # Calculate fatigue for each play
        for idx in range(len(game_plays)):
            # Check for timeout (simplified - would need timeout column)
            timeout_called = False

            fatigue_result = calculate_net_fatigue_modifier(
                game_plays, idx, temperature=temp, timeout_called=timeout_called
            )

            # Update the original dataframe at correct location
            original_idx = game_plays.index[idx]
            result_idx = result.index[game_mask][original_idx]

            result.loc[result_idx, 'defensive_fatigue_score'] = \
                fatigue_result['defensive_fatigue']['fatigue_score']
            result.loc[result_idx, 'offensive_fatigue_score'] = \
                fatigue_result['offensive_fatigue']['fatigue_score']
            result.loc[result_idx, 'net_fatigue_impact_pct'] = \
                fatigue_result['net_impact_pct']
            result.loc[result_idx, 'fatigue_modifier'] = \
                fatigue_result['fatigue_modifier']

    logger.info("Fatigue modifiers added")
    logger.info(f"  Mean fatigue modifier: {result['fatigue_modifier'].mean():.3f}")
    logger.info(f"  Plays with defensive fatigue > 5: {(result['defensive_fatigue_score'] > 5).sum():,}")
    logger.info(f"  Plays with offensive fatigue > 5: {(result['offensive_fatigue_score'] > 5).sum():,}")

    return result


def analyze_fatigue_impact(plays_df):
    """
    Analyze fatigue impact distribution.

    Args:
        plays_df: DataFrame with fatigue columns

    Returns:
        DataFrame: Summary statistics
    """
    if 'fatigue_modifier' not in plays_df.columns:
        logger.error("No fatigue_modifier column found")
        return pd.DataFrame()

    result = plays_df.copy()

    # Categorize fatigue levels
    def categorize_defensive_fatigue(score):
        if score >= 20:
            return 'extreme'
        elif score >= 15:
            return 'high'
        elif score >= 10:
            return 'moderate'
        elif score >= 5:
            return 'mild'
        else:
            return 'fresh'

    result['def_fatigue_category'] = result['defensive_fatigue_score'].apply(
        categorize_defensive_fatigue
    )

    # Analyze by category
    summary = result.groupby('def_fatigue_category').agg({
        'defensive_fatigue_score': ['count', 'mean'],
        'offensive_fatigue_score': 'mean',
        'net_fatigue_impact_pct': 'mean',
        'fatigue_modifier': 'mean'
    }).round(3)

    return summary


# Legacy compatibility functions
def calculate_fatigue_level(play_count, game_time, temperature, pace):
    """
    Legacy function for backward compatibility.

    Note: Use calculate_net_fatigue_modifier() for new code.

    Args:
        play_count: Number of plays run
        game_time: Current game time (seconds)
        temperature: Temperature in Fahrenheit
        pace: Plays per minute

    Returns:
        float: Fatigue factor (0.0 to 1.0)
    """
    logger.warning("calculate_fatigue_level() is deprecated")

    # Simple estimate
    top_minutes = (play_count * 6) / 60.0  # ~6 sec per play
    base_fatigue = calculate_base_fatigue(play_count, top_minutes)
    temp_modifier = calculate_temperature_modifier(temperature)
    fatigue_score = base_fatigue * temp_modifier

    # Normalize to 0-1 scale
    return min(1.0, fatigue_score / 25.0)


def estimate_unit_fatigue(unit_type, snap_counts, rest_time):
    """
    Legacy function for backward compatibility.

    Note: Use calculate_defensive_fatigue() or calculate_offensive_fatigue().

    Args:
        unit_type: 'offense' or 'defense'
        snap_counts: List of snap counts by player
        rest_time: Time since last drive (seconds)

    Returns:
        dict: Unit-specific fatigue metrics
    """
    logger.warning("estimate_unit_fatigue() is deprecated")

    avg_snaps = np.mean(snap_counts) if snap_counts else 0

    return {
        'unit': unit_type,
        'avg_snaps': avg_snaps,
        'rest_time': rest_time,
        'fatigue_estimate': min(1.0, avg_snaps / 50.0)
    }


if __name__ == "__main__":
    """
    Test fatigue calculations.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from ingestion.play_by_play import load_pbp_data

    logger.info("="*60)
    logger.info("FATIGUE MODEL TEST")
    logger.info("="*60)

    # Load sample data
    logger.info("Loading 2023 season...")
    pbp = load_pbp_data(seasons=[2023])

    # Get first game
    first_game = pbp['game_id'].iloc[0]
    game = pbp[pbp['game_id'] == first_game].copy()

    logger.info(f"\nProcessing game: {first_game}")
    logger.info(f"Total plays: {len(game)}")

    # Test on a few plays
    logger.info("\n" + "="*60)
    logger.info("SAMPLE PLAY FATIGUE CALCULATIONS")
    logger.info("="*60)

    # Test play 20 (should have some fatigue built up)
    if len(game) > 20:
        test_indices = [10, 20, 40, 60]

        for idx in test_indices:
            if idx < len(game):
                play = game.iloc[idx]
                temp = play.get('temp') if 'temp' in game.columns else None

                logger.info(f"\nPlay {idx}:")
                logger.info(f"  Team: {play.get('posteam', 'N/A')}")
                logger.info(f"  Quarter: {play.get('qtr', 'N/A')}")
                logger.info(f"  Temperature: {temp}°F" if temp else "  Temperature: N/A")

                result = calculate_net_fatigue_modifier(game, idx, temperature=temp)

                logger.info(f"  Defensive Fatigue:")
                logger.info(f"    Consecutive plays: {result['defensive_fatigue']['consecutive_plays']}")
                logger.info(f"    TOP minutes: {result['defensive_fatigue']['top_minutes']:.1f}")
                logger.info(f"    Fatigue score: {result['defensive_fatigue']['fatigue_score']:.2f}")
                logger.info(f"    Impact: {result['defensive_fatigue']['impact_pct']*100:+.1f}%")

                logger.info(f"  Offensive Fatigue:")
                logger.info(f"    Consecutive plays: {result['offensive_fatigue']['consecutive_plays']}")
                logger.info(f"    TOP minutes: {result['offensive_fatigue']['top_minutes']:.1f}")
                logger.info(f"    Fatigue score: {result['offensive_fatigue']['fatigue_score']:.2f}")
                logger.info(f"    Impact: {result['offensive_fatigue']['impact_pct']*100:+.1f}%")

                logger.info(f"  Net Impact: {result['net_impact_pct']*100:+.1f}%")
                logger.info(f"  Fatigue Modifier: {result['fatigue_modifier']:.3f}")

    # Add fatigue to entire game
    logger.info("\n" + "="*60)
    logger.info("ADDING FATIGUE TO ENTIRE GAME")
    logger.info("="*60)

    game_with_fatigue = add_fatigue_modifiers(game)

    # Show distribution
    logger.info("\nFatigue statistics:")
    logger.info(f"  Defensive fatigue - Mean: {game_with_fatigue['defensive_fatigue_score'].mean():.2f}")
    logger.info(f"  Defensive fatigue - Max: {game_with_fatigue['defensive_fatigue_score'].max():.2f}")
    logger.info(f"  Offensive fatigue - Mean: {game_with_fatigue['offensive_fatigue_score'].mean():.2f}")
    logger.info(f"  Offensive fatigue - Max: {game_with_fatigue['offensive_fatigue_score'].max():.2f}")
    logger.info(f"  Net modifier - Mean: {game_with_fatigue['fatigue_modifier'].mean():.3f}")
    logger.info(f"  Net modifier - Min: {game_with_fatigue['fatigue_modifier'].min():.3f}")
    logger.info(f"  Net modifier - Max: {game_with_fatigue['fatigue_modifier'].max():.3f}")

    # Analyze impact
    logger.info("\n" + "="*60)
    logger.info("FATIGUE IMPACT ANALYSIS")
    logger.info("="*60)
    summary = analyze_fatigue_impact(game_with_fatigue)
    print(summary)
