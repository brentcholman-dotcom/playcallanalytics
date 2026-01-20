import pandas as pd
import numpy as np
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_momentum(row, team_season_averages=None):
    """
    Calculates Momentum Score (0-100) for the offensive team (posteam) on a given play.
    
    COMPONENTS:
    1. Recent play success (40% weight)
       - Scale: 0% success = 0 points, 100% success = 40 points
    2. Drive efficiency vs season average (25% weight)
       - If 50% better than average = 25 points
       - If at average = 12.5 points
       - If 50% worse = 0 points
    3. Scoring recency (20% weight)
       - Scored in last 2 mins = 20 points
       - Scored in last 5 mins = 15 points
       - Scored in last 10 mins = 10 points
       - No recent score = 5 points
    4. Turnover impact (15% weight)
       - Opponent turnover in last 5 plays = 15 points
       - Own turnover in last 5 plays = 0 points
       - No recent turnovers = 7.5 points
    """
    
    score = 0
    
    # 1. Recent play success (40%)
    success_rate = row.get('recent_success_rate', 0.5) # Default to 50% if unknown
    score += success_rate * 40
    
    # 2. Drive efficiency vs season average (25%)
    # For now, let's assume season average is 5.0 yards/play if not provided
    avg_eff = 5.0
    if team_season_averages and row['posteam'] in team_season_averages:
        avg_eff = team_season_averages[row['posteam']]
        
    current_eff = row.get('drive_efficiency', avg_eff)
    eff_ratio = current_eff / avg_eff if avg_eff > 0 else 1.0
    
    # Scale: 1.5 ratio = 25 pts, 1.0 ratio = 12.5 pts, 0.5 ratio = 0 pts
    eff_points = (eff_ratio - 0.5) * 25
    score += max(0, min(25, eff_points))
    
    # 3. Scoring recency (20%)
    # game_seconds_remaining or time_since_last_score (in seconds)
    time_since_score = row.get('time_since_last_score', 3600)
    
    if time_since_score <= 120:
        score += 20
    elif time_since_score <= 300:
        score += 15
    elif time_since_score <= 600:
        score += 10
    else:
        score += 5
        
    # 4. Turnover impact (15%)
    # We need to know if there was a turnover in last 5 plays for either team
    # (Simplified: check turnovers in last 10 plays metric we built)
    posteam_tos = row.get('turnovers_last_10_plays_posteam', 0)
    defteam_tos = row.get('turnovers_last_10_plays_defteam', 0)
    
    # nflfastR doesn't give us "last 5 plays" directly easily without more context,
    # but we'll use a simplified version for the MVP.
    if defteam_tos > 0: # Opponent turned it over
        score += 15
    elif posteam_tos > 0: # We turned it over
        score += 0
    else:
        score += 7.5
        
    return score

def add_momentum_column(df):
    """
    Adds momentum_score column to the context dataframe.
    """
    logger.info("Calculating momentum scores for all plays...")
    
    # Calculate season averages for drive efficiency
    team_averages = df.groupby(['season', 'posteam'])['drive_efficiency'].mean().to_dict()
    
    # This might be slow on large datasets, but for MVP it's fine
    df['momentum_score'] = df.apply(lambda row: calculate_momentum(row, team_averages), axis=1)
    
    return df

if __name__ == "__main__":
    # Test logic
    test_row = {
        'recent_success_rate': 0.8,
        'drive_efficiency': 7.5,
        'posteam': 'KC',
        'time_since_last_score': 100,
        'turnovers_last_10_plays_defteam': 1,
        'turnovers_last_10_plays_posteam': 0
    }
    score = calculate_momentum(test_row, {'KC': 5.0})
    print(f"Test Momentum Score: {score}")
