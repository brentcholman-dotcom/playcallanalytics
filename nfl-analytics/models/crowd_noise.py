"""
Crowd Noise Impact Model

This module models the impact of crowd noise on offensive communication and
play execution. Supports both direct dB measurement and proxy estimation.
"""

import logging
from typing import Optional, Dict
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# STADIUM NOISE BASE RATINGS
# ==============================================================================

# Base noise ratings for all 32 NFL stadiums (scale 0-100)
# Higher = louder venue
STADIUM_NOISE = {
    # Elite noise venues (95+)
    'KC': 98,      # Arrowhead Stadium - holds world record
    'SEA': 96,     # Lumen Field - famous 12th man
    'NO': 95,      # Superdome - dome amplifies sound
    'MIN': 93,     # US Bank Stadium - indoor dome

    # Very loud (85-89)
    'PIT': 88,     # Acrisure Stadium - passionate fans
    'PHI': 88,     # Lincoln Financial Field - intense crowd
    'BAL': 86,     # M&T Bank Stadium
    'GB': 85,      # Lambeau Field - historic venue
    'BUF': 85,     # Highmark Stadium - Bills Mafia

    # Loud (80-84)
    'SF': 84,      # Levi's Stadium
    'DAL': 83,     # AT&T Stadium - large capacity
    'CIN': 82,     # Paycor Stadium
    'DEN': 82,     # Empower Field - altitude affects sound
    'TEN': 81,     # Nissan Stadium
    'LAC': 80,     # SoFi Stadium (shared, newer)
    'LAR': 80,     # SoFi Stadium (shared, newer)

    # Above average (75-79)
    'CLE': 79,     # FirstEnergy Stadium - Dawg Pound
    'DET': 78,     # Ford Field - indoor
    'CHI': 77,     # Soldier Field
    'CAR': 77,     # Bank of America Stadium
    'ATL': 76,     # Mercedes-Benz Stadium - retractable roof
    'IND': 76,     # Lucas Oil Stadium - dome
    'NE': 76,      # Gillette Stadium
    'TB': 76,      # Raymond James Stadium
    'LV': 75,      # Allegiant Stadium - newer dome
    'ARI': 75,     # State Farm Stadium - retractable roof

    # Average (70-74)
    'WAS': 74,     # FedExField
    'NYG': 73,     # MetLife Stadium (shared)
    'NYJ': 73,     # MetLife Stadium (shared)
    'HOU': 72,     # NRG Stadium - retractable roof
    'MIA': 72,     # Hard Rock Stadium
    'JAX': 70,     # TIAA Bank Field
}

# Default for unlisted teams
DEFAULT_STADIUM_NOISE = 75


# ==============================================================================
# SITUATION INTENSITY FACTORS
# ==============================================================================

SITUATION_INTENSITY = {
    'routine': 0.3,      # Routine plays (1st/2nd down)
    'third_down': 0.7,   # 3rd down situations
    'fourth_down': 1.0,  # 4th down (maximum intensity)
    'red_zone': 0.85,    # Red zone situations
    'two_minute': 0.95,  # Two-minute drill
}


# ==============================================================================
# GAME STATE FACTORS
# ==============================================================================

def get_game_state_factor(score_differential: int) -> float:
    """
    Get crowd intensity factor based on score differential.

    Crowds are loudest when game is close.

    Args:
        score_differential: Absolute score difference

    Returns:
        float: Game state factor (0.3 to 1.0)
    """
    abs_diff = abs(score_differential)

    if abs_diff <= 7:
        return 1.0      # One score game - maximum intensity
    elif abs_diff <= 14:
        return 0.75     # Two score game
    elif abs_diff <= 21:
        return 0.5      # Three score game
    else:
        return 0.3      # Blowout - crowd disengaged


# ==============================================================================
# QUARTER FACTORS
# ==============================================================================

QUARTER_FACTOR = {
    1: 0.7,     # Q1 - crowd warming up
    2: 0.8,     # Q2 - building momentum
    3: 0.85,    # Q3 - second half energy
    4: 1.0,     # Q4 - maximum intensity
    5: 1.1,     # OT - overtime excitement
}


# ==============================================================================
# PLAY TYPE ADJUSTMENTS
# ==============================================================================

PLAY_TYPE_PENALTY = {
    'pass': 1.0,        # Full penalty for pass plays (communication critical)
    'run': 0.5,         # Half penalty for run plays
    'qb_sneak': 0.25,   # Minimal penalty for QB sneak (simple play)
}


