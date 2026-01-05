# Worst-Case Vig Removal Method

## Overview

The **worst-case** vig removal method is a conservative approach to removing bookmaker margins from odds. It provides the most pessimistic estimate of true probabilities, making it ideal for risk-averse betting strategies.

## When to Use Worst-Case

### Recommended For:
- **Conservative bankroll management** - When you want maximum protection
- **Uncertain markets** - When sharp book odds vary significantly  
- **Risk-averse strategies** - When you prefer fewer, higher-confidence bets
- **Learning phase** - When you're still validating your betting approach
- **Volatile sports** - Sports with high variance or unpredictable outcomes

### Not Recommended For:
- **Aggressive growth strategies** - May filter out too many opportunities
- **High-volume betting** - Reduces number of qualifying bets significantly
- **Well-established markets** - When sharp books agree and vig is low

## How It Works

The worst-case method assumes the **full vig burden** falls on each individual outcome, then normalizes probabilities. This creates a conservative lower bound on true probabilities.

### Example:

```
Original odds: [1.95, 1.95]
Total implied probability: 102.56%
Vig: 2.56%

Worst-case logic:
- Assume each outcome bears the FULL 2.56% vig penalty
- Results in more conservative probability estimates
- Reduces estimated edge on all bets
```

## Configuration

In your `.env` file:

```bash
# Enable vig adjustment
USE_VIG_ADJUSTED_EV=true

# Set method to worst_case
VIG_REMOVAL_METHOD=worst_case
```

## Available Methods Comparison

| Method | Approach | Use Case |
|--------|----------|----------|
| **proportional** | Simple, even distribution | General purpose, balanced |
| **power** | Accounts for favorite-longshot bias | When favorites are overbet |
| **shin** | Accounts for insider trading | Most accurate theoretical fair value |
| **worst_case** | Maximum vig penalty | Conservative risk management |

## Impact on Betting

### Expected Results:
- ✅ **Fewer bets** - Only the strongest edges pass the filter
- ✅ **Higher confidence** - Bets that qualify have edges even under pessimistic assumptions
- ✅ **Lower variance** - Conservative estimates reduce overconfidence
- ✅ **Bankroll protection** - Helps avoid betting on edges that may not exist

### Trade-offs:
- ❌ **Missed opportunities** - May filter out genuine +EV bets
- ❌ **Slower growth** - Fewer bets means slower bankroll growth (but safer)
- ❌ **Over-conservative** - May underestimate your true edge

## Testing the Method

Run the test script to see worst-case in action:

```bash
PYTHONPATH=. python tests/test_devig_worst_case.py
```

This demonstrates how worst-case compares to other methods across different market types.

## Recommendations

### For Beginners:
Start with `worst_case` for the first 100-200 bets to:
- Build confidence in the system
- Protect your bankroll during the learning phase
- Only bet when edges are very clear

### For Experienced Bettors:
- Use `shin` for most accurate theoretical edges
- Switch to `worst_case` during uncertain periods (injuries, news, volatility)
- Consider using `worst_case` for larger stake sizes

### For Aggressive Growth:
- Use `proportional` or `power` methods
- Accept higher variance for potentially higher returns
- Ensure you have adequate bankroll to handle swings

## Mathematical Foundation

The worst-case method applies maximum vig penalty before normalization:

```
fair_probability[i] = implied_probability[i] / (1 + total_vig)
```

Then normalizes to ensure probabilities sum to 1.0:

```
normalized_probability[i] = fair_probability[i] / sum(fair_probabilities)
```

This ensures each outcome bears the maximum possible vig burden, giving you the most conservative estimate.

## Validation

All existing tests pass with the worst-case method added:
- ✅ EV calculation tests
- ✅ Devig multiple outcomes tests  
- ✅ Integration with scanner
- ✅ Kelly criterion calculations

## Support

For issues or questions about the worst-case method, check:
1. This documentation
2. Test output: `tests/test_devig_worst_case.py`
3. Implementation: `src/utils/odds_utils.py` (function: `remove_vig_worst_case`)
