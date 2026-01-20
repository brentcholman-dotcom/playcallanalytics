# NFL Context-Aware Analytics System
## Claude Code Prompts Guide

Use these prompts sequentially in Claude Code to build your system. Each prompt builds on the previous work.

---

## Phase 1: Project Setup & Data Pipeline

### Prompt 1.1 — Project Initialization

```
I'm building a context-aware NFL analytics system that improves on static 4th down 
decision models by incorporating game flow, weather, injuries, fatigue, and crowd noise.

Set up the project structure:

nfl-analytics/
├── data/
│   ├── raw/              # nflfastR downloads
│   └── processed/        # cleaned, enriched data
├── models/
│   ├── momentum.py       # momentum scoring algorithm
│   ├── injuries.py       # injury impact calculations
│   ├── weather.py        # weather adjustments
│   ├── crowd_noise.py    # noise impact model
│   ├── fatigue.py        # fatigue estimates
│   └── conversion.py     # final probability calculator
├── ingestion/
│   ├── play_by_play.py   # historical data loading
│   ├── weather_api.py    # weather data integration
│   └── injury_feed.py    # injury report parsing
├── backtesting/
│   └── validator.py      # compare predictions vs outcomes
├── config/
│   └── settings.py       # API keys, weights, thresholds
└── README.md

Create this structure with placeholder files and a requirements.txt including:
- pandas
- numpy
- nfl_data_py (Python wrapper for nflfastR)
- requests
- python-dotenv
```

---

### Prompt 1.2 — Load Historical Play-by-Play Data

```
In ingestion/play_by_play.py, create functions to:

1. Download play-by-play data from nflfastR using nfl_data_py
   - Load seasons 2018-2024
   - Include all regular season and playoff games

2. Filter to relevant columns:
   - Game identifiers: game_id, season, week, home_team, away_team
   - Situation: down, ydstogo, yardline_100, game_seconds_remaining, quarter
   - Score: home_score, away_score, score_differential
   - Play info: play_type, yards_gained, first_down, touchdown, turnover
   - Context: posteam (team on offense), defteam, posteam_type (home/away)
   - Existing analytics: wp (win probability), wpa (win prob added), ep, epa

3. Create a function to extract 4th down situations specifically:
   - Filter to down == 4
   - Classify decision: went_for_it, punted, kicked_fg
   - Track outcome: converted (yes/no), result

4. Save processed data to data/processed/

Include basic data validation and logging.
```

---

### Prompt 1.3 — Build Rolling Game Context

```
Create a new file models/game_context.py that builds rolling context for each play.

For each play in a game, calculate:

1. Recent play history (last 5 plays for offense):
   - success_rate: % of plays gaining 40%+ of needed yards
   - yards_per_play: average
   - explosive_plays: plays of 15+ yards

2. Recent play history (last 5 plays for defense they're facing):
   - opponent_success_rate
   - opponent_yards_per_play

3. Drive context:
   - plays_this_drive
   - yards_this_drive
   - drive_efficiency: yards_per_play this drive

4. Scoring context:
   - time_since_last_score (either team)
   - last_score_team: who scored last
   - momentum_shift: did lead change in last 5 minutes?

5. Turnover context:
   - turnovers_last_10_plays (by each team)
   - time_since_turnover

The function should take a game_id and return a dataframe with one row per play,
original columns plus all the rolling context columns.

Process all games and save to data/processed/plays_with_context.parquet
```

---

## Phase 2: Core Algorithms

### Prompt 2.1 — Momentum Algorithm

