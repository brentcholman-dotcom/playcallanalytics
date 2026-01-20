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

## Game Context & Rolling Statistics

### Overview

The `game_context` module adds rolling context to each play, tracking recent performance, drive status, scoring momentum, and turnovers. This provides dynamic context that evolves throughout the game.

### Quick Start

```python
from models.game_context import process_all_games_with_context

# Process all games and add rolling context
plays_with_context = process_all_games_with_context(seasons=[2023])

# Data saved to: data/processed/plays_with_context.parquet
```

### Context Features Added

#### 1. Recent Offensive History (Last 5 Plays)

Tracks the offense's recent performance:

- **off_success_rate**: % of plays gaining 40%+ of needed yards
- **off_yards_per_play**: Average yards gained
- **off_explosive_plays**: Count of 15+ yard plays

```python
# Example: Find hot offenses
hot_offenses = plays[plays['off_success_rate'] >= 0.8]
```

#### 2. Recent Defensive History (Last 5 Plays)

Tracks the defense's recent performance:

- **def_success_rate**: % of plays allowed gaining 40%+ of needed yards
- **def_yards_per_play**: Average yards allowed

```python
# Example: Find struggling defenses
struggling_defenses = plays[plays['def_yards_per_play'] > 7.0]
```

#### 3. Drive Context

Tracks current drive statistics:

- **plays_this_drive**: Number of plays in current drive
- **yards_this_drive**: Total yards gained this drive
- **drive_efficiency**: Yards per play this drive

```python
# Example: Find long, efficient drives
long_drives = plays[
    (plays['plays_this_drive'] >= 8) &
    (plays['drive_efficiency'] >= 6.0)
]
```

#### 4. Scoring & Momentum Context

Tracks scoring trends and momentum:

- **time_since_last_score**: Seconds since last score (either team)
- **last_score_team**: Team that scored last
- **momentum_shift**: Did lead change in last 5 minutes?

```python
# Example: Find plays with recent momentum shifts
momentum_plays = plays[plays['momentum_shift'] == True]

# Example: Long scoring droughts
droughts = plays[plays['time_since_last_score'] > 600]  # 10+ minutes
```

#### 5. Turnover Context

Tracks recent turnovers:

- **turnovers_last_10_plays_offense**: Turnovers by current offense
- **turnovers_last_10_plays_defense**: Turnovers forced by current defense
- **time_since_turnover**: Seconds since last turnover (either team)

```python
# Example: Post-turnover situations
recent_turnovers = plays[plays['time_since_turnover'] < 120]  # Last 2 minutes
```

### Advanced Usage

#### Process Single Game

```python
from ingestion.play_by_play import load_pbp_data
from models.game_context import add_game_context

# Load data
pbp = load_pbp_data(seasons=[2023])

# Get specific game
game = pbp[pbp['game_id'] == '2023_01_BUF_NYJ']

# Add context
game_with_context = add_game_context(game)
```

#### Individual Context Functions

```python
from models.game_context import (
    calculate_recent_offensive_history,
    calculate_recent_defensive_history,
    calculate_drive_context,
    calculate_scoring_context,
    calculate_turnover_context
)

# Calculate specific contexts
game = calculate_recent_offensive_history(game, window=5)
game = calculate_drive_context(game)
game = calculate_scoring_context(game)
```

#### Get Summary Statistics

```python
from models.game_context import get_context_summary

# Load processed data
plays = pd.read_parquet('data/processed/plays_with_context.parquet')

# Get summary
summary = get_context_summary(plays)
print(summary)
```

### Example Analysis

#### 4th Down Decisions by Context

```python
import pandas as pd

# Load 4th down data with context
fourth_downs = pd.read_parquet('data/processed/fourth_downs_2023.parquet')
plays_context = pd.read_parquet('data/processed/plays_with_context.parquet')

# Merge context into 4th downs
fourth_downs_with_context = fourth_downs.merge(
    plays_context[['game_id', 'play_id', 'off_success_rate', 'momentum_shift']],
    on=['game_id', 'play_id'],
    how='left'
)

# Analyze decisions by offensive success rate
print(fourth_downs_with_context.groupby('decision')['off_success_rate'].mean())

# Went for it rate when offense is hot
hot_offense = fourth_downs_with_context[
    fourth_downs_with_context['off_success_rate'] >= 0.8
]
print(f"Go for it rate when hot: {(hot_offense['decision'] == 'went_for_it').mean():.2%}")
```

#### Conversion Success by Context

```python
# Filter to "went for it" decisions
went_for_it = fourth_downs_with_context[
    fourth_downs_with_context['decision'] == 'went_for_it'
]

# Conversion rate by offensive success
bins = [0, 0.4, 0.6, 0.8, 1.0]
labels = ['cold', 'lukewarm', 'warm', 'hot']
went_for_it['offense_temp'] = pd.cut(
    went_for_it['off_success_rate'],
    bins=bins,
    labels=labels
)

conversion_by_temp = went_for_it.groupby('offense_temp')['converted'].agg([
    ('attempts', 'count'),
    ('success_rate', 'mean')
])
print(conversion_by_temp)
```

### Running Tests

```bash
cd nfl-analytics
python test_game_context.py
```

This will:
- Test each context calculation function
- Process a full season
- Generate summary statistics
- Validate data quality

### Performance Notes

- **Processing time**: ~2-3 minutes per season (single-threaded)
- **Memory usage**: ~500 MB for full dataset
- **Output size**: ~150 MB parquet file for single season

### Context Calculation Notes

1. **Rolling windows**: Use last N plays for each team separately
2. **Edge cases**: First few plays of game may have NaN values for context
3. **Drive tracking**: Uses existing drive identifiers when available
4. **Chronological order**: Critical that plays are processed in game order

## Next Steps

After loading the data and adding context, you can:
1. Merge with weather data (see `ingestion/weather_api.py`)
2. Add injury information (see `ingestion/injury_feed.py`)
3. Use context features in momentum models (see `models/momentum.py`)
4. Build context-aware conversion probability models (see `models/conversion.py`)
5. Backtest predictions with contextual features (see `backtesting/validator.py`)
