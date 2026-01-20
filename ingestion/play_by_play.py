import nfl_data_py as nfl
import pandas as pd
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_pbp_data(seasons=None):
    """
    Download play-by-play data from nflfastR using nfl_data_py.
    """
    if seasons is None:
        seasons = list(range(2018, 2025))
    
    logger.info(f"Downloading play-by-play data for seasons: {seasons}")
    try:
        df = nfl.import_pbp_data(seasons)
        return df
    except Exception as e:
        logger.error(f"Error downloading data: {e}")
        return None

def filter_pbp_data(df):
    """
    Filter to relevant columns for the analytics system.
    """
    columns = [
        'game_id', 'season', 'week', 'home_team', 'away_team',
        'down', 'ydstogo', 'yardline_100', 'game_seconds_remaining', 'quarter',
        'home_score', 'away_score', 'score_differential',
        'play_type', 'yards_gained', 'first_down', 'touchdown', 'turnover',
        'posteam', 'defteam', 'posteam_type',
        'wp', 'wpa', 'ep', 'epa'
    ]
    
    # Check which columns exist in the dataframe
    existing_columns = [col for col in columns if col in df.columns]
    logger.info(f"Filtering to {len(existing_columns)} columns.")
    return df[existing_columns]

def extract_4th_downs(df):
    """
    Extract 4th down situations and classify decisions.
    """
    logger.info("Extracting 4th down situations.")
    df_4th = df[df['down'] == 4].copy()
    
    def classify_decision(row):
        if row['play_type'] == 'punt':
            return 'punted'
        elif row['play_type'] == 'field_goal':
            return 'kicked_fg'
        elif row['play_type'] in ['run', 'pass']:
            return 'went_for_it'
        else:
            return 'other'

    df_4th['decision'] = df_4th.apply(classify_decision, axis=1)
    
    # Track outcome
    df_4th['converted'] = ((df_4th['first_down'] == 1) | (df_4th['touchdown'] == 1)).astype(int)
    
    return df_4th

def process_and_save():
    """
    Main function to download, process, and save data.
    """
    processed_dir = 'data/processed'
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)
        
    df_raw = download_pbp_data()
    if df_raw is not None:
        df_filtered = filter_pbp_data(df_raw)
        df_4th = extract_4th_downs(df_filtered)
        
        # Save filtered full pbp and 4th down specific data
        filtered_path = os.path.join(processed_dir, 'pbp_filtered.parquet')
        df_4th_path = os.path.join(processed_dir, 'pbp_4th_downs.parquet')
        
        logger.info(f"Saving filtered data to {filtered_path}")
        df_filtered.to_parquet(filtered_path)
        
        logger.info(f"Saving 4th down data to {df_4th_path}")
        df_4th.to_parquet(df_4th_path)
        
        return df_filtered, df_4th
    return None, None

if __name__ == "__main__":
    process_and_save()
