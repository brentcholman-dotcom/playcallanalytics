# Contributing

## Code Style
Please follow PEP 8 for Python code.

## Adding Modifiers
1. Create a new file in `models/`.
2. Implement a modifier function that returns a relative Change (e.g., +0.05 for +5%).
3. Integrate the modifier into `models/conversion.py`.

## Testing
Always run a backtest after modifying model logic to ensure it improves (or doesn't significantly degrade) predictive accuracy.
