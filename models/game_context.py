import pandas as pd
import numpy as np
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def build_game_context(df_game):
    """
    Builds rolling context for each play in a single game.
    """
    df_game = df_game.sort_values(['quarter', 'game_seconds_remaining'], ascending=[True, False]).copy()
    
    # 1. & 2. Recent play history (last 5 plays)
    # We need to track this per team (offense/defense)
    
    # Success definition: 40% of yards needed
    df_game['is_success'] = (df_game['yards_gained'] >= (df_game['ydstogo'] * 0.4)).astype(int)
    df_game['is_explosive'] = (df_game['yards_gained'] >= 15).astype(int)
    
    # helper to calculate rolling metrics for a team
    def get_rolling_metrics(group):
        # Rolling success rate (last 5 plays)
        group['recent_success_rate'] = group['is_success'].shift(1).rolling(5, min_periods=1).mean()
        group['recent_yards_per_play'] = group['yards_gained'].shift(1).rolling(5, min_periods=1).mean()
        group['recent_explosive_plays'] = group['is_explosive'].shift(1).rolling(5, min_periods=1).sum()
        return group

    # Apply rolling metrics per posteam
    df_game = df_game.groupby('posteam', group_keys=False).apply(get_rolling_metrics)
    
    # Now we need defense metrics (what the defense they are facing has done)
    # This is slightly tricky: for each play, look at the defteam's recent defensive performance
    # But usually "defensive momentum" is just the inverse of the offense's performance against them
    # The prompt asks for "last 5 plays for defense they're facing"
    
    def get_defensive_rolling_metrics(group):
        # Metrics for when THIS team was on defense
        group['opponent_recent_success_rate'] = group['is_success'].shift(1).rolling(5, min_periods=1).mean()
        group['opponent_recent_yards_per_play'] = group['yards_gained'].shift(1).rolling(5, min_periods=1).mean()
        return group

    # Apply based on defteam
    def_metrics = df_game.groupby('defteam', group_keys=False).apply(get_defensive_rolling_metrics)
    df_game['opponent_success_rate'] = def_metrics['opponent_recent_success_rate']
    df_game['opponent_yards_per_play'] = def_metrics['opponent_recent_yards_per_play']

    # 3. Drive Context
    # nflfastR has drive_id or drive column, but let's calculate manually if needed or use existing
    # Assuming 'drive' column exists in nflfastR data
    if 'drive' in df_game.columns:
        df_game['plays_this_drive'] = df_game.groupby('drive').cumcount()
        df_game['yards_this_drive'] = df_game.groupby('drive')['yards_gained'].cumsum().shift(1).fillna(0)
        df_game['drive_efficiency'] = df_game['yards_this_drive'] / df_game['plays_this_drive'].replace(0, 1)

    # 4. Scoring Context
    # We need to track the time of the last score
    df_game['is_score'] = ((df_game['touchdown'] == 1) | (df_game['play_type'] == 'field_goal')).astype(int) # simplistic
    # More accurate: check score changes
    df_game['total_score'] = df_game['home_score'] + df_game['away_score']
    df_game['score_change'] = df_game['total_score'].diff().fillna(0)
    
    # Time since last score
    # We can use game_seconds_remaining
    last_score_time = 3600 # Start of game
    times_since_last_score = []
    last_team_scored = None
    
    for idx, row in df_game.iterrows():
        if row['score_change'] > 0:
            last_score_time = row['game_seconds_remaining']
            # Determine who scored (might need more logic for accuracy)
            last_team_scored = row['posteam'] # simplistic
            
        times_since_last_score.append(last_score_time - row['game_seconds_remaining'])
    
    df_game['time_since_last_score'] = times_since_last_score
    
    # 5. Turnover context
    df_game['is_turnover'] = df_game['turnover'].fillna(0).astype(int)
    df_game['turnovers_last_10_plays_posteam'] = df_game.groupby('posteam')['is_turnover'].shift(1).rolling(10, min_periods=1).sum()
    df_game['turnovers_last_10_plays_defteam'] = df_game.groupby('defteam')['is_turnover'].shift(1).rolling(10, min_periods=1).sum()

    return df_game

def process_all_games(pbp_path='data/processed/pbp_filtered.parquet'):
    if not os.path.exists(pbp_path):
        logger.error(f"PBP data not found at {pbp_path}")
        return
        
    df = pd.read_parquet(pbp_path)
    logger.info(f"Processing context for {len(df['game_id'].unique())} games.")
    
    processed_games = []
    for game_id, group in df.groupby('game_id'):
        processed_games.append(build_game_context(group))
        
    df_context = pd.concat(processed_games)
    
    output_path = 'data/processed/plays_with_context.parquet'
    logger.info(f"Saving context-enriched data to {output_path}")
    df_context.to_parquet(output_path)
    return df_context

if __name__ == "__main__":
    process_all_games()