```
In models/momentum.py, implement the momentum scoring algorithm.

Offensive Momentum Score (0-100 scale):

COMPONENTS:
1. Recent play success (40% weight)
   - Last 5 plays: what % were "successful" (gained 40%+ of needed yards)
   - Scale: 0% success = 0 points, 100% success = 40 points

2. Drive efficiency vs season average (25% weight)
   - Compare current drive yards/play to team's season average
   - If 50% better than average = 25 points
   - If at average = 12.5 points
   - If 50% worse = 0 points

3. Scoring recency (20% weight)
   - Scored in last 2 minutes = 20 points
   - Scored in last 5 minutes = 15 points
   - Scored in last 10 minutes = 10 points
   - No recent score = 5 points

4. Turnover impact (15% weight)
   - Opponent turnover in last 5 plays = 15 points
   - Own turnover in last 5 plays = 0 points
   - No recent turnovers = 7.5 points

FINAL SCORE = sum of components (0-100)

Create:
- calculate_momentum(game_context_row) -> float
- A function to add momentum_score column to the context dataframe

Test with a few example games to verify the logic makes sense.
```

---

### Prompt 2.2 — Weather Impact Model

```
In models/weather.py, create the weather impact model.

For historical backtesting, we need to get weather data for past games.
Use the nfl_data_py weather data if available, or create a structure to 
integrate with a weather API later.

Weather factors that affect play:

1. Wind Impact (affects kicking and deep passing):
   wind_speed < 10 mph:  0% impact
   10-15 mph:           -3% on FG over 45 yards, -2% on deep passes
   15-20 mph:           -8% on FG over 40 yards, -5% on deep passes
   20+ mph:             -15% on FG over 35 yards, -10% on deep passes
   
   Also factor wind direction vs field orientation if available.

2. Temperature Impact (affects grip, fatigue):
   Below 32°F:  -2% on passing plays (ball harder to grip)
   32-50°F:     0%
   50-85°F:     0%
   Above 85°F:  -1% per 5 degrees (fatigue factor)

3. Precipitation:
   Rain:        -5% passing, -2% kicking
   Snow:        -8% passing, -10% kicking
   None:        0%

Create:
- get_weather_for_game(game_id) -> dict with temp, wind_speed, wind_dir, precipitation
- calculate_weather_modifier(weather_dict, play_type, field_position) -> float (multiplier)

For plays where we don't have weather data, return 1.0 (no modification).
```

---

### Prompt 2.3 — Fatigue Model

```
In models/fatigue.py, create the fatigue estimation model.

Defensive Fatigue (helps offense):
- consecutive_defensive_plays: plays without a change of possession
- time_of_possession_against: TOP opponent has had this quarter
- temperature_factor: high heat increases fatigue impact

Formula:
base_fatigue = (consecutive_plays * 0.3) + (top_against_minutes * 0.5)
temp_modifier = 1.0 + max(0, (temp - 85) * 0.02)  # 2% more per degree over 85
fatigue_score = base_fatigue * temp_modifier

Convert to impact:
fatigue_score 0-5:   +0% (fresh)
fatigue_score 5-10:  +1.5%
fatigue_score 10-15: +3%
fatigue_score 15-20: +5%
fatigue_score 20+:   +7%

Offensive Fatigue (hurts offense):
- Same calculation but for your own offense
- Impact is negative (reduces conversion probability)

Timeout reset:
- Timeout by defense resets their fatigue by 50%
- Need to track timeouts in game context

Create:
- calculate_defensive_fatigue(game_context) -> float (positive, helps offense)
- calculate_offensive_fatigue(game_context) -> float (negative, hurts offense)
- calculate_net_fatigue_modifier(game_context) -> float
```

---

### Prompt 2.4 — Injury Impact Model

