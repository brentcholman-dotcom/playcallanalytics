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

## Momentum Scoring

### Overview

The momentum module quantifies offensive momentum on a 0-100 scale using four weighted components:

- **Recent Play Success** (40%): Success rate of last 5 plays
- **Drive Efficiency** (25%): Current drive vs season average
- **Scoring Recency** (20%): How recently team scored
- **Turnover Impact** (15%): Recent turnover effects

### Momentum Scale

- **0-25**: Cold/struggling offense
- **26-50**: Average momentum
- **51-75**: Good momentum
- **76-100**: Hot/dominant offense

### Quick Start

```python
from ingestion.play_by_play import load_pbp_data
from models.game_context import add_game_context
from models.momentum import add_momentum_scores

# Load data
pbp = load_pbp_data(seasons=[2023])

# Get a game
game = pbp[pbp['game_id'] == '2023_01_BUF_NYJ']

# Add context
game_with_context = add_game_context(game)

# Add momentum scores
game_with_momentum = add_momentum_scores(game_with_context)

# View momentum scores
print(game_with_momentum[['posteam', 'momentum_score']].head())
```

### Momentum Components

#### 1. Recent Play Success (0-40 points)

Based on success rate of last 5 plays (gaining 40%+ of needed yards):

```python
# 100% success = 40 points
# 50% success = 20 points
# 0% success = 0 points
```

#### 2. Drive Efficiency (0-25 points)

Compares current drive efficiency to team's season average:

```python
# 50% better than average (1.5x) = 25 points
# At average (1.0x) = 12.5 points
# 50% worse than average (0.5x) = 0 points
```

#### 3. Scoring Recency (0-20 points)

Rewards teams that scored recently:

```python
# Scored in last 2 minutes = 20 points
# Scored in last 5 minutes = 15 points
# Scored in last 10 minutes = 10 points
# No recent score or opponent scored = 5 points
```

#### 4. Turnover Impact (0-15 points)

Accounts for recent turnovers:

```python
# Opponent turnover in last 10 plays = 15 points (momentum boost)
# Own turnover in last 10 plays = 0 points (momentum killer)
# No recent turnovers = 7.5 points (neutral)
```

### Usage Examples

#### Calculate Momentum for Single Play

```python
from models.momentum import calculate_momentum, calculate_season_averages

# Calculate season averages
season_avg_ypp = calculate_season_averages(pbp_data)

# Calculate momentum for a specific row
row = plays_with_context.iloc[100]
momentum_score = calculate_momentum(row, season_avg_ypp)
print(f"Momentum: {momentum_score:.1f}/100")
```

#### Add Momentum to Entire Dataset

```python
from models.momentum import add_momentum_scores

# Add momentum scores (calculates season averages automatically)
plays_with_momentum = add_momentum_scores(plays_with_context)

# View statistics
print(plays_with_momentum['momentum_score'].describe())
```

#### Categorize Momentum

```python
from models.momentum import get_momentum_category

# Add categories
plays_with_momentum['momentum_category'] = plays_with_momentum['momentum_score'].apply(
    get_momentum_category
)

# View distribution
print(plays_with_momentum['momentum_category'].value_counts())
```

#### Analyze Momentum Distribution

```python
from models.momentum import analyze_momentum_distribution

# Get summary by momentum category
summary = analyze_momentum_distribution(plays_with_momentum)
print(summary)
```

### Example Analysis

#### 4th Down Decisions by Momentum

```python
import pandas as pd

# Load 4th downs and add momentum
fourth_downs = pd.read_parquet('data/processed/fourth_downs_2023.parquet')
plays_momentum = pd.read_parquet('data/processed/plays_with_momentum.parquet')

# Merge
fourth_downs_momentum = fourth_downs.merge(
    plays_momentum[['game_id', 'play_id', 'momentum_score']],
    on=['game_id', 'play_id'],
    how='left'
)

# Add categories
from models.momentum import get_momentum_category
fourth_downs_momentum['momentum_category'] = fourth_downs_momentum['momentum_score'].apply(
    get_momentum_category
)

# Analyze: Do high-momentum offenses go for it more?
decision_by_momentum = pd.crosstab(
    fourth_downs_momentum['momentum_category'],
    fourth_downs_momentum['decision'],
    normalize='index'
)
print(decision_by_momentum)
```

#### Conversion Success by Momentum

```python
# Filter to "went for it" decisions
went_for_it = fourth_downs_momentum[
    fourth_downs_momentum['decision'] == 'went_for_it'
]

# Conversion rate by momentum category
conversion_by_momentum = went_for_it.groupby('momentum_category')['converted'].agg([
    ('attempts', 'count'),
    ('conversions', 'sum'),
    ('rate', 'mean')
])
print(conversion_by_momentum)
```

#### Hot vs Cold Offenses

```python
# Compare hot vs cold offenses
hot_offenses = plays_with_momentum[plays_with_momentum['momentum_score'] >= 76]
cold_offenses = plays_with_momentum[plays_with_momentum['momentum_score'] <= 25]

print(f"Hot offenses: {len(hot_offenses):,} plays")
print(f"  Avg yards/play: {hot_offenses['yards_gained'].mean():.2f}")
print(f"  First down rate: {hot_offenses['first_down'].mean():.1%}")

print(f"\nCold offenses: {len(cold_offenses):,} plays")
print(f"  Avg yards/play: {cold_offenses['yards_gained'].mean():.2f}")
print(f"  First down rate: {cold_offenses['first_down'].mean():.1%}")
```

### Running Tests

```bash
cd nfl-analytics
python test_momentum.py
```

This will test:
- Individual momentum components
- Single game calculations
- Momentum categories
- Relationship to outcomes
- Multiple games analysis
- Extreme scenarios
- 4th down specific analysis

### Integration with Game Context

Momentum scoring requires game context features:

```python
from ingestion.play_by_play import load_pbp_data
from models.game_context import add_game_context
from models.momentum import add_momentum_scores

# Complete pipeline
pbp = load_pbp_data(seasons=[2023])
pbp_context = add_game_context(pbp)
pbp_momentum = add_momentum_scores(pbp_context)

# Save for later use
from ingestion.play_by_play import save_processed_data
save_processed_data(pbp_momentum, 'plays_with_momentum_2023')
```

### Performance Notes

- **Computation**: ~1-2 seconds per game
- **Season averages**: Calculated once per dataset
- **Memory**: Minimal overhead (~1 column added)
- **Dependencies**: Requires game context columns

## Next Steps

After loading the data, adding context, and calculating momentum, you can:
1. Merge with weather data (see `ingestion/weather_api.py`)
2. Add injury information (see `ingestion/injury_feed.py`)
3. Build context-aware conversion probability models using momentum (see `models/conversion.py`)
4. Backtest predictions with momentum features (see `backtesting/validator.py`)
5. Compare coach decisions to model recommendations stratified by momentum