# ==============================================================================
# DIRECT dB CONVERSION
# ==============================================================================

def db_to_impact(decibels: float) -> float:
    """
    Convert direct dB measurement to impact modifier.

    Crowd noise affects offensive communication and causes false starts.

    Args:
        decibels: Measured sound level in dB

    Returns:
        float: Impact modifier (negative, e.g., -0.05 for -5%)
    """
    if decibels < 70:
        return 0.0          # No impact
    elif decibels < 86:
        return -0.01        # -1%
    elif decibels <= 100:
        return -0.03        # -3%
    elif decibels <= 110:
        return -0.05        # -5%
    elif decibels <= 120:
        return -0.08        # -8%
    elif decibels <= 130:
        return -0.11        # -11%
    else:
        return -0.13        # -13% maximum


# ==============================================================================
# PROXY ESTIMATION
# ==============================================================================

def get_stadium_base_noise(team: str) -> int:
    """
    Get base noise rating for stadium.

    Args:
        team: Team abbreviation (e.g., 'KC', 'SEA')

    Returns:
        int: Base noise rating (0-100)
    """
    team = team.upper() if team else ''
    return STADIUM_NOISE.get(team, DEFAULT_STADIUM_NOISE)


def estimate_crowd_noise(
    team: str,
    is_home: bool,
    situation: str = 'routine',
    score_differential: int = 0,
    quarter: int = 1,
    is_offense_home: bool = True
) -> float:
    """
    Estimate crowd noise using proxy factors.

    Args:
        team: Team abbreviation for stadium
        is_home: Whether this is a home game for the stadium team
        situation: 'routine', 'third_down', 'fourth_down', 'red_zone', 'two_minute'
        score_differential: Score difference (positive or negative)
        quarter: Quarter (1-4, 5 for OT)
        is_offense_home: Whether the offense is the home team

    Returns:
        float: Estimated noise score (0-100)
    """
    # Get base stadium rating
    base = get_stadium_base_noise(team)

    # Home/away factor: crowd is loud when AWAY team has ball
    # If offense is home team, crowd is quiet (factor = 0.0)
    # If offense is away team, crowd is loud (factor = 1.0)
    home_away_factor = 0.0 if is_offense_home else 1.0

    # Situation intensity
    situation_factor = SITUATION_INTENSITY.get(situation, 0.3)

    # Game state factor
    game_state_factor = get_game_state_factor(score_differential)

    # Quarter factor
    quarter_factor = QUARTER_FACTOR.get(quarter, 0.7)

    # Calculate estimated noise score
    estimated_noise = (
        base * home_away_factor * situation_factor *
        game_state_factor * quarter_factor
    )

    logger.debug(f"Noise estimation: base={base}, home_away={home_away_factor}, "
                f"situation={situation_factor}, game_state={game_state_factor}, "
                f"quarter={quarter_factor}, result={estimated_noise:.1f}")

    return estimated_noise


def proxy_noise_to_impact(noise_score: float, play_type: str = 'pass') -> float:
    """
    Convert proxy noise score to impact modifier.

    Maps 0-100 noise score to dB equivalent, then to impact.

    Args:
        noise_score: Estimated noise score (0-100)
        play_type: 'pass', 'run', or 'qb_sneak'

    Returns:
        float: Impact modifier (negative)
    """
    if noise_score <= 0:
        return 0.0

    # Map noise score (0-100) to approximate dB (70-130)
    # Linear mapping: score 0 = 70 dB, score 100 = 130 dB
    estimated_db = 70 + (noise_score / 100.0) * 60

    # Convert to base impact
    base_impact = db_to_impact(estimated_db)

    # Apply play type adjustment
    play_penalty = PLAY_TYPE_PENALTY.get(play_type, 1.0)
    adjusted_impact = base_impact * play_penalty

    return adjusted_impact


# ==============================================================================
# MAIN MODIFIER FUNCTION
# ==============================================================================

