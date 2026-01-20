import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STADIUM_NOISE = {
    'KC': 98, 'SEA': 96, 'NO': 95, 'PHI': 88, 'BAL': 86,
    'GB': 85, 'BUF': 85, 'CIN': 82, 'DEN': 82, 'MIN': 80,
    # Defaults for others
    'NE': 80, 'PIT': 84, 'CLE': 82, 'DAL': 85, 'SF': 84,
    'LAR': 78, 'LAC': 75, 'LV': 82, 'TEN': 80, 'IND': 82,
    'JAX': 78, 'HOU': 78, 'MIA': 80, 'NYJ': 80, 'NYG': 80,
    'CHI': 82, 'DET': 85, 'TB': 80, 'ATL': 80, 'CAR': 78,
    'ARI': 78, 'WAS': 75
}

def estimate_crowd_noise(game_context):
    """
    Proxy estimation formula for crowd noise.
    """
    team = game_context.get('defteam', 'DEFAULT')
    base = STADIUM_NOISE.get(team, 75)
    
    # 1.0 if away offense, 0.0 if home offense
    home_away_factor = 1.0 if game_context.get('posteam_type') == 'away' else 0.1
    
    # situation_intensity
    down = game_context.get('down', 1)
    if down == 4:
        intensity = 1.0
    elif down == 3:
        intensity = 0.7
    else:
        intensity = 0.3
        
    # game_state (closeness)
    score_diff = abs(game_context.get('score_differential', 0))
    if score_diff <= 7: state_factor = 1.0
    elif score_diff <= 14: state_factor = 0.75
    elif score_diff <= 21: state_factor = 0.5
    else: state_factor = 0.3
    
    # quarter_factor
    q = game_context.get('quarter', 1)
    q_factors = {1: 0.7, 2: 0.8, 3: 0.85, 4: 1.0, 5: 1.1} # 5 is OT
    q_factor = q_factors.get(q, 0.8)
    
    estimated_noise = base * home_away_factor * intensity * state_factor * q_factor
    # Normalize to 0-100 for conversion (the factors above can make it small, 
    # but the base is what we start with for "top" noise)
    # Re-evaluating: the base reflects peak noise. Let's make it a score.
    
    return min(100, estimated_noise + 60) # roughly mapping to dB range

def db_to_impact(decibels):
    """
    Converts decibels to a probability multiplier penalty.
    """
    if decibels < 70: return 0.0
    if decibels < 85: return -0.01
    if decibels < 100: return -0.03
    if decibels < 110: return -0.05
    if decibels < 120: return -0.08
    if decibels < 130: return -0.11
    return -0.13

def calculate_crowd_modifier(game_context, actual_db=None):
    """
    Calculates the crowd modifier impact.
    """
    db = actual_db if actual_db is not None else estimate_crowd_noise(game_context)
    base_impact = db_to_impact(db)
    
    # Play type adjustment
    play_type = game_context.get('play_type', 'pass')
    if play_type == 'pass':
        return base_impact
    elif play_type == 'run':
        return base_impact * 0.5
    elif 'sneak' in game_context.get('desc', '').lower():
        return base_impact * 0.25
    
    return base_impact

class CrowdNoiseTracker:
    def __init__(self):
        self.current_db = None
        self.last_timestamp = 0

    def set_db_reading(self, decibels):
        import time
        self.current_db = decibels
        self.last_timestamp = time.time()
        logger.info(f"Updated dB reading: {decibels}")

    def get_current_estimate(self, game_context):
        import time
        if self.current_db is not None and not self.is_reading_stale():
            return self.current_db
        return estimate_crowd_noise(game_context)

    def is_reading_stale(self, max_age_seconds=90):
        import time
        return (time.time() - self.last_timestamp) > max_age_seconds

if __name__ == "__main__":
    import sys
    import time
    if len(sys.argv) > 2 and sys.argv[1] == "set":
        db = float(sys.argv[2])
        # In a real app, this would update a shared state
        print(f"Setting crowd noise to {db} dB")