```
In models/injuries.py, create the injury impact model.

This needs two components:

1. Position value weights by situation:

4TH_SHORT = {  # 1-2 yards to go
    'DT': 0.8, 'NT': 0.8,
    'MLB': 0.8, 'ILB': 0.8,
    'EDGE': 0.5, 'OLB': 0.5,
    'SS': 0.5, 'FS': 0.4,
    'CB': 0.2
}

4TH_MEDIUM = {  # 3-5 yards
    'MLB': 0.8, 'ILB': 0.8,
    'EDGE': 0.7, 'OLB': 0.7,
    'CB': 0.6,
    'SS': 0.5, 'FS': 0.5,
    'DT': 0.5, 'NT': 0.5
}

4TH_LONG = {  # 6+ yards
    'CB': 0.9,
    'EDGE': 0.8, 'OLB': 0.8,
    'FS': 0.7, 'SS': 0.7,
    'MLB': 0.5, 'ILB': 0.5,
    'DT': 0.3, 'NT': 0.3
}

# Similar weights for offensive positions (negative impact)
OFFENSE_SHORT = {
    'RB': 0.8, 'C': 0.8, 'OG': 0.7, 'FB': 0.6, 'TE': 0.6,
    'OT': 0.5, 'QB': 0.4, 'WR': 0.2
}
# ... etc for medium and long

2. Player quality tiers (simple version for MVP):
   STARTER = 1.0
   QUALITY_BACKUP = 0.8
   DEPTH = 0.6
   PRACTICE_SQUAD = 0.4

3. Impact calculation:
   For each injured defender:
   impact = position_weight * (starter_tier - backup_tier) * 0.1
   
   Sum all defensive injuries = defensive_injury_modifier (positive)
   Sum all offensive injuries = offensive_injury_modifier (negative)
   
   Special case: QB injury uses tier-based lookup table:
   STARTER_OUT_QUALITY_BACKUP = -0.20  # 20% reduction
   STARTER_OUT_DEPTH_BACKUP = -0.40    # 40% reduction

4. OL shuffle penalty:
   If 2 OL backups playing: multiply OL impact by 1.3
   If 3+ OL backups: multiply by 1.6

Create:
- InjuryTracker class that maintains current injury state
- calculate_defensive_injury_modifier(injuries, yards_to_go) -> float
- calculate_offensive_injury_modifier(injuries, yards_to_go) -> float
- calculate_net_injury_modifier(def_injuries, off_injuries, yards_to_go) -> float

For backtesting, we'll need to integrate historical injury report data later.
For now, create the calculation logic with stub data.
```

---

### Prompt 2.5 — Crowd Noise Model

```
In models/crowd_noise.py, create the crowd noise impact model.

Two modes: direct dB reading (preferred) or proxy estimation.

1. Stadium base ratings (build a lookup dict):

STADIUM_NOISE = {
    'KC': 98,   # Arrowhead
    'SEA': 96,  # Lumen Field
    'NO': 95,   # Superdome
    'PHI': 88,  
    'BAL': 86,
    'GB': 85,
    'BUF': 85,
    'CIN': 82,
    'DEN': 82,  # Altitude affects sound
    'MIN': 80,  # US Bank dome
    # ... add all 32 teams with reasonable estimates
    # Default: 75 for unlisted
}

2. Proxy estimation formula:
   base = STADIUM_NOISE[team]
   × home_away (1.0 if away offense, 0.0 if home offense)
   × situation_intensity (0.3 routine, 0.7 3rd down, 1.0 4th down)
   × game_state (1.0 within 7 pts, 0.75 within 14, 0.5 within 21, 0.3 blowout)
   × quarter_factor (Q1: 0.7, Q2: 0.8, Q3: 0.85, Q4: 1.0, OT: 1.1)
   = estimated_noise_score (0-100)

3. Direct dB conversion (when available):
   dB < 70:      0% impact
   70-85 dB:    -1%
   86-100 dB:   -3%
   101-110 dB:  -5%
   111-120 dB:  -8%
   121-130 dB:  -11%
   > 130 dB:   -13%

4. Play type adjustment:
   Pass plays: full penalty
   Run plays: 50% of penalty
   QB sneaks: 25% of penalty

Create:
- estimate_crowd_noise(game_context) -> float (0-100 score)
- db_to_impact(decibels) -> float (negative multiplier)
- calculate_crowd_modifier(game_context, actual_db=None) -> float

For backtesting, we'll use the proxy model. 
The direct dB input will be used for real-time operation.
```

