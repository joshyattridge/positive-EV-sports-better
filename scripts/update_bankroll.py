import csv

input_file = 'data/paper_trade_history.csv'
output_file = 'data/paper_trade_history.csv'

# Read the CSV and update related columns
with open(input_file, 'r') as infile:
    reader = csv.reader(infile)
    rows = list(reader)
    
    header = rows[0]
    # Find column indices
    bankroll_idx = header.index('bankroll')
    kelly_pct_idx = header.index('kelly_percentage')
    kelly_frac_idx = header.index('kelly_fraction')
    rec_stake_idx = header.index('recommended_stake')
    exp_profit_idx = header.index('expected_profit')
    bet_odds_idx = header.index('bet_odds')
    bet_result_idx = header.index('bet_result')
    actual_pl_idx = header.index('actual_profit_loss')
    
    # Process each row
    for i, row in enumerate(rows):
        if i == 0:  # Skip header
            continue
        
        if len(row) > max(bankroll_idx, kelly_pct_idx, rec_stake_idx, exp_profit_idx, actual_pl_idx):
            old_bankroll = float(row[bankroll_idx])
            new_bankroll = 1000.0
            
            # Calculate the ratio
            ratio = new_bankroll / old_bankroll
            
            # Update recommended_stake
            old_stake = float(row[rec_stake_idx])
            new_stake = old_stake * ratio
            row[rec_stake_idx] = str(new_stake)
            
            # Update expected_profit
            old_exp_profit = float(row[exp_profit_idx])
            new_exp_profit = old_exp_profit * ratio
            row[exp_profit_idx] = str(new_exp_profit)
            
            # Update actual_profit_loss based on bet result
            bet_result = row[bet_result_idx]
            if bet_result == 'win':
                bet_odds = float(row[bet_odds_idx])
                new_actual_pl = new_stake * (bet_odds - 1)
                row[actual_pl_idx] = str(new_actual_pl)
            elif bet_result == 'loss':
                row[actual_pl_idx] = str(-new_stake)
            elif bet_result == 'void':
                row[actual_pl_idx] = '0.0'
            elif bet_result == 'pending':
                row[actual_pl_idx] = ''
            
            # Update bankroll
            row[bankroll_idx] = '1000.0'

# Write back to the same file
with open(output_file, 'w', newline='') as outfile:
    writer = csv.writer(outfile)
    writer.writerows(rows)

print(f"Updated {len(rows) - 1} rows")
print("\nSample of first 5 updated rows:")
print("Row | Bankroll | Stake | Expected Profit | Actual P/L | Result")
print("-" * 70)
for i in range(1, min(6, len(rows))):
    row = rows[i]
    print(f"{i:3} | {row[bankroll_idx]:8} | {row[rec_stake_idx]:6} | {row[exp_profit_idx]:15} | {row[actual_pl_idx]:10} | {row[bet_result_idx]}")
