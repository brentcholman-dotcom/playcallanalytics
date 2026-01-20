import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_weather_for_game(game_id, pbp_df=None):
    """
    Get weather data for a game. 
    In nflfastR, this is often in the 'weather' or specific 'temp', 'wind' columns if available.
    """
    # Stub: for now, we'll try to extract from pbp_df if provided, else return defaults
    weather = {
        'temp': 70,
        'wind_speed': 0,
        'wind_dir': None,
        'precipitation': 'None'
    }
    
    if pbp_df is not None:
        game_data = pbp_df[pbp_df['game_id'] == game_id].iloc[0] if not pbp_df[pbp_df['game_id'] == game_id].empty else {}
        if 'temp' in game_data: weather['temp'] = game_data['temp']
        if 'wind' in game_data: weather['wind_speed'] = game_data['wind']
        # nflfastR weather string parsing could be added here
        
    return weather

def calculate_weather_modifier(weather_dict, play_type, field_position=None, distance=None):
    """
    Calculates a probability multiplier based on weather factors.
    Returns 1.0 for no impact, < 1.0 for negative impact.
    """
    if not weather_dict:
        return 1.0
        
    modifier = 1.0
    temp = weather_dict.get('temp', 70)
    wind = weather_dict.get('wind_speed', 0)
    precip = weather_dict.get('precipitation', 'None')
    
    # 1. Wind Impact
    if wind >= 10:
        if play_type == 'field_goal':
            # Distance matters for FG wind impact
            fg_dist = (100 - field_position) + 17 if field_position else 45
            if wind < 15 and fg_dist > 45:
                modifier *= 0.97
            elif 15 <= wind < 20 and fg_dist > 40:
                modifier *= 0.92
            elif wind >= 20 and fg_dist > 35:
                modifier *= 0.85
        elif play_type == 'pass':
            # deep passes specifically, but let's assume general pass impact for simplicity
            if wind < 15:
                modifier *= 0.98
            elif 15 <= wind < 20:
                modifier *= 0.95
            elif wind >= 20:
                modifier *= 0.90

    # 2. Temperature Impact
    if temp < 32:
        if play_type == 'pass':
            modifier *= 0.98 # Ball harder to grip
    elif temp > 85:
        # Fatigue factor
        fatigue_penalty = (temp - 85) // 5 * 0.01
        modifier *= (1.0 - fatigue_penalty)

    # 3. Precipitation
    if precip == 'Rain':
        if play_type == 'pass': modifier *= 0.95
        if play_type == 'field_goal': modifier *= 0.98
    elif precip == 'Snow':
        if play_type == 'pass': modifier *= 0.92
        if play_type == 'field_goal': modifier *= 0.90
        
    return modifier

def get_play_type_from_row(row):
    """Helper to determine play type for weather calculation"""
    if row['play_type'] == 'field_goal':
        return 'field_goal'
    elif row['play_type'] == 'pass':
        return 'pass'
    elif row['play_type'] == 'run':
        return 'run'
    return 'other'