---

### Prompt 2.6 — Combined Conversion Probability

```
In models/conversion.py, bring all the modifiers together.

Final conversion probability formula:

BASE_RATE = historical 4th down conversion rate for this:
- yards to go (1, 2, 3, 4, 5, 6, 7, 8, 9, 10+)
- field position zone (own 1-20, own 21-50, opp 49-21, red zone)
- Use nflfastR historical data to build this lookup table

MODIFIERS:
- momentum_modifier: (momentum_score - 50) / 500
  (so momentum of 70 = +4%, momentum of 30 = -4%)
  
- weather_modifier: from weather model (typically -0.02 to -0.10)

- fatigue_modifier: net fatigue from fatigue model (+/- 0.07 max)

- injury_modifier: net injury impact (+/- 0.15 typical range)

- crowd_modifier: from crowd noise model (0 to -0.13)

FINAL = BASE_RATE * (1 + momentum_mod + weather_mod + fatigue_mod + injury_mod + crowd_mod)

Clamp final probability between 0.05 and 0.95.

Create:
- build_base_rate_table(play_by_play_df) -> dict
- calculate_conversion_probability(game_context, injuries=None, weather=None, crowd_db=None) -> dict
  Returns: {
      'base_rate': float,
      'momentum_modifier': float,
      'weather_modifier': float,
      'fatigue_modifier': float,
      'injury_modifier': float,
      'crowd_modifier': float,
      'final_probability': float,
      'confidence': 'high'|'medium'|'low'
  }

- ConversionModel class that loads the base rate table and provides prediction interface
```

---

## Phase 3: Backtesting Framework

### Prompt 3.1 — Backtesting Validator

```
In backtesting/validator.py, create the backtesting framework.

Purpose: Compare our context-adjusted model against:
1. What coaches actually did
2. What static analytics would have recommended
3. Actual outcomes

For each 4th down play in the dataset:

1. Get our model's recommendation:
   - Calculate conversion probability with all modifiers
   - Compare go-for-it EV vs punt EV vs FG EV (if in range)
   - Recommend the highest EV option

2. Record:
   - our_recommendation: 'go' | 'punt' | 'fg'
   - our_conversion_prob: float
   - static_recommendation: what nflfastR wp model suggests
   - actual_decision: what coach did
   - actual_outcome: converted, failed, punt_result, fg_result
   - context_factors: dict of all our modifiers

3. Analysis functions:
   - accuracy_vs_static(): when we disagreed with static model, who was right more often?
   - value_added(): sum of WPA for plays where coach followed our rec vs didn't
   - calibration_check(): are our probabilities accurate? (predicted 60% should convert ~60%)
   - modifier_impact(): which modifiers had biggest predictive value?

Create:
- BacktestRunner class
- run_backtest(seasons=[2022, 2023]) -> BacktestResults
- BacktestResults with methods for analysis and visualization
- generate_report() -> markdown summary of findings

Focus on 4th down decisions only for the MVP.
```

---

### Prompt 3.2 — Run Initial Backtest

```
Create a script scripts/run_backtest.py that:

1. Loads the processed play-by-play data with context
2. Builds the base rate table from historical conversions
3. Initializes the ConversionModel
4. Runs the backtest on 2022-2023 seasons
5. Generates a report showing:
   - Overall accuracy of our probability estimates
   - Cases where we disagreed with static analytics
   - Breakdown by modifier (which factors mattered most)
   - Top 10 most impactful plays where our model differed from static

6. Save results to data/processed/backtest_results.json

Run this and show me the output. We need to see if our approach
actually adds value over the baseline models.
```

---

## Phase 4: Real-Time Components

### Prompt 4.1 — Live Data Ingestion

