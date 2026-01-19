# Data Ingestion Usage Guide

This guide demonstrates how to use the play-by-play data ingestion functions.

## Quick Start

### Load and Process 4th Down Data (Complete Pipeline)

The simplest way to get started is using the complete pipeline:

```python
from ingestion.play_by_play import load_and_process_fourth_downs

# Load, filter, enrich, and save 4th down data for 2018-2024
fourth_downs = load_and_process_fourth_downs()

# Or specify custom seasons
fourth_downs = load_and_process_fourth_downs(seasons=[2022, 2023])
```

This will:
1. Download play-by-play data from nflfastR
2. Filter to 4th down situations
3. Classify decisions (went_for_it, punted, kicked_fg)
4. Add contextual features
5. Save to `data/processed/`

## Step-by-Step Usage

### 1. Load Play-by-Play Data

```python
from ingestion.play_by_play import load_pbp_data

# Load specific seasons
pbp_data = load_pbp_data(seasons=[2023, 2024])

# Load 2018-2024 (default)
pbp_data = load_pbp_data()

# Include only regular season
pbp_data = load_pbp_data(include_playoffs=False)
```

**Columns included:**
- Game identifiers: `game_id`, `season`, `week`, `home_team`, `away_team`
- Situation: `down`, `ydstogo`, `yardline_100`, `game_seconds_remaining`, `quarter`
- Score: `home_score`, `away_score`, `score_differential`
- Play info: `play_type`, `yards_gained`, `first_down`, `touchdown`, `turnover`
- Context: `posteam`, `defteam`, `posteam_type`
- Analytics: `wp`, `wpa`, `ep`, `epa`
- Weather: `temp`, `wind`, `roof`, `surface`

### 2. Filter to 4th Down Plays

```python
from ingestion.play_by_play import filter_fourth_down_plays

# Filter to 4th down situations
fourth_downs = filter_fourth_down_plays(pbp_data)

# Check decision breakdown
print(fourth_downs['decision'].value_counts())
# Output:
#   punted         ~12,000
#   went_for_it    ~4,000
#   kicked_fg      ~3,000
```

**New columns added:**
- `decision`: Classification of 4th down decision
  - `went_for_it`: Team attempted conversion
  - `punted`: Team punted
  - `kicked_fg`: Team attempted field goal
- `converted`: Boolean indicating if conversion succeeded (for went_for_it only)
- `success`: Boolean indicating successful outcome

### 3. Enrich with Contextual Features

```python
from ingestion.play_by_play import enrich_play_context

# Add contextual features
enriched = enrich_play_context(fourth_downs)
```

**New features added:**
- `game_minutes_remaining`: Minutes left in game
- `is_final_two_minutes`: Boolean for final 2 minutes
- `field_position_category`: `red_zone`, `plus_territory`, `midfield`, `own_territory`, `deep_own`
- `score_situation`: `down_big`, `down_two_scores`, `down_one_score`, `close`, `up_one_score`, etc.
- `distance_category`: `short`, `medium`, `long`, `very_long`

### 4. Save Processed Data

```python
from ingestion.play_by_play import save_processed_data

# Save to data/processed/
save_processed_data(enriched, filename='fourth_downs_2023')

# Output files:
#   data/processed/fourth_downs_2023.csv
#   data/processed/fourth_downs_2023.parquet
```

## Example Analysis

### Conversion Rate by Distance

```python
import pandas as pd
from ingestion.play_by_play import load_and_process_fourth_downs

# Load data
df = load_and_process_fourth_downs(seasons=[2023])

# Filter to "went for it" decisions
went_for_it = df[df['decision'] == 'went_for_it']

# Calculate conversion rate by distance category
conversion_by_distance = went_for_it.groupby('distance_category')['converted'].agg([
    ('attempts', 'count'),
    ('conversions', 'sum'),
    ('rate', 'mean')
])

print(conversion_by_distance)
```

### 4th Down Decisions by Field Position

```python
# Cross-tabulation of decision by field position
decision_by_field = pd.crosstab(
    df['field_position_category'],
    df['decision'],
    normalize='index'
)

print(decision_by_field)
```

### Situational Analysis

```python
# Analyze 4th down decisions in final 2 minutes when trailing
critical_situations = df[
    (df['is_final_two_minutes']) &
    (df['score_differential'] < 0)
]

print(f"Total 4th downs in critical situations: {len(critical_situations)}")
print(critical_situations['decision'].value_counts(normalize=True))
```

## Running Tests

To verify the implementation:

```bash
cd nfl-analytics
python test_ingestion.py
```

This will:
- Load a single season of data
- Filter to 4th downs
- Enrich with contextual features
- Run the complete pipeline
- Perform data quality checks

## Data Validation

The ingestion module includes automatic validation:
- Checks for required columns
- Warns about missing data
- Validates season ranges
- Verifies down values
- Logs statistics at each step

## Logging

All functions include detailed logging:

```python
import logging

# Set log level
logging.basicConfig(level=logging.INFO)

# Run functions - detailed logs will be printed
df = load_and_process_fourth_downs()
```

## Performance Notes

- **Full dataset (2018-2024)**: ~500,000 4th down plays
- **Single season**: ~3,000-4,000 4th down plays
- **Memory usage**: ~100-200 MB for full dataset
- **Load time**: 30-60 seconds for full dataset (first download is cached)

## Next Steps

After loading the data, you can:
1. Merge with weather data (see `ingestion/weather_api.py`)
2. Add injury information (see `ingestion/injury_feed.py`)
3. Calculate momentum scores (see `models/momentum.py`)
4. Build conversion probability models (see `models/conversion.py`)
