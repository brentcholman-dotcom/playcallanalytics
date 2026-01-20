import pandas as pd
import os
import json
from ingestion.play_by_play import process_and_save
from models.game_context import process_all_games
from models.momentum import add_momentum_column
from models.conversion import ConversionModel, build_base_rate_table
from backtesting.validator import BacktestRunner

def main():
    # 1. Ensure data is processed
    pbp_filtered_path = 'data/processed/pbp_filtered.parquet'
    context_path = 'data/processed/plays_with_context.parquet'
    
    if not os.path.exists(pbp_filtered_path):
        print("Initial data processing...")
        process_and_save()
        
    if not os.path.exists(context_path):
        print("Building rolling game context...")
        process_all_games(pbp_filtered_path)
    
    # 2. Load context data
    df = pd.read_parquet(context_path)
    
    # 3. Add momentum scores if not present
    if 'momentum_score' not in df.columns:
        df = add_momentum_column(df)
        df.to_parquet(context_path)
        
    # 4. Build base rate table (using all historical data)
    # We should distinguish between training and testing seasons but for MVP we use all
    # Or just use 2018-2021 to build table, 2022-2023 for backtest
    train_df = df[df['season'] < 2022]
    test_df = df[df['season'] >= 2022]
    
    # Filter test_df to 4th downs
    test_4th = test_df[test_df['down'] == 4].copy()
    
    # Re-classify decision for test set if needed (it should be there from extract_4th_downs)
    # But wait, process_all_games works on pbp_filtered. 
    # Let's make sure we have the 'decision' and 'converted' columns.
    
    # Actually, ingestion/play_by_play.py creates pbp_4th_downs.parquet which has these.
    # We should merge the context back into that or vice versa.
    # For simplicity, let's just make sure decision classification is applied.
    
    base_rates = build_base_rate_table(train_df)
    
    # 5. Initialize model and runner
    model = ConversionModel(base_rate_table=base_rates)
    runner = BacktestRunner(model)
    
    # 6. Run backtest
    results = runner.run_backtest(test_4th)
    
    # 7. Generate report
    report = results.generate_report()
    print(report)
    
    # 8. Save results
    output_path = 'data/processed/backtest_results.json'
    results.df.to_json(output_path, orient='records')
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()
