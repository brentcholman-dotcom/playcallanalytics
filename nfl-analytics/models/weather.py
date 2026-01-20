"""
Weather Impact Model

This module calculates weather adjustments for play probabilities based on:
- Wind speed and direction (affects kicking and deep passing)
- Temperature (affects grip and fatigue)
- Precipitation (affects passing and kicking)
- Field type (grass vs turf)

Weather modifiers are returned as multipliers (1.0 = no impact, < 1.0 = negative impact)
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


def get_weather_for_game(game_data):
    """
    Extract weather information from game data.

    Args:
        game_data: DataFrame row or dict with game information
                   Expected columns: temp, wind, weather, roof, surface

    Returns:
        dict: Weather information with keys:
              - temperature (float): Temperature in Fahrenheit
              - wind_speed (float): Wind speed in mph
              - precipitation (str): 'none', 'rain', 'snow'
              - roof (str): 'outdoors', 'dome', 'closed', 'open'
              - surface (str): Field surface type
    """
    weather_dict = {
        'temperature': None,
        'wind_speed': None,
        'precipitation': 'none',
        'roof': 'outdoors',
        'surface': 'grass'
    }

    # Extract temperature
    if 'temp' in game_data:
        temp = game_data['temp']
        if pd.notna(temp):
            weather_dict['temperature'] = float(temp)

    # Extract wind speed
    if 'wind' in game_data:
        wind = game_data['wind']
        if pd.notna(wind):
            # Parse wind string (e.g., "10 mph", "15-20 mph")
            wind_speed = _parse_wind_speed(str(wind))
            if wind_speed is not None:
                weather_dict['wind_speed'] = wind_speed

    # Extract precipitation
    if 'weather' in game_data:
        weather = game_data['weather']
        if pd.notna(weather):
            weather_str = str(weather).lower()
            if 'rain' in weather_str or 'shower' in weather_str:
                weather_dict['precipitation'] = 'rain'
            elif 'snow' in weather_str or 'flurr' in weather_str:
                weather_dict['precipitation'] = 'snow'

    # Extract roof type
    if 'roof' in game_data:
        roof = game_data['roof']
        if pd.notna(roof):
            weather_dict['roof'] = str(roof).lower()

    # Extract surface type
    if 'surface' in game_data:
        surface = game_data['surface']
        if pd.notna(surface):
            weather_dict['surface'] = str(surface).lower()

    return weather_dict


def _parse_wind_speed(wind_str):
    """
    Parse wind speed from string.

    Args:
        wind_str: Wind string (e.g., "10 mph", "15-20 mph", "calm")

    Returns:
        float: Wind speed in mph, or None if cannot parse
    """
    try:
        wind_str = wind_str.lower()

        # Handle calm/no wind
        if 'calm' in wind_str or 'none' in wind_str:
            return 0.0

        # Extract numbers
        import re
        numbers = re.findall(r'\d+', wind_str)

        if numbers:
            # If range (e.g., "15-20"), take average
            if len(numbers) >= 2:
                return (float(numbers[0]) + float(numbers[1])) / 2
            else:
                return float(numbers[0])

        return None
    except:
        return None


def calculate_wind_impact(wind_speed, play_type, field_position):
    """
    Calculate wind impact on play success probability.

    Wind primarily affects:
    - Field goal attempts (more impact on longer kicks)
    - Deep passing plays

    Args:
        wind_speed: Wind speed in mph
        play_type: Type of play ('pass', 'run', 'field_goal', 'punt')
        field_position: Yards from goal line (for FG distance)

    Returns:
        float: Multiplier for probability (1.0 = no impact, < 1.0 = negative)
    """
    if pd.isna(wind_speed) or wind_speed is None:
        return 1.0

    # No significant impact below 10 mph
    if wind_speed < 10:
        return 1.0

    # Field goal impact (more severe on longer kicks)
    if play_type in ['field_goal', 'kicked_fg']:
        # Estimate FG distance (field position + 17 yards for end zone and holder)
        fg_distance = field_position + 17

        if wind_speed >= 20:
            if fg_distance > 35:
                return 0.85  # -15% on FG over 35 yards
        elif wind_speed >= 15:
            if fg_distance > 40:
                return 0.92  # -8% on FG over 40 yards
        elif wind_speed >= 10:
            if fg_distance > 45:
                return 0.97  # -3% on FG over 45 yards

    # Deep passing impact
    elif play_type == 'pass':
        if wind_speed >= 20:
            return 0.90  # -10% on deep passes
        elif wind_speed >= 15:
            return 0.95  # -5% on deep passes
        elif wind_speed >= 10:
            return 0.98  # -2% on deep passes

    # Punt impact (less critical for our 4th down analysis)
    elif play_type == 'punt':
        if wind_speed >= 20:
            return 0.95
        elif wind_speed >= 15:
            return 0.97

    return 1.0


def calculate_temperature_impact(temperature, play_type):
    """
    Calculate temperature impact on play success probability.

    Temperature affects:
    - Ball grip (cold weather makes passing harder)
    - Player fatigue (extreme heat reduces performance)

    Args:
        temperature: Temperature in Fahrenheit
        play_type: Type of play ('pass', 'run', 'field_goal', etc.)

    Returns:
        float: Multiplier for probability (1.0 = no impact)
    """
    if pd.isna(temperature) or temperature is None:
        return 1.0

    # Cold weather impact on passing
    if temperature < 32:
        if play_type == 'pass':
            return 0.98  # -2% on passing plays (harder grip)
        elif play_type in ['field_goal', 'kicked_fg']:
            return 0.98  # -2% on kicking (ball harder)

    # Extreme heat impact (fatigue)
    elif temperature > 85:
        # -1% per 5 degrees above 85
        excess_temp = temperature - 85
        penalty_pct = (excess_temp / 5) * 0.01
        return max(0.90, 1.0 - penalty_pct)  # Cap at -10%

    return 1.0


def calculate_precipitation_impact(precipitation, play_type):
    """
    Calculate precipitation impact on play success probability.

    Precipitation affects:
    - Passing (wet ball, poor visibility)
    - Kicking (wet ball, poor footing)

    Args:
        precipitation: Type of precipitation ('none', 'rain', 'snow')
        play_type: Type of play ('pass', 'run', 'field_goal', etc.)

    Returns:
        float: Multiplier for probability (1.0 = no impact)
    """
    if pd.isna(precipitation) or precipitation == 'none':
        return 1.0

    precipitation = str(precipitation).lower()

    # Rain impact
    if 'rain' in precipitation:
        if play_type == 'pass':
            return 0.95  # -5% on passing
        elif play_type in ['field_goal', 'kicked_fg']:
            return 0.98  # -2% on kicking

    # Snow impact (more severe)
    elif 'snow' in precipitation:
        if play_type == 'pass':
            return 0.92  # -8% on passing
        elif play_type in ['field_goal', 'kicked_fg']:
            return 0.90  # -10% on kicking

    return 1.0


def calculate_weather_modifier(weather_dict, play_type, field_position=50):
    """
    Calculate combined weather modifier for a play.

    Args:
        weather_dict: Dictionary with weather info (from get_weather_for_game)
        play_type: Type of play ('pass', 'run', 'field_goal', 'went_for_it', etc.)
        field_position: Yards from goal line (for FG calculations)

    Returns:
        float: Combined weather modifier (multiplier for probability)
               1.0 = no impact, < 1.0 = negative impact
    """
    # If playing indoors, weather doesn't matter
    if weather_dict.get('roof') in ['dome', 'closed']:
        return 1.0

    # Normalize play type
    play_type_normalized = str(play_type).lower()

    # Calculate individual impacts
    wind_modifier = calculate_wind_impact(
        weather_dict.get('wind_speed'),
        play_type_normalized,
        field_position
    )

    temp_modifier = calculate_temperature_impact(
        weather_dict.get('temperature'),
        play_type_normalized
    )

    precip_modifier = calculate_precipitation_impact(
        weather_dict.get('precipitation'),
        play_type_normalized
    )

    # Combine modifiers (multiplicative)
    combined_modifier = wind_modifier * temp_modifier * precip_modifier

    return combined_modifier


def add_weather_modifiers(plays_df):
    """
    Add weather modifier columns to plays dataframe.

    Args:
        plays_df: DataFrame with play data including weather columns

    Returns:
        DataFrame: Original dataframe with weather_modifier column added
    """
    logger.info("Adding weather modifiers to plays...")

    result = plays_df.copy()

    # Calculate weather modifier for each play
    def calculate_row_weather(row):
        # Get weather for this game
        weather = get_weather_for_game(row)

        # Get play type
        play_type = row.get('play_type', 'run')

        # Get field position (for FG calculations)
        field_pos = row.get('yardline_100', 50)

        # Calculate modifier
        modifier = calculate_weather_modifier(weather, play_type, field_pos)

        return modifier

    result['weather_modifier'] = result.apply(calculate_row_weather, axis=1)

    logger.info("Weather modifiers added")
    logger.info(f"  Mean modifier: {result['weather_modifier'].mean():.3f}")
    logger.info(f"  Min modifier: {result['weather_modifier'].min():.3f}")
    logger.info(f"  Plays with impact < 1.0: {(result['weather_modifier'] < 1.0).sum():,}")

    return result


def analyze_weather_impact(plays_df):
    """
    Analyze weather impact across different conditions.

    Args:
        plays_df: DataFrame with weather_modifier column

    Returns:
        DataFrame: Summary statistics by weather condition
    """
    if 'weather_modifier' not in plays_df.columns:
        logger.error("No weather_modifier column found")
        return pd.DataFrame()

    result = plays_df.copy()

    # Add weather condition categories
    result['has_wind'] = result['wind'].notna() & (result['wind'].str.contains('mph', na=False))
    result['has_rain'] = result['weather'].notna() & (result['weather'].str.contains('rain|shower', case=False, na=False))
    result['has_snow'] = result['weather'].notna() & (result['weather'].str.contains('snow|flurr', case=False, na=False))
    result['is_cold'] = result['temp'].notna() & (result['temp'] < 32)
    result['is_hot'] = result['temp'].notna() & (result['temp'] > 85)
    result['is_dome'] = result['roof'].notna() & (result['roof'].isin(['dome', 'closed']))

    # Analyze by condition
    conditions = {
        'All Plays': result,
        'Windy': result[result['has_wind']],
        'Rain': result[result['has_rain']],
        'Snow': result[result['has_snow']],
        'Cold': result[result['is_cold']],
        'Hot': result[result['is_hot']],
        'Dome': result[result['is_dome']],
        'Outdoor': result[~result['is_dome']]
    }

    summary = []
    for condition_name, condition_df in conditions.items():
        if len(condition_df) > 0:
            summary.append({
                'condition': condition_name,
                'plays': len(condition_df),
                'mean_modifier': condition_df['weather_modifier'].mean(),
                'min_modifier': condition_df['weather_modifier'].min(),
                'pct_impacted': (condition_df['weather_modifier'] < 1.0).mean() * 100
            })

    return pd.DataFrame(summary)


def calculate_weather_impact(temperature=None, wind_speed=None, precipitation=None, field_type=None):
    """
    Legacy function for backward compatibility.

    Args:
        temperature: Temperature in Fahrenheit
        wind_speed: Wind speed in mph
        precipitation: Precipitation level (0-1) or type
        field_type: 'grass' or 'turf'

    Returns:
        float: Weather adjustment factor (multiplier)
    """
    # Create weather dict from parameters
    weather_dict = {
        'temperature': temperature,
        'wind_speed': wind_speed,
        'precipitation': 'rain' if precipitation else 'none',
        'roof': 'outdoors',
        'surface': field_type if field_type else 'grass'
    }

    # Use generic play type (run has minimal weather impact)
    return calculate_weather_modifier(weather_dict, 'run', 50)


if __name__ == "__main__":
    """
    Test weather impact calculations.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from ingestion.play_by_play import load_pbp_data

    logger.info("="*60)
    logger.info("WEATHER IMPACT TEST")
    logger.info("="*60)

    # Load sample data
    logger.info("Loading 2023 season...")
    pbp = load_pbp_data(seasons=[2023])

    # Get first game with weather data
    games_with_weather = pbp[pbp['temp'].notna() | pbp['wind'].notna()]
    if not games_with_weather.empty:
        first_game = games_with_weather['game_id'].iloc[0]
        game = pbp[pbp['game_id'] == first_game].copy()

        logger.info(f"\nProcessing game: {first_game}")

        # Show weather conditions
        weather = get_weather_for_game(game.iloc[0])
        logger.info(f"Weather conditions:")
        for key, value in weather.items():
            logger.info(f"  {key}: {value}")

        # Add weather modifiers
        game_with_weather = add_weather_modifiers(game)

        # Show examples
        logger.info("\nExample plays with weather impact:")
        display_cols = [
            'play_type', 'temp', 'wind',
            'yardline_100', 'weather_modifier'
        ]
        available_cols = [col for col in display_cols if col in game_with_weather.columns]
        print(game_with_weather[available_cols].head(20))

        # Analyze distribution
        logger.info("\n" + "="*60)
        logger.info("WEATHER IMPACT ANALYSIS")
        logger.info("="*60)
        summary = analyze_weather_impact(game_with_weather)
        print(summary)
    else:
        logger.info("No games with weather data found")
