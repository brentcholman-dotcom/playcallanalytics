"""
Injury Impact Model

This module calculates the impact of player injuries on 4th down conversion
probabilities, accounting for position importance by situation and player quality.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# POSITION WEIGHTS BY SITUATION (DEFENSIVE)
# ==============================================================================

# 4th and short (1-2 yards) - interior defenders most important
DEFENSIVE_WEIGHTS_SHORT = {
    'DT': 0.8, 'NT': 0.8,          # Interior line critical for stuffing
    'MLB': 0.8, 'ILB': 0.8,        # Linebackers fill gaps
    'EDGE': 0.5, 'OLB': 0.5,       # Edge less critical in short yardage
    'SS': 0.5, 'FS': 0.4,          # Safeties provide run support
    'CB': 0.2                       # Corners least important
}

# 4th and medium (3-5 yards) - balanced impact
DEFENSIVE_WEIGHTS_MEDIUM = {
    'MLB': 0.8, 'ILB': 0.8,        # Linebackers cover most zones
    'EDGE': 0.7, 'OLB': 0.7,       # Pass rush becomes important
    'CB': 0.6,                      # Coverage matters
    'SS': 0.5, 'FS': 0.5,          # Safety help
    'DT': 0.5, 'NT': 0.5           # Interior still relevant
}

# 4th and long (6+ yards) - coverage positions most important
DEFENSIVE_WEIGHTS_LONG = {
    'CB': 0.9,                      # Corners critical in coverage
    'EDGE': 0.8, 'OLB': 0.8,       # Pass rush very important
    'FS': 0.7, 'SS': 0.7,          # Safeties provide deep coverage
    'MLB': 0.5, 'ILB': 0.5,        # Linebackers less critical
    'DT': 0.3, 'NT': 0.3           # Interior line least important
}

# ==============================================================================
# POSITION WEIGHTS BY SITUATION (OFFENSIVE)
# ==============================================================================

# 4th and short (1-2 yards) - power positions most important
OFFENSIVE_WEIGHTS_SHORT = {
    'RB': 0.8,                      # Running back most critical
    'C': 0.8,                       # Center controls point of attack
    'OG': 0.7,                      # Guards drive block
    'FB': 0.6, 'TE': 0.6,          # Blocking help
    'OT': 0.5,                      # Tackles less critical
    'QB': 0.4,                      # QB less critical in short yardage
    'WR': 0.2                       # Receivers least important
}

# 4th and medium (3-5 yards) - balanced attack
OFFENSIVE_WEIGHTS_MEDIUM = {
    'QB': 0.8,                      # QB becomes more important
    'RB': 0.7,                      # RB still relevant
    'WR': 0.7, 'TE': 0.7,          # Pass catchers important
    'OT': 0.6,                      # Pass protection matters
    'C': 0.6, 'OG': 0.6,           # Interior line balanced
    'FB': 0.3                       # Fullback less used
}

# 4th and long (6+ yards) - passing game positions
OFFENSIVE_WEIGHTS_LONG = {
    'QB': 0.9,                      # QB critical
    'WR': 0.8,                      # Wide receivers most important
    'OT': 0.7,                      # Pass protection critical
    'TE': 0.6,                      # Tight end as receiver
    'C': 0.5, 'OG': 0.5,           # Interior pass protection
    'RB': 0.4,                      # RB for checkdowns/protection
    'FB': 0.2                       # Fullback rarely used
}


# ==============================================================================
# PLAYER QUALITY TIERS
# ==============================================================================

class PlayerTier(Enum):
    """Player quality tier enum."""
    STARTER = 1.0
    QUALITY_BACKUP = 0.8
    DEPTH = 0.6
    PRACTICE_SQUAD = 0.4


# QB injury impact lookup table
QB_INJURY_IMPACT = {
    ('STARTER', 'QUALITY_BACKUP'): -0.20,      # -20% with quality backup
    ('STARTER', 'DEPTH'): -0.40,               # -40% with depth backup
    ('STARTER', 'PRACTICE_SQUAD'): -0.60,      # -60% with practice squad
    ('QUALITY_BACKUP', 'DEPTH'): -0.20,        # -20% losing backup
    ('QUALITY_BACKUP', 'PRACTICE_SQUAD'): -0.35,  # -35%
    ('DEPTH', 'PRACTICE_SQUAD'): -0.15,        # -15%
}

# OL shuffle penalty multipliers
OL_SHUFFLE_PENALTY = {
    0: 1.0,    # No backups, no penalty
    1: 1.0,    # One backup, no additional penalty
    2: 1.3,    # Two backups, 30% more impact
    3: 1.6,    # Three+ backups, 60% more impact
}


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class InjuredPlayer:
    """Represents an injured player."""
    name: str
    position: str
    starter_tier: PlayerTier
    backup_tier: PlayerTier
    side: str  # 'offense' or 'defense'

    def __post_init__(self):
        """Validate and normalize data."""
        self.position = self.position.upper()
        self.side = self.side.lower()

        # Convert string tiers to PlayerTier enum if needed
        if isinstance(self.starter_tier, str):
            self.starter_tier = PlayerTier[self.starter_tier.upper().replace(' ', '_')]
        if isinstance(self.backup_tier, str):
            self.backup_tier = PlayerTier[self.backup_tier.upper().replace(' ', '_')]


# ==============================================================================
# INJURY TRACKER CLASS
# ==============================================================================

class InjuryTracker:
    """
    Tracks current injury state for both teams.
    """

    def __init__(self):
        """Initialize empty injury tracker."""
        self.offensive_injuries: List[InjuredPlayer] = []
        self.defensive_injuries: List[InjuredPlayer] = []

    def add_injury(self, injured_player: InjuredPlayer):
        """
        Add an injury to the tracker.

        Args:
            injured_player: InjuredPlayer instance
        """
        if injured_player.side == 'offense':
            self.offensive_injuries.append(injured_player)
            logger.debug(f"Added offensive injury: {injured_player.name} ({injured_player.position})")
        elif injured_player.side == 'defense':
            self.defensive_injuries.append(injured_player)
            logger.debug(f"Added defensive injury: {injured_player.name} ({injured_player.position})")
        else:
            logger.warning(f"Unknown side '{injured_player.side}' for {injured_player.name}")

    def remove_injury(self, player_name: str, side: str):
        """
        Remove an injury (player returns).

        Args:
            player_name: Name of player
            side: 'offense' or 'defense'
        """
        side = side.lower()
        if side == 'offense':
            self.offensive_injuries = [
                p for p in self.offensive_injuries if p.name != player_name
            ]
            logger.debug(f"Removed offensive injury: {player_name}")
        elif side == 'defense':
            self.defensive_injuries = [
                p for p in self.defensive_injuries if p.name != player_name
            ]
            logger.debug(f"Removed defensive injury: {player_name}")

    def clear_all(self):
        """Clear all injuries."""
        self.offensive_injuries = []
        self.defensive_injuries = []
        logger.debug("Cleared all injuries")

    def get_injury_count(self, side: str) -> int:
        """
        Get count of injuries on one side.

        Args:
            side: 'offense' or 'defense'

        Returns:
            int: Number of injured players
        """
        side = side.lower()
        if side == 'offense':
            return len(self.offensive_injuries)
        elif side == 'defense':
            return len(self.defensive_injuries)
        return 0

    def get_injuries_by_position(self, side: str) -> Dict[str, int]:
        """
        Get injury counts by position.

        Args:
            side: 'offense' or 'defense'

        Returns:
            dict: Position -> count
        """
        side = side.lower()
        injuries = self.offensive_injuries if side == 'offense' else self.defensive_injuries

        position_counts = {}
        for injury in injuries:
            pos = injury.position
            position_counts[pos] = position_counts.get(pos, 0) + 1

        return position_counts


# ==============================================================================
# IMPACT CALCULATION FUNCTIONS
# ==============================================================================

def get_defensive_weights(yards_to_go: int) -> Dict[str, float]:
    """
    Get defensive position weights based on yards to go.

    Args:
        yards_to_go: Yards needed for first down

    Returns:
        dict: Position -> weight
    """
    if yards_to_go <= 2:
        return DEFENSIVE_WEIGHTS_SHORT
    elif yards_to_go <= 5:
        return DEFENSIVE_WEIGHTS_MEDIUM
    else:
        return DEFENSIVE_WEIGHTS_LONG


def get_offensive_weights(yards_to_go: int) -> Dict[str, float]:
    """
    Get offensive position weights based on yards to go.

    Args:
        yards_to_go: Yards needed for first down

    Returns:
        dict: Position -> weight
    """
    if yards_to_go <= 2:
        return OFFENSIVE_WEIGHTS_SHORT
    elif yards_to_go <= 5:
        return OFFENSIVE_WEIGHTS_MEDIUM
    else:
        return OFFENSIVE_WEIGHTS_LONG


def calculate_single_injury_impact(
    injured_player: InjuredPlayer,
    position_weights: Dict[str, float]
) -> float:
    """
    Calculate impact of a single injury.

    Args:
        injured_player: InjuredPlayer instance
        position_weights: Position weight dictionary for current situation

    Returns:
        float: Impact value
    """
    position = injured_player.position
    position_weight = position_weights.get(position, 0.0)

    # Calculate tier difference
    starter_value = injured_player.starter_tier.value
    backup_value = injured_player.backup_tier.value
    tier_diff = starter_value - backup_value

    # Impact = position_weight * tier_difference * 0.1
    impact = position_weight * tier_diff * 0.1

    return impact


def calculate_qb_injury_impact(injured_player: InjuredPlayer) -> float:
    """
    Calculate QB injury impact using lookup table.

    Args:
        injured_player: InjuredPlayer with position 'QB'

    Returns:
        float: QB injury impact (negative)
    """
    starter_tier = injured_player.starter_tier.name
    backup_tier = injured_player.backup_tier.name

    key = (starter_tier, backup_tier)
    impact = QB_INJURY_IMPACT.get(key, -0.30)  # Default -30% if not in table

    return impact


def calculate_ol_shuffle_penalty(offensive_injuries: List[InjuredPlayer]) -> float:
    """
    Calculate OL shuffle penalty multiplier.

    Args:
        offensive_injuries: List of offensive injured players

    Returns:
        float: Multiplier (1.0 = no penalty, >1.0 = penalty)
    """
    # Count OL positions playing backups
    ol_positions = {'OT', 'OG', 'C'}
    ol_backup_count = 0

    for injury in offensive_injuries:
        if injury.position in ol_positions:
            # Only count if backup is actually playing (not starter)
            if injury.backup_tier != PlayerTier.STARTER:
                ol_backup_count += 1

    # Apply penalty based on count
    if ol_backup_count >= 3:
        return OL_SHUFFLE_PENALTY[3]
    else:
        return OL_SHUFFLE_PENALTY.get(ol_backup_count, 1.0)


def calculate_defensive_injury_modifier(
    injuries: List[InjuredPlayer],
    yards_to_go: int
) -> float:
    """
    Calculate defensive injury modifier (helps offense when positive).

    Args:
        injuries: List of defensive injured players
        yards_to_go: Yards needed for first down

    Returns:
        float: Defensive injury modifier (positive helps offense)
    """
    if not injuries:
        return 0.0

    # Get appropriate position weights
    position_weights = get_defensive_weights(yards_to_go)

    # Calculate total impact
    total_impact = 0.0
    for injury in injuries:
        impact = calculate_single_injury_impact(injury, position_weights)
        total_impact += impact
        logger.debug(f"  {injury.position} injury impact: +{impact:.3f}")

    logger.info(f"Defensive injury modifier: +{total_impact:.3f} (helps offense)")
    return total_impact


def calculate_offensive_injury_modifier(
    injuries: List[InjuredPlayer],
    yards_to_go: int
) -> float:
    """
    Calculate offensive injury modifier (hurts offense when negative).

    Args:
        injuries: List of offensive injured players
        yards_to_go: Yards needed for first down

    Returns:
        float: Offensive injury modifier (negative hurts offense)
    """
    if not injuries:
        return 0.0

    # Get appropriate position weights
    position_weights = get_offensive_weights(yards_to_go)

    # Calculate total impact
    total_impact = 0.0
    qb_injury_handled = False

    for injury in injuries:
        # Special case: QB uses lookup table
        if injury.position == 'QB' and not qb_injury_handled:
            impact = calculate_qb_injury_impact(injury)
            qb_injury_handled = True
            logger.debug(f"  QB injury impact: {impact:.3f}")
        else:
            # Normal calculation
            impact = calculate_single_injury_impact(injury, position_weights)
            impact = -impact  # Negative for offense
            logger.debug(f"  {injury.position} injury impact: {impact:.3f}")

        total_impact += impact

    # Apply OL shuffle penalty if applicable
    ol_penalty = calculate_ol_shuffle_penalty(injuries)
    if ol_penalty > 1.0:
        # Only apply penalty to OL impacts
        ol_positions = {'OT', 'OG', 'C'}
        ol_impact = sum(
            -calculate_single_injury_impact(inj, position_weights)
            for inj in injuries
            if inj.position in ol_positions and inj.position != 'QB'
        )
        penalty_addition = ol_impact * (ol_penalty - 1.0)
        total_impact += penalty_addition
        logger.debug(f"  OL shuffle penalty: {penalty_addition:.3f} (multiplier: {ol_penalty}x)")

    logger.info(f"Offensive injury modifier: {total_impact:.3f} (hurts offense)")
    return total_impact


def calculate_net_injury_modifier(
    def_injuries: List[InjuredPlayer],
    off_injuries: List[InjuredPlayer],
    yards_to_go: int
) -> float:
    """
    Calculate net injury modifier combining both sides.

    Args:
        def_injuries: List of defensive injured players
        off_injuries: List of offensive injured players
        yards_to_go: Yards needed for first down

    Returns:
        float: Net injury modifier (positive helps offense, negative hurts)
    """
    logger.info(f"Calculating net injury modifier (yards to go: {yards_to_go})")

    # Calculate each side
    defensive_modifier = calculate_defensive_injury_modifier(def_injuries, yards_to_go)
    offensive_modifier = calculate_offensive_injury_modifier(off_injuries, yards_to_go)

    # Net = defensive injuries help offense + offensive injuries hurt offense
    net_modifier = defensive_modifier + offensive_modifier

    logger.info(f"Net injury modifier: {net_modifier:+.3f}")
    return net_modifier


def calculate_injury_modifier_multiplier(
    def_injuries: List[InjuredPlayer],
    off_injuries: List[InjuredPlayer],
    yards_to_go: int
) -> float:
    """
    Calculate injury modifier as multiplier (for consistency with other models).

    Args:
        def_injuries: List of defensive injured players
        off_injuries: List of offensive injured players
        yards_to_go: Yards needed for first down

    Returns:
        float: Injury multiplier (1.0 = no impact, >1.0 = helps, <1.0 = hurts)
    """
    net_modifier = calculate_net_injury_modifier(def_injuries, off_injuries, yards_to_go)

    # Convert to multiplier
    multiplier = 1.0 + net_modifier

    return multiplier


# ==============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ==============================================================================

def calculate_injury_impact(injured_players, position_importance):
    """
    Legacy function for backward compatibility.

    Note: Use calculate_net_injury_modifier() for new code.

    Args:
        injured_players: List of injured player data
        position_importance: Dict of position weights

    Returns:
        float: Injury impact factor (0.0 to 1.0)
    """
    logger.warning("calculate_injury_impact() is deprecated")

    if not injured_players:
        return 1.0

    # Simple calculation
    total_impact = 0.0
    for player in injured_players:
        pos = player.get('position', 'UNKNOWN')
        weight = position_importance.get(pos, 0.0)
        total_impact += weight * 0.1

    # Normalize to 0-1 scale
    impact_factor = max(0.0, 1.0 - total_impact)
    return impact_factor


def assess_position_depth(team_roster, injuries):
    """
    Legacy function for backward compatibility.

    Note: Use InjuryTracker class for new code.

    Args:
        team_roster: Team roster data
        injuries: Current injury list

    Returns:
        dict: Position-specific impact scores
    """
    logger.warning("assess_position_depth() is deprecated")

    position_impact = {}
    for injury in injuries:
        pos = injury.get('position', 'UNKNOWN')
        position_impact[pos] = position_impact.get(pos, 0) + 1

    return position_impact


# ==============================================================================
# TESTING
# ==============================================================================

if __name__ == "__main__":
    """
    Test injury impact calculations.
    """
    logger.info("="*60)
    logger.info("INJURY IMPACT MODEL TEST")
    logger.info("="*60)

    # Create injury tracker
    tracker = InjuryTracker()

    # Test scenario 1: 4th and 1 with defensive DT injury
    logger.info("\n" + "="*60)
    logger.info("TEST 1: 4th and 1 with defensive DT injury")
    logger.info("="*60)

    dt_injury = InjuredPlayer(
        name="John Doe",
        position="DT",
        starter_tier=PlayerTier.STARTER,
        backup_tier=PlayerTier.DEPTH,
        side="defense"
    )
    tracker.add_injury(dt_injury)

    modifier = calculate_net_injury_modifier(
        def_injuries=tracker.defensive_injuries,
        off_injuries=tracker.offensive_injuries,
        yards_to_go=1
    )
    multiplier = calculate_injury_modifier_multiplier(
        tracker.defensive_injuries, tracker.offensive_injuries, 1
    )
    logger.info(f"Result: modifier={modifier:+.3f}, multiplier={multiplier:.3f}")

    # Test scenario 2: 4th and 10 with offensive QB and WR injuries
    logger.info("\n" + "="*60)
    logger.info("TEST 2: 4th and 10 with QB and WR injuries")
    logger.info("="*60)

    tracker.clear_all()

    qb_injury = InjuredPlayer(
        name="Tom Brady",
        position="QB",
        starter_tier=PlayerTier.STARTER,
        backup_tier=PlayerTier.QUALITY_BACKUP,
        side="offense"
    )
    wr_injury = InjuredPlayer(
        name="Jerry Rice",
        position="WR",
        starter_tier=PlayerTier.STARTER,
        backup_tier=PlayerTier.DEPTH,
        side="offense"
    )
    tracker.add_injury(qb_injury)
    tracker.add_injury(wr_injury)

    modifier = calculate_net_injury_modifier(
        def_injuries=tracker.defensive_injuries,
        off_injuries=tracker.offensive_injuries,
        yards_to_go=10
    )
    multiplier = calculate_injury_modifier_multiplier(
        tracker.defensive_injuries, tracker.offensive_injuries, 10
    )
    logger.info(f"Result: modifier={modifier:+.3f}, multiplier={multiplier:.3f}")

    # Test scenario 3: OL shuffle penalty (3 OL backups)
    logger.info("\n" + "="*60)
    logger.info("TEST 3: 4th and 2 with 3 OL backup injuries")
    logger.info("="*60)

    tracker.clear_all()

    for i, pos in enumerate(['OT', 'OG', 'C']):
        injury = InjuredPlayer(
            name=f"Lineman {i+1}",
            position=pos,
            starter_tier=PlayerTier.STARTER,
            backup_tier=PlayerTier.DEPTH,
            side="offense"
        )
        tracker.add_injury(injury)

    modifier = calculate_net_injury_modifier(
        def_injuries=tracker.defensive_injuries,
        off_injuries=tracker.offensive_injuries,
        yards_to_go=2
    )
    multiplier = calculate_injury_modifier_multiplier(
        tracker.defensive_injuries, tracker.offensive_injuries, 2
    )
    logger.info(f"Result: modifier={modifier:+.3f}, multiplier={multiplier:.3f}")

    # Test scenario 4: Both sides have injuries
    logger.info("\n" + "="*60)
    logger.info("TEST 4: 4th and 5 with injuries on both sides")
    logger.info("="*60)

    tracker.clear_all()

    # Defensive injuries
    cb_injury = InjuredPlayer(
        name="Deion Sanders",
        position="CB",
        starter_tier=PlayerTier.STARTER,
        backup_tier=PlayerTier.QUALITY_BACKUP,
        side="defense"
    )
    edge_injury = InjuredPlayer(
        name="Lawrence Taylor",
        position="EDGE",
        starter_tier=PlayerTier.STARTER,
        backup_tier=PlayerTier.DEPTH,
        side="defense"
    )

    # Offensive injury
    te_injury = InjuredPlayer(
        name="Rob Gronkowski",
        position="TE",
        starter_tier=PlayerTier.STARTER,
        backup_tier=PlayerTier.DEPTH,
        side="offense"
    )

    tracker.add_injury(cb_injury)
    tracker.add_injury(edge_injury)
    tracker.add_injury(te_injury)

    modifier = calculate_net_injury_modifier(
        def_injuries=tracker.defensive_injuries,
        off_injuries=tracker.offensive_injuries,
        yards_to_go=5
    )
    multiplier = calculate_injury_modifier_multiplier(
        tracker.defensive_injuries, tracker.offensive_injuries, 5
    )
    logger.info(f"Result: modifier={modifier:+.3f}, multiplier={multiplier:.3f}")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("INJURY TRACKER SUMMARY")
    logger.info("="*60)
    logger.info(f"Total offensive injuries: {tracker.get_injury_count('offense')}")
    logger.info(f"Total defensive injuries: {tracker.get_injury_count('defense')}")
    logger.info(f"Offensive injuries by position: {tracker.get_injuries_by_position('offense')}")
    logger.info(f"Defensive injuries by position: {tracker.get_injuries_by_position('defense')}")