def calculate_crowd_modifier(
    team: str,
    is_offense_home: bool,
    situation: str = 'fourth_down',
    score_differential: int = 0,
    quarter: int = 4,
    play_type: str = 'pass',
    actual_db: Optional[float] = None
) -> float:
    """
    Calculate crowd noise modifier.

    Uses direct dB measurement if available, otherwise uses proxy estimation.

    Args:
        team: Team abbreviation for stadium
        is_offense_home: Whether the offense is the home team
        situation: 'routine', 'third_down', 'fourth_down', 'red_zone', 'two_minute'
        score_differential: Score difference
        quarter: Quarter (1-4, 5 for OT)
        play_type: 'pass', 'run', or 'qb_sneak'
        actual_db: Optional direct dB measurement

    Returns:
        float: Crowd noise modifier (1.0 = no impact, <1.0 = negative impact)
    """
    if actual_db is not None:
        # Use direct dB measurement
        logger.debug(f"Using direct dB measurement: {actual_db} dB")
        base_impact = db_to_impact(actual_db)

        # Apply play type adjustment
        play_penalty = PLAY_TYPE_PENALTY.get(play_type, 1.0)
        impact = base_impact * play_penalty

    else:
        # Use proxy estimation
        logger.debug("Using proxy estimation for crowd noise")
        noise_score = estimate_crowd_noise(
            team=team,
            is_home=True,  # Assuming we're evaluating at this team's stadium
            situation=situation,
            score_differential=score_differential,
            quarter=quarter,
            is_offense_home=is_offense_home
        )

        impact = proxy_noise_to_impact(noise_score, play_type)

    # Convert impact to multiplier
    modifier = 1.0 + impact

    logger.info(f"Crowd noise modifier: {modifier:.3f} (impact: {impact:+.3f})")
    return modifier


def calculate_crowd_modifier_from_play(
    play_data: Dict,
    actual_db: Optional[float] = None
) -> float:
    """
    Calculate crowd modifier from play data dictionary.

    Args:
        play_data: Dictionary with play information
        actual_db: Optional direct dB measurement

    Returns:
        float: Crowd noise modifier
    """
    # Extract play information
    home_team = play_data.get('home_team', '')
    away_team = play_data.get('away_team', '')
    posteam = play_data.get('posteam', '')

    # Determine if offense is home team
    is_offense_home = (posteam == home_team)

    # Get stadium (home team's stadium)
    stadium_team = home_team

    # Determine situation
    down = play_data.get('down', 1)
    ydstogo = play_data.get('ydstogo', 10)
    yardline_100 = play_data.get('yardline_100', 50)
    game_seconds_remaining = play_data.get('game_seconds_remaining', 3600)

    if down == 4:
        situation = 'fourth_down'
    elif down == 3:
        situation = 'third_down'
    elif yardline_100 <= 20:
        situation = 'red_zone'
    elif game_seconds_remaining <= 120:
        situation = 'two_minute'
    else:
        situation = 'routine'

    # Score differential
    score_diff = play_data.get('score_differential', 0)

    # Quarter
    quarter = play_data.get('qtr', 1)

    # Play type
    play_type_raw = play_data.get('play_type', 'pass')
    if play_type_raw == 'qb_kneel' or play_type_raw == 'qb_spike':
        play_type = 'qb_sneak'
    elif play_type_raw == 'run':
        play_type = 'run'
    else:
        play_type = 'pass'

    # Calculate modifier
    return calculate_crowd_modifier(
        team=stadium_team,
        is_offense_home=is_offense_home,
        situation=situation,
        score_differential=score_diff,
        quarter=quarter,
        play_type=play_type,
        actual_db=actual_db
    )


# ==============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ==============================================================================

def calculate_noise_impact(is_home, stadium_capacity, attendance, dome_status):
    """
    Legacy function for backward compatibility.

    Note: Use calculate_crowd_modifier() for new code.

    Args:
        is_home: Boolean indicating if team is home
        stadium_capacity: Stadium capacity
        attendance: Actual attendance
        dome_status: 'dome', 'open', or 'retractable'

    Returns:
        float: Noise impact factor
    """
    logger.warning("calculate_noise_impact() is deprecated")

    # Simple estimation
    if is_home:
        return 1.0  # No negative impact when home

    # Away team faces noise
    attendance_pct = attendance / stadium_capacity if stadium_capacity > 0 else 0.8

    # Domes are louder
    dome_factor = 1.2 if dome_status == 'dome' else 1.0

    # Simple impact calculation
    noise_factor = attendance_pct * dome_factor
    impact = -0.05 * noise_factor  # Up to -5% impact

    return 1.0 + impact


