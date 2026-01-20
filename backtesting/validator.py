import pandas as pd
import numpy as np
import logging
from models.conversion import ConversionModel

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BacktestRunner:
    def __init__(self, model):
        self.model = model
        self.results = []

    def run_backtest(self, pbp_df):
        """
        Run backtest on a dataframe of 4th down situations.
        """
        logger.info(f"Running backtest on {len(pbp_df)} situations...")
        
        for idx, row in pbp_df.iterrows():
            # Get model probability
            # For backtesting, we use the context factors already in the row
            prediction = self.model.calculate_conversion_probability(row)
            
            # Simplified Decision logic for backtest
            # Go for it if prob > 0.5 (or compare to EV in more complex version)
            rec = 'go' if prediction['final_probability'] > 0.5 else 'punt'
            
            # Note: real EV would compare punt_wp vs go_wp. 
            # nflfastR gives us 'wp' which is current win prob.
            # 'wpa' is win prob added by the result.
            
            result = {
                'game_id': row['game_id'],
                'play_id': row.get('play_id'),
                'our_recommendation': rec,
                'our_conversion_prob': prediction['final_probability'],
                'static_recommendation': 'go' if row.get('wp', 0.5) > 0.5 else 'punt', # Dummy static rec
                'actual_decision': row['decision'],
                'actual_outcome': row['converted'],
                'context_factors': prediction
            }
            self.results.append(result)
            
        return BacktestResults(self.results)

class BacktestResults:
    def __init__(self, results):
        self.df = pd.DataFrame(results)

    def accuracy_vs_static(self):
        # Comparison logic
        return "Accuracy metrics summary..."

    def value_added(self):
        # WPA analysis
        return "Value added analysis..."

    def generate_report(self):
        """
        Generate a markdown summary of findings.
        """
        report = "# Backtest Results Report\n\n"
        report += f"Total Plays Analyzed: {len(self.df)}\n"
        report += f"Avg Predicted Conversion Prob: {self.df['our_conversion_prob'].mean():.2%}\n"
        report += "...\n"
        return report