```
Create ingestion/live_feed.py for real-time game data.

Use ESPN's hidden API for live play-by-play:
- Endpoint: http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
- Individual game: http://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}

Create:
- LiveGameFeed class:
  - __init__(game_id)
  - connect() - start polling
  - get_current_situation() -> dict with down, distance, field_pos, score, time
  - get_recent_plays(n=10) -> list of play dicts
  - on_new_play(callback) - register callback for new plays

- parse_espn_play(raw_play) -> standardized play dict matching our schema

- LiveGameTracker class:
  - Maintains rolling game context as plays come in
  - Updates momentum, fatigue calculations in real-time
  - Provides current_context() matching our backtest schema

Test with a completed game to verify parsing works correctly.
```

---

### Prompt 4.2 — Weather API Integration

```
In ingestion/weather_api.py, integrate OpenWeatherMap for real-time weather.

You'll need an API key (user will provide via .env file).

Create:
- get_current_weather(lat, lon) -> dict with temp, wind_speed, wind_direction, conditions
- get_stadium_weather(team_code) -> dict
  (use a lookup table of stadium coordinates)

STADIUM_COORDS = {
    'KC': (39.0489, -94.4839),   # Arrowhead
    'SEA': (47.5952, -122.3316), # Lumen Field
    # ... all 32 stadiums
}

- WeatherTracker class:
  - Updates every 5 minutes during game
  - Caches results to avoid API spam
  - Provides get_current() -> weather dict

Handle API errors gracefully - return None and let the model
use default (no weather adjustment) if API fails.
```

---

### Prompt 4.3 — Injury Input System

```
Create ingestion/injury_feed.py for injury tracking.

Two sources:

1. Pre-game injuries (from NFL.com injury reports):
   - Create InjuryReport class
   - load_weekly_report(week, season) -> dict by team
   - Player status: OUT, DOUBTFUL, QUESTIONABLE, PROBABLE
   - For backtesting: scrape historical injury reports

2. In-game injuries (manual input for real-time):
   - InGameInjuryTracker class
   - add_injury(player_name, team, position, status)
   - remove_injury(player_name) - player returned
   - get_current_injuries(team) -> list

3. X/Twitter monitoring (future enhancement):
   - Stub out XInjuryMonitor class
   - Would poll curated list of beat reporters
   - Surface potential injuries for human confirmation
   - Not implemented in MVP, just create the interface

Create a simple CLI for manual injury entry during games:
- python -m ingestion.injury_feed add "Sauce Gardner" NYJ CB out
- python -m ingestion.injury_feed remove "Sauce Gardner" NYJ
- python -m ingestion.injury_feed list NYJ
```

---

### Prompt 4.4 — Crowd Noise Input

```
Update models/crowd_noise.py to support real-time dB input.

Add:
- CrowdNoiseTracker class:
  - set_db_reading(decibels, timestamp)
  - get_current_estimate(game_context) -> dict
    Returns either direct reading (if recent) or proxy estimate
  - is_reading_stale(max_age_seconds=90) -> bool

- Simple input interface:
  - Accept dB reading from command line or API call
  - Timestamp each reading
  - Fall back to proxy if no recent reading

The interface should make it easy for someone watching the broadcast
to input the dB reading when it appears on screen:

python -m models.crowd_noise set 118

This updates the current reading which the model will use for 
the next recommendation.
```

---

## Phase 5: Recommendation Interface

### Prompt 5.1 — Core Recommendation Engine

