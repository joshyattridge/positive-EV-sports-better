#!/usr/bin/env python3
"""
Quick test to verify the de-vig fix is working correctly.
This simulates the Idaho vs Bakersfield scenario.
"""

from src.utils.odds_utils import remove_vig_proportional, calculate_implied_probability, calculate_ev

# Pinnacle odds from the user's example
pinnacle_idaho = 1.315
pinnacle_bakersfield = 3.590

# William Hill odds
wh_idaho = 1.3333  # 1/3 in decimal

print("=" * 60)
print("Testing De-Vig Fix - Idaho vs Bakersfield Example")
print("=" * 60)

# Calculate without de-vig (old buggy method)
print("\n❌ OLD METHOD (INCORRECT - just using sharp odds directly):")
prob_no_devig = 1 / pinnacle_idaho
print(f"   Pinnacle Idaho: {pinnacle_idaho}")
print(f"   True probability: {prob_no_devig:.4f} ({prob_no_devig*100:.2f}%)")
ev_no_devig = calculate_ev(wh_idaho, prob_no_devig)
print(f"   EV at WH {wh_idaho}: {ev_no_devig*100:+.2f}%")
print(f"   ⚠️  This shows +EV but is WRONG!")

# Calculate WITH proper de-vig (new correct method)
print("\n✅ NEW METHOD (CORRECT - de-vig both sides first):")
print(f"   Pinnacle Idaho: {pinnacle_idaho}")
print(f"   Pinnacle Bakersfield: {pinnacle_bakersfield}")

# Calculate implied probabilities
implied_idaho = 1 / pinnacle_idaho
implied_bakersfield = 1 / pinnacle_bakersfield
total_implied = implied_idaho + implied_bakersfield
margin = (total_implied - 1) * 100

print(f"   Implied probabilities (with vig):")
print(f"     Idaho: {implied_idaho:.4f} ({implied_idaho*100:.2f}%)")
print(f"     Bakersfield: {implied_bakersfield:.4f} ({implied_bakersfield*100:.2f}%)")
print(f"     Total: {total_implied:.4f} (margin: {margin:.2f}%)")

# De-vig using proportional method
fair_odds = remove_vig_proportional([pinnacle_idaho, pinnacle_bakersfield])
fair_prob_idaho = 1 / fair_odds[0]
fair_prob_bakersfield = 1 / fair_odds[1]

print(f"   Fair odds (after de-vig):")
print(f"     Idaho: {fair_odds[0]:.4f}")
print(f"     Bakersfield: {fair_odds[1]:.4f}")
print(f"   Fair probabilities:")
print(f"     Idaho: {fair_prob_idaho:.4f} ({fair_prob_idaho*100:.2f}%)")
print(f"     Bakersfield: {fair_prob_bakersfield:.4f} ({fair_prob_bakersfield*100:.2f}%)")
print(f"     Total: {fair_prob_idaho + fair_prob_bakersfield:.4f}")

# Calculate EV with proper de-vig
ev_devig = calculate_ev(wh_idaho, fair_prob_idaho)
print(f"\n   EV at WH {wh_idaho}: {ev_devig*100:+.2f}%")

# Determine if it's +EV or -EV
if ev_devig > 0:
    print(f"   ✅ This IS positive EV")
else:
    print(f"   ❌ This is NEGATIVE EV (correctly identified!)")

print("\n" + "=" * 60)
print("COMPARISON:")
print("=" * 60)
print(f"Old method EV: {ev_no_devig*100:+.2f}% (WRONG - false positive)")
print(f"New method EV: {ev_devig*100:+.2f}% (CORRECT)")
print(f"Difference: {(ev_no_devig - ev_devig)*100:.2f} percentage points")
print("=" * 60)
