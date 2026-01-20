# Algorithm Documentation

## Momentum Scoring

The momentum score (0-100) is calculated based on:
- Recent play success (40%)
- Drive efficiency vs season average (25%)
- Scoring recency (20%)
- Turnover impact (15%)

## Combined Conversion Probability

`FINAL = BASE_RATE * (1 + momentum_mod + weather_mod + fatigue_mod + injury_mod + crowd_mod)`

- **Base Rate**: Historical conversion % for the specific distance and field zone.
- **Momentum**: `(Score - 50) / 500`.
- **Weather**: Negative multiplier for high wind or precipitation.
- **Fatigue**: Positive modifier if defense is tired; negative if offense is tired.
- **Injuries**: Position-weighted impact of inactive players.
- **Crowd Noise**: dB-based penalty for away offenses.