```
Create a new file interface/recommender.py

RecommendationEngine class:
- __init__(conversion_model, live_feed, weather_tracker, injury_tracker, noise_tracker)

- get_recommendation(situation=None) -> Recommendation
  If situation is None, uses live_feed.get_current_situation()
  
  Returns Recommendation object:
  {
    'situation': {
      'down': 4,
      'distance': 3,
      'field_position': 'OPP 41',
      'score_diff': -7,
      'time_remaining': '6:22 Q4',
      'team': 'KC',
      'opponent': 'BUF'
    },
    'options': {
      'go_for_it': {
        'conversion_prob': 0.58,
        'success_wp': 0.72,
        'fail_wp': 0.41,
        'expected_wp': 0.59,
        'recommendation_strength': 'strong'
      },
      'punt': {
        'expected_wp': 0.52,
        'net_yards_expected': 38
      },
      'field_goal': {
        'in_range': True,
        'make_prob': 0.78,
        'expected_wp': 0.54
      }
    },
    'recommendation': 'go_for_it',
    'confidence': 'high',
    'key_factors': [
      {'factor': 'momentum', 'impact': '+4.2%', 'detail': 'Offense 7/10 on recent plays'},
      {'factor': 'crowd_noise', 'impact': '-8.1%', 'detail': 'Arrowhead, 116 dB'},
      {'factor': 'injuries', 'impact': '+3.4%', 'detail': 'CB1 out for defense'}
    ],
    'comparison_to_static': {
      'static_recommendation': 'go_for_it',
      'agrees': True,
      'our_conversion_prob': 0.58,
      'static_conversion_prob': 0.54,
      'difference_reason': 'Momentum and injury factors increase our estimate'
    }
  }

- explain_recommendation() -> str
  Human-readable explanation of the recommendation
```

---

### Prompt 5.2 — Terminal Dashboard

```
Create interface/dashboard.py - a simple terminal-based dashboard.

Using the 'rich' library for terminal formatting.

Dashboard shows:

┌─────────────────────────────────────────────────────────────────┐
│  KC @ BUF                                    Q4  6:22           │
│  Chiefs 21 - Bills 28                        KC ball            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SITUATION: 4th & 3 at BUF 41                                   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  GO FOR IT   │  │    PUNT      │  │  FIELD GOAL  │          │
│  │              │  │              │  │              │          │
│  │  Win Prob    │  │  Win Prob    │  │  Out of      │          │
│  │   +7.2%      │  │   +0.4%      │  │  Range       │          │
│  │              │  │              │  │              │          │
│  │  Conv: 58%   │  │  Net: 38 yds │  │              │          │
│  │  ★ BEST ★    │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  CONTEXT FACTORS                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  ⚡ Momentum:      +4.2%   (7/10 recent plays successful)       │
│  📢 Crowd noise:  -8.1%   (116 dB - DIRECT)                     │
│  🏥 Injuries:     +3.4%   (DEF: CB1 out | OFF: all healthy)    │
│  😰 Fatigue:      +1.8%   (Defense 12 consecutive plays)        │
│  🌬️ Weather:      -1.2%   (Wind 15mph, 42°F)                   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  [I] Add injury  [D] Enter dB  [R] Refresh  [Q] Quit           │
└─────────────────────────────────────────────────────────────────┘

Features:
- Auto-refreshes when new play detected
- Keyboard shortcuts for manual inputs
- Color coding: green for recommended, yellow for close, red for avoid
- Flashing/highlight on 4th down situations

Create:
- TerminalDashboard class
- run() method that starts the live display
- Handle keyboard input for injury/dB updates
```

---

### Prompt 5.3 — Main Entry Point

```
Create main.py as the primary entry point.

Commands:

# Run backtest on historical data
python main.py backtest --seasons 2022 2023

# Start live tracking for a specific game
python main.py live --game-id 401547654

# Start live tracking, auto-detect current game for a team
python main.py live --team KC

# Run in demo mode with a historical game
python main.py demo --game-id 401547654

# Generate backtest report
python main.py report --output results.md

Use argparse for CLI handling.
Include --verbose flag for debug output.
Include --no-weather flag to skip weather API (for testing).

Each command should have helpful error messages and 
validate inputs before running.
```

---

## Phase 6: Documentation & Polish

### Prompt 6.1 — Documentation

