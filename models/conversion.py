import pandas as pd
import numpy as np
import logging
import os

from models.momentum import calculate_momentum
from models.weather import calculate_weather_modifier
from models.fatigue import calculate_net_fatigue_modifier
from models.injuries import calculate_net_injury_modifier
from models.crowd_noise import calculate_crowd_modifier

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_field_zone(yardline_100):
    if yardline_100 >= 80: return 'own_20'
    if yardline_100 >= 50: return 'own_half'
    if yardline_100 >= 21: return 'opp_half'
    return 'red_zone'

def build_base_rate_table(pbp_df):
    """
    Builds a lookup table for historical 4th down conversion rates.
    """
    logger.info("Building base rate table from historical data...")
    # Filter to 4th down "went for it" plays
    went_for_it = pbp_df[pbp_df['decision'] == 'went_for_it'].copy()
    
    # Add field zone
    went_for_it['field_zone'] = went_for_it['yardline_100'].apply(get_field_zone)
    
    # Calculate rates by yards to go and field zone
    rates = went_for_it.groupby(['ydstogo', 'field_zone'])['converted'].mean().to_dict()
    
    # Fill in some defaults if data is sparse
    # Typically 4th & 1 is ~70%, 4th & 10 is ~30%
    return rates

class ConversionModel:
    def __init__(self, base_rate_table=None):
        self.base_rate_table = base_rate_table or {}

    def get_base_rate(self, ydstogo, yardline_100):
        zone = get_field_zone(yardline_100)
        rate = self.base_rate_table.get((ydstogo, zone))
        
        if rate is None:
            # Fallback logic if specific combo doesn't exist
            # Basic decay: 0.70 for 1 yard, dropping as yards increase
            rate = max(0.1, 0.75 - (ydstogo * 0.05))
            
        return rate

    def calculate_conversion_probability(self, game_context, injuries=None, weather=None, crowd_db=None):
        """
        Brings all modifiers together.
        """
        ydstogo = game_context.get('ydstogo', 1)
        yardline_100 = game_context.get('yardline_100', 50)
        
        base_rate = self.get_base_rate(ydstogo, yardline_100)
        
        # 1. Momentum Modifier
        # (momentum_score - 50) / 500
        m_score = game_context.get('momentum_score', 50)
        momentum_mod = (m_score - 50) / 500.0
        
        # 2. Weather Modifier
        # weather_mod is typically a multiplier like 0.95 (meaning -5% relative)
        # But instructions say: (1 + momentum_mod + weather_mod + ...)
        # So we should convert multipliers to relative changes.
        w_mult = calculate_weather_modifier(weather, game_context.get('play_type', 'pass'), yardline_100)
        weather_mod = w_mult - 1.0
        
        # 3. Fatigue Modifier
        fatigue_mod = calculate_net_fatigue_modifier(game_context)
        
        # 4. Injury Modifier
        if injuries:
            off_inj = injuries.get('offense', [])
            def_inj = injuries.get('defense', [])
            injury_mod = calculate_net_injury_modifier(def_inj, off_inj, ydstogo)
        else:
            injury_mod = 0.0
            
        # 5. Crowd Modifier
        crowd_mod = calculate_crowd_modifier(game_context, actual_db=crowd_db)
        
        # Combined
        total_mod = 1.0 + momentum_mod + weather_mod + fatigue_mod + injury_mod + crowd_mod
        final_prob = base_rate * total_mod
        
        # Clamp
        final_prob = max(0.05, min(0.95, final_prob))
        
        return {
            'base_rate': base_rate,
            'momentum_modifier': momentum_mod,
            'weather_modifier': weather_mod,
            'fatigue_modifier': fatigue_mod,
            'injury_modifier': injury_mod,
            'crowd_modifier': crowd_mod,
            'final_probability': final_prob,
            'confidence': 'high' if base_rate > 0 else 'low'
        }
