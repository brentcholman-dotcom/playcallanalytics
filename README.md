# NFL Context-Aware Analytics System

Improved 4th down decision analytics incorporating game flow, weather, injuries, fatigue, and crowd noise.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run a backtest:
   ```bash
   python main.py backtest
   ```

3. Start live tracking:
   ```bash
   python main.py live --game-id 401547654
   ```

## Architecture

- `ingestion/`: Data pipelines for historical and live data.
- `models/`: Context-aware algorithms for momentum, weather, etc.
- `interface/`: Recommender engine and terminal dashboard.
- `backtesting/`: Validation framework against historical outcomes.

## Documentation

- [Algorithm Details](docs/ALGORITHM.md)
- [Data Sources](docs/DATA_SOURCES.md)
- [Backtest Findings](docs/BACKTEST_RESULTS.md)