```
Create comprehensive documentation:

1. README.md - Project overview:
   - What this does and why it's better than static analytics
   - Quick start guide
   - Screenshots/examples of output
   - Architecture overview

2. docs/ALGORITHM.md - Detailed algorithm documentation:
   - Momentum calculation with examples
   - Each modifier explained
   - How factors combine
   - Calibration methodology

3. docs/DATA_SOURCES.md - Data source documentation:
   - nflfastR for historical data
   - ESPN API for live data
   - Weather API setup
   - Injury data sources
   - Stadium noise data

4. docs/BACKTEST_RESULTS.md - Template for backtest findings:
   - Methodology
   - Key findings
   - Comparison to static models
   - Limitations and future work

5. CONTRIBUTING.md - For future contributors:
   - Code style
   - How to add new modifiers
   - Testing requirements
```

---

### Prompt 6.2 — Configuration & Calibration

```
Create config/settings.py with all tunable parameters:

# Momentum weights
MOMENTUM_WEIGHTS = {
    'recent_success': 0.40,
    'drive_efficiency': 0.25,
    'scoring_recency': 0.20,
    'turnover_impact': 0.15
}

# Weather thresholds
WIND_THRESHOLDS = {
    'light': 10,
    'moderate': 15,
    'strong': 20
}

# Stadium noise ratings
STADIUM_NOISE_RATINGS = {
    'KC': 98,
    'SEA': 96,
    # ... all teams
}

# Position weights for injuries
POSITION_WEIGHTS = {
    'short': {...},
    'medium': {...},
    'long': {...}
}

# API configuration
ESPN_BASE_URL = "http://site.api.espn.com/apis/site/v2/sports/football/nfl"
WEATHER_API_KEY_ENV = "OPENWEATHER_API_KEY"

# Model calibration
PROBABILITY_FLOOR = 0.05
PROBABILITY_CEILING = 0.95

Create a CalibrationManager class that can:
- Load current weights
- Run calibration against backtest data
- Suggest improved weights
- Save calibrated settings
```

---

## Additional Prompts as Needed

### If Backtest Shows Poor Calibration

```
The backtest shows our probabilities are not well-calibrated.
When we predict 60% conversion, actual rate is [X]%.

Analyze the calibration data and:
1. Identify which modifiers are over/under-weighted
2. Suggest adjusted weights
3. Implement a calibration routine that optimizes weights
   against historical outcomes
4. Re-run backtest with calibrated weights
5. Show before/after comparison
```

### If You Need Better Base Rates

```
The base conversion rate table seems too coarse.
Improve it by:

1. Add more granular field position zones (every 10 yards)
2. Factor in team offensive/defensive rankings
3. Consider time remaining more precisely
4. Add score differential as a factor in base rates
5. Use logistic regression to build a proper base rate model
   instead of simple lookup tables
```

### For Future X/Twitter Integration

```
Implement the XInjuryMonitor class stub.

Using tweepy or similar:
1. Maintain a curated list of beat reporters (2-3 per team)
2. Poll their recent tweets during games
3. Use simple keyword matching for injury-related tweets:
   - "injury", "hurt", "locker room", "questionable", "out"
   - Player names from active roster
4. Surface potential injuries with the original tweet text
5. Require human confirmation before adding to tracker

Create:
- BEAT_REPORTERS dict mapping team -> list of Twitter handles
- XMonitor class with poll() and get_alerts() methods
- Alert object with tweet_text, detected_player, confidence
```

---

## Success Criteria

After completing these prompts, you should have:

1. ✅ Historical data loaded and processed (2018-2024)
2. ✅ All five modifiers implemented and tested
3. ✅ Backtest showing improvement over static models
4. ✅ Real-time data ingestion working
5. ✅ Terminal dashboard for live game tracking
6. ✅ Manual input system for injuries and crowd noise
7. ✅ Documentation for all components

The system should be able to:
- Run backtests proving the concept works
- Track a live game and provide real-time recommendations
- Clearly explain WHY it's recommending each decision
- Show how it differs from static analytics and why
