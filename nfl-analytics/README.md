# NFL Context-Aware Analytics System

A sophisticated NFL analytics system that improves on static 4th down decision models by incorporating real-time game context including momentum, weather, injuries, fatigue, and crowd noise.

## Overview

Traditional 4th down models rely on static probabilities based on field position and distance. This system enhances those models by incorporating dynamic contextual factors that significantly impact play outcomes:

- **Game Momentum**: Recent play sequences and scoring trends
- **Injury Impact**: Effects of key player injuries on team performance
- **Weather Conditions**: Temperature, wind, precipitation, and field type
- **Crowd Noise**: Home field advantage and communication challenges
- **Fatigue Levels**: Player fatigue based on snap counts and game flow

## Project Structure

```
nfl-analytics/
├── data/
│   ├── raw/              # nflfastR downloads and raw data
│   └── processed/        # Cleaned and enriched datasets
├── models/
│   ├── momentum.py       # Momentum scoring algorithm
│   ├── injuries.py       # Injury impact calculations
│   ├── weather.py        # Weather adjustment factors
│   ├── crowd_noise.py    # Crowd noise impact model
│   ├── fatigue.py        # Fatigue estimation model
│   └── conversion.py     # Final probability calculator
├── ingestion/
│   ├── play_by_play.py   # Historical data loading via nfl_data_py
│   ├── weather_api.py    # Weather data integration
│   └── injury_feed.py    # Injury report parsing
├── backtesting/
│   └── validator.py      # Model validation and comparison
├── config/
│   └── settings.py       # Configuration and model weights
└── requirements.txt      # Python dependencies
```

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Configuration

Edit `config/settings.py` to customize:

- **Model Weights**: Adjust the importance of each contextual factor
- **Thresholds**: Set decision thresholds for recommendations
- **API Keys**: Configure weather and data API credentials
- **Data Paths**: Customize data storage locations

### Default Model Weights

```python
MODEL_WEIGHTS = {
    'momentum': 0.20,
    'injuries': 0.15,
    'weather': 0.10,
    'crowd_noise': 0.08,
    'fatigue': 0.12,
    'base_model': 0.35
}
```

## Usage

### Loading Historical Data

```python
from ingestion.play_by_play import load_pbp_data, filter_fourth_down_plays

# Load play-by-play data for multiple seasons
pbp_data = load_pbp_data(seasons=[2020, 2021, 2022, 2023])

# Filter to 4th down situations
fourth_down_plays = filter_fourth_down_plays(pbp_data)
```

### Calculating Context-Aware Probabilities

```python
from models.conversion import calculate_conversion_probability
from config.settings import MODEL_WEIGHTS

# Calculate conversion probability with all factors
probability = calculate_conversion_probability(
    base_probability=0.55,
    momentum_score=0.15,
    injury_impact=0.92,
    weather_factor=0.95,
    noise_impact=0.88,
    fatigue_factor=0.90,
    weights=MODEL_WEIGHTS
)
```

### Backtesting

```python
from backtesting.validator import backtest_predictions, compare_to_baseline

# Validate model performance
results = backtest_predictions(predictions, actual_outcomes)

# Compare to static baseline model
comparison = compare_to_baseline(model_results, baseline_results)
```

## Data Sources

- **Play-by-Play Data**: nfl_data_py (Python wrapper for nflfastR)
- **Weather Data**: Weather API integration (configure in settings.py)
- **Injury Reports**: NFL injury report feeds

## Model Components

### Momentum Model
Analyzes recent play sequences, possession efficiency, and scoring trends to quantify game momentum.

### Injury Impact Model
Assesses the impact of injuries to key players, considering position importance and depth chart effects.

### Weather Model
Adjusts probabilities based on temperature, wind speed, precipitation, and field conditions.

### Crowd Noise Model
Models the impact of crowd noise on offensive communication and execution, particularly for road teams.

### Fatigue Model
Estimates player fatigue based on snap counts, pace of play, game time, and environmental factors.

### Conversion Probability Calculator
Integrates all contextual factors with configurable weights to produce final conversion probabilities and recommendations.

## Backtesting and Validation

The system includes comprehensive backtesting capabilities to validate model performance:

- Compare predictions against historical outcomes
- Measure improvement over static baseline models
- Generate detailed performance reports
- Analyze model performance across different scenarios

## Development Roadmap

- [ ] Implement data ingestion pipeline
- [ ] Develop individual contextual models
- [ ] Create integration framework
- [ ] Build backtesting infrastructure
- [ ] Validate against historical data
- [ ] Optimize model weights
- [ ] Add real-time prediction capabilities
- [ ] Create visualization dashboard

## Contributing

Contributions are welcome. Please ensure:

- Code follows PEP 8 style guidelines
- New features include appropriate tests
- Documentation is updated accordingly

## License

MIT License

## Acknowledgments

- nflfastR team for excellent play-by-play data
- NFL analytics community for inspiration and research
