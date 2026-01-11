#!/usr/bin/env python3
"""
Recalculate backtest results with dynamic bankroll based on actual bet outcomes.
"""

import csv
from decimal import Decimal, ROUND_HALF_UP

def recalculate_backtest_with_dynamic_bankroll(input_file, output_file, initial_bankroll=1000.0):
    """
    Recalculate bet stakes and P/L with dynamic bankroll that updates after each bet.
    """
    current_bankroll = Decimal(str(initial_bankroll))
    
    with open(input_file, 'r') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    updated_rows = []
    
    for row in rows:
        # Update bankroll to current value
        row['bankroll'] = str(float(current_bankroll))
        
        # Get kelly percentage and convert to decimal
        kelly_pct = Decimal(row['kelly_percentage']) / Decimal('100')
        
        # Calculate new recommended stake based on current bankroll
        recommended_stake = current_bankroll * kelly_pct
        # Round to 2 decimal places
        recommended_stake = recommended_stake.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Apply minimum stake of 5
        recommended_stake = max(recommended_stake, Decimal('5.0'))
        row['recommended_stake'] = str(float(recommended_stake))
        
        # Recalculate expected profit
        bet_odds = Decimal(row['bet_odds'])
        ev_pct = Decimal(row['ev_percentage']) / Decimal('100')
        expected_profit = recommended_stake * ev_pct
        expected_profit = expected_profit.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        row['expected_profit'] = str(float(expected_profit))
        
        # Recalculate actual P/L based on bet result
        bet_result = row['bet_result']
        if bet_result == 'win':
            actual_pl = recommended_stake * (bet_odds - Decimal('1'))
        elif bet_result == 'loss':
            actual_pl = -recommended_stake
        else:
            # Handle push/void
            actual_pl = Decimal('0')
        
        actual_pl = actual_pl.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        row['actual_profit_loss'] = str(float(actual_pl))
        
        # Update current bankroll for next bet
        current_bankroll += actual_pl
        
        updated_rows.append(row)
    
    # Write updated data to output file
    with open(output_file, 'w', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    print(f"✓ Recalculated {len(updated_rows)} bets")
    print(f"Starting bankroll: £{initial_bankroll:.2f}")
    print(f"Final bankroll: £{float(current_bankroll):.2f}")
    print(f"Total P/L: £{float(current_bankroll - Decimal(str(initial_bankroll))):.2f}")
    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    input_file = "data/backtest_bet_history.csv"
    output_file = "data/backtest_bet_history_recalculated.csv"
    
    recalculate_backtest_with_dynamic_bankroll(input_file, output_file)
