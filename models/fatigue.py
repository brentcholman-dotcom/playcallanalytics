import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_fatigue_score(consecutive_plays, top_minutes, temp=70):
    """
    Core fatigue calculation.
    """
    base_fatigue = (consecutive_plays * 0.3) + (top_minutes * 0.5)
    temp_modifier = 1.0 + max(0, (temp - 85) * 0.02)
    return base_fatigue * temp_modifier

def score_to_impact(fatigue_score):
    """
    Converts fatigue score to a probability modifier (percentage).
    """
    if fatigue_score < 5:
        return 0.0
    elif fatigue_score < 10:
        return 0.015
    elif fatigue_score < 15:
        return 0.03
    elif fatigue_score < 20:
        return 0.05
    else:
        return 0.07

def calculate_defensive_fatigue(game_context):
    """
    Calculates defensive fatigue impact (positive, helps offense).
    """
    # Extract values from game_context
    # plays_this_drive can be a proxy for consecutive_plays
    consecutive_plays = game_context.get('plays_this_drive', 1)
    # top_against_minutes (proxied by drive time or similar)
    # nflfastR has drive_time_spent
    top_minutes = 5.0 # Stub for now
    temp = game_context.get('temp', 70)
    
    score = calculate_fatigue_score(consecutive_plays, top_minutes, temp)
    
    # Timeout reset logic
    # If defense called timeout last, reduce score by 50%
    if game_context.get('last_timeout_team') == game_context.get('defteam'):
        score *= 0.5
        
    return score_to_impact(score)

def calculate_offensive_fatigue(game_context):
    """
    Calculates offensive fatigue impact (negative, hurts offense).
    """
    # Similar to defensive but for the posteam
    consecutive_plays = game_context.get('plays_this_drive', 1)
    top_minutes = 5.0 # Stub
    temp = game_context.get('temp', 70)
    
    score = calculate_fatigue_score(consecutive_plays, top_minutes, temp)
    
    # Timeout logic for offense
    if game_context.get('last_timeout_team') == game_context.get('posteam'):
        score *= 0.5
        
    return -score_to_impact(score)

def calculate_net_fatigue_modifier(game_context):
    """
    Combines off/def fatigue into a single net modifier.
    """
    def_impact = calculate_defensive_fatigue(game_context)
    off_impact = calculate_offensive_fatigue(game_context)
    return def_impact + off_impact