def adjust_for_home_field(team, opponent, venue_data):
    """
    Legacy function for backward compatibility.

    Note: Use calculate_crowd_modifier() for new code.

    Args:
        team: Team identifier
        opponent: Opponent identifier
        venue_data: Venue characteristics

    Returns:
        float: Home field adjustment
    """
    logger.warning("adjust_for_home_field() is deprecated")

    base_noise = get_stadium_base_noise(team)

    # Simple home field advantage
    advantage = (base_noise - DEFAULT_STADIUM_NOISE) / 1000.0

    return 1.0 + advantage


# ==============================================================================
# TESTING
# ==============================================================================

if __name__ == "__main__":
    """
    Test crowd noise calculations.
    """
    logger.info("="*60)
    logger.info("CROWD NOISE MODEL TEST")
    logger.info("="*60)

    # Test scenario 1: 4th down at Arrowhead (KC), away offense
    logger.info("\n" + "="*60)
    logger.info("TEST 1: 4th down at Arrowhead, away offense")
    logger.info("="*60)

    noise_score = estimate_crowd_noise(
        team='KC',
        is_home=True,
        situation='fourth_down',
        score_differential=3,
        quarter=4,
        is_offense_home=False  # Away team has ball
    )
    logger.info(f"Estimated noise score: {noise_score:.1f}")

    modifier = calculate_crowd_modifier(
        team='KC',
        is_offense_home=False,
        situation='fourth_down',
        score_differential=3,
        quarter=4,
        play_type='pass'
    )
    logger.info(f"Crowd modifier: {modifier:.3f}")

    # Test scenario 2: Same situation but home offense
    logger.info("\n" + "="*60)
    logger.info("TEST 2: 4th down at Arrowhead, home offense")
    logger.info("="*60)

    noise_score = estimate_crowd_noise(
        team='KC',
        is_home=True,
        situation='fourth_down',
        score_differential=3,
        quarter=4,
        is_offense_home=True  # Home team has ball
    )
    logger.info(f"Estimated noise score: {noise_score:.1f}")

    modifier = calculate_crowd_modifier(
        team='KC',
        is_offense_home=True,
        situation='fourth_down',
        score_differential=3,
        quarter=4,
        play_type='pass'
    )
    logger.info(f"Crowd modifier: {modifier:.3f}")

    # Test scenario 3: Direct dB measurement (125 dB at Seattle)
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Direct dB measurement (125 dB)")
    logger.info("="*60)

    modifier = calculate_crowd_modifier(
        team='SEA',
        is_offense_home=False,
        play_type='pass',
        actual_db=125.0
    )
    logger.info(f"Crowd modifier with direct dB: {modifier:.3f}")

    # Test scenario 4: Different play types
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Play type adjustments at 4th down")
    logger.info("="*60)

    for play_type in ['pass', 'run', 'qb_sneak']:
        modifier = calculate_crowd_modifier(
            team='SEA',
            is_offense_home=False,
            situation='fourth_down',
            score_differential=0,
            quarter=4,
            play_type=play_type
        )
        logger.info(f"{play_type:10s}: {modifier:.3f}")

    # Test scenario 5: Game state impact
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Game state impact (score differential)")
    logger.info("="*60)

    for score_diff in [3, 10, 21, 35]:
        noise_score = estimate_crowd_noise(
            team='PHI',
            is_home=True,
            situation='fourth_down',
            score_differential=score_diff,
            quarter=4,
            is_offense_home=False
        )
        logger.info(f"Score diff {score_diff:2d}: noise={noise_score:.1f}")

    # Test scenario 6: Quarter progression
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Quarter progression")
    logger.info("="*60)

    for qtr in [1, 2, 3, 4, 5]:
        noise_score = estimate_crowd_noise(
            team='NO',
            is_home=True,
            situation='fourth_down',
            score_differential=3,
            quarter=qtr,
            is_offense_home=False
        )
        qtr_name = f'Q{qtr}' if qtr <= 4 else 'OT'
        logger.info(f"{qtr_name}: noise={noise_score:.1f}")

    # Test scenario 7: Stadium comparison
    logger.info("\n" + "="*60)
    logger.info("TEST 7: Stadium comparison (4th down, away offense, Q4, close game)")
    logger.info("="*60)

    test_stadiums = ['KC', 'SEA', 'NO', 'PHI', 'JAX']
    for stadium in test_stadiums:
        base = get_stadium_base_noise(stadium)
        modifier = calculate_crowd_modifier(
            team=stadium,
            is_offense_home=False,
            situation='fourth_down',
            score_differential=3,
            quarter=4,
            play_type='pass'
        )
        logger.info(f"{stadium:3s} (base={base:2d}): modifier={modifier:.3f}")
