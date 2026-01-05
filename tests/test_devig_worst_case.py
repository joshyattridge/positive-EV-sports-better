#!/usr/bin/env python3
"""
Test worst-case devig method to demonstrate conservative approach.
"""

from src.utils.odds_utils import (
    remove_vig_proportional,
    remove_vig_power,
    remove_vig_shin,
    remove_vig_worst_case,
    calculate_ev
)

print("=" * 70)
print("Testing Worst-Case Devig Method (Conservative Approach)")
print("=" * 70)

# Example: 2-way market with typical bookmaker vig
print("\n📊 SCENARIO: NBA Game - Team A vs Team B")
print("-" * 70)

odds_2way = [1.95, 1.95]  # Typical symmetric market with ~2.5% vig per side
print(f"Bookmaker odds: {odds_2way}")

# Calculate implied probabilities
implied = [1/o for o in odds_2way]
print(f"Implied probs: {[f'{p:.4f}' for p in implied]} (sum: {sum(implied):.4f})")
margin = (sum(implied) - 1) * 100
print(f"Vig/Margin: {margin:.2f}%")

# Apply different devig methods
print("\n🔬 DEVIG RESULTS:")
print("-" * 70)

proportional = remove_vig_proportional(odds_2way)
power = remove_vig_power(odds_2way)
shin = remove_vig_shin(odds_2way)
worst_case = remove_vig_worst_case(odds_2way)

print(f"Proportional:  {[f'{o:.4f}' for o in proportional]} → probs: {[f'{1/o:.4f}' for o in proportional]}")
print(f"Power:         {[f'{o:.4f}' for o in power]} → probs: {[f'{1/o:.4f}' for o in power]}")
print(f"Shin:          {[f'{o:.4f}' for o in shin]} → probs: {[f'{1/o:.4f}' for o in shin]}")
print(f"Worst-case:    {[f'{o:.4f}' for o in worst_case]} → probs: {[f'{1/o:.4f}' for o in worst_case]}")

# Show the conservative difference
print("\n📉 CONSERVATISM IMPACT:")
print("-" * 70)
print(f"Proportional Team A prob: {1/proportional[0]:.4f} ({(1/proportional[0])*100:.2f}%)")
print(f"Worst-case Team A prob:   {1/worst_case[0]:.4f} ({(1/worst_case[0])*100:.2f}%)")
print(f"Difference:               {(1/proportional[0] - 1/worst_case[0])*100:.2f} percentage points")

# Example 2: Asymmetric market (favorite vs underdog)
print("\n\n📊 SCENARIO 2: NFL Game - Heavy Favorite vs Underdog")
print("-" * 70)

odds_asymmetric = [1.45, 3.20]  # Favorite at 1.45, Underdog at 3.20 (with vig)
print(f"Bookmaker odds: {odds_asymmetric}")

implied = [1/o for o in odds_asymmetric]
print(f"Implied probs: {[f'{p:.4f}' for p in implied]} (sum: {sum(implied):.4f})")
margin = (sum(implied) - 1) * 100
print(f"Vig/Margin: {margin:.2f}%")

# Apply different devig methods
print("\n🔬 DEVIG RESULTS:")
print("-" * 70)

proportional = remove_vig_proportional(odds_asymmetric)
power = remove_vig_power(odds_asymmetric)
shin = remove_vig_shin(odds_asymmetric)
worst_case = remove_vig_worst_case(odds_asymmetric)

print(f"Proportional:  {[f'{o:.4f}' for o in proportional]}")
print(f"  Favorite: {1/proportional[0]:.4f} ({(1/proportional[0])*100:.2f}%), Underdog: {1/proportional[1]:.4f} ({(1/proportional[1])*100:.2f}%)")
print(f"Power:         {[f'{o:.4f}' for o in power]}")
print(f"  Favorite: {1/power[0]:.4f} ({(1/power[0])*100:.2f}%), Underdog: {1/power[1]:.4f} ({(1/power[1])*100:.2f}%)")
print(f"Shin:          {[f'{o:.4f}' for o in shin]}")
print(f"  Favorite: {1/shin[0]:.4f} ({(1/shin[0])*100:.2f}%), Underdog: {1/shin[1]:.4f} ({(1/shin[1])*100:.2f}%)")
print(f"Worst-case:    {[f'{o:.4f}' for o in worst_case]}")
print(f"  Favorite: {1/worst_case[0]:.4f} ({(1/worst_case[0])*100:.2f}%), Underdog: {1/worst_case[1]:.4f} ({(1/worst_case[1])*100:.2f}%)")

# Example 3: EV calculation comparison
print("\n\n💰 EV CALCULATION EXAMPLE:")
print("-" * 70)
print("You find Underdog at 3.35 on another bookmaker")
print("Sharp book (Pinnacle) has: Favorite 1.45, Underdog 3.20")

bet_odds = 3.35
sharp_market = [1.45, 3.20]

print("\n🔬 EV with different devig methods:")
print("-" * 70)

# Proportional
prop_fair = remove_vig_proportional(sharp_market)
prop_true_prob = 1 / prop_fair[1]  # Underdog probability
prop_ev = calculate_ev(bet_odds, prop_true_prob)
print(f"Proportional: True prob = {prop_true_prob:.4f} → EV = {prop_ev*100:+.2f}%")

# Power
power_fair = remove_vig_power(sharp_market)
power_true_prob = 1 / power_fair[1]
power_ev = calculate_ev(bet_odds, power_true_prob)
print(f"Power:        True prob = {power_true_prob:.4f} → EV = {power_ev*100:+.2f}%")

# Shin
shin_fair = remove_vig_shin(sharp_market)
shin_true_prob = 1 / shin_fair[1]
shin_ev = calculate_ev(bet_odds, shin_true_prob)
print(f"Shin:         True prob = {shin_true_prob:.4f} → EV = {shin_ev*100:+.2f}%")

# Worst-case
wc_fair = remove_vig_worst_case(sharp_market)
wc_true_prob = 1 / wc_fair[1]
wc_ev = calculate_ev(bet_odds, wc_true_prob)
print(f"Worst-case:   True prob = {wc_true_prob:.4f} → EV = {wc_ev*100:+.2f}%")

print("\n" + "=" * 70)
print("CONCLUSION:")
print("=" * 70)
print("✅ Worst-case method provides most conservative EV estimates")
print("✅ Only bets when edge persists under pessimistic assumptions")
print("✅ Recommended for bankroll protection and risk management")
print("✅ May reduce number of bets, but increases confidence in +EV")
print("=" * 70)
