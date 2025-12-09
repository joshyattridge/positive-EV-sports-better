#!/usr/bin/env python3
"""
Show Ignored Bets Script

Displays bets that have failed multiple times and are being ignored in future scans.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.bet_logger import BetLogger
import csv


def show_ignored_bets(max_failures: int = 3):
    """
    Display bets that are being ignored due to multiple failures.
    
    Args:
        max_failures: Threshold for ignoring bets (default: 3)
    """
    logger = BetLogger()
    failed_opportunities = logger.get_failed_bet_opportunities(max_failures=max_failures)
    
    if not failed_opportunities:
        print(f"\n✅ No bets are currently being ignored (threshold: {max_failures} failures)")
        return
    
    print(f"\n{'='*80}")
    print(f"IGNORED BETS (failed {max_failures}+ times)")
    print(f"{'='*80}\n")
    
    # Get additional details about these bets from the log
    bet_details = {}
    
    with open(logger.log_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            game_id = row.get('game_id', '').strip()
            market = row.get('market', '').strip()
            outcome = row.get('outcome', '').strip()
            key = (game_id, market, outcome)
            
            if key in failed_opportunities:
                if key not in bet_details:
                    bet_details[key] = {
                        'sport': row.get('sport', ''),
                        'game': row.get('game', ''),
                        'bookmaker': row.get('bookmaker', ''),
                        'failures': 0,
                        'last_notes': ''
                    }
                
                bet_result = row.get('bet_result', '').strip()
                if bet_result == 'not_placed':
                    bet_details[key]['failures'] += 1
                    bet_details[key]['last_notes'] = row.get('notes', '')
    
    # Display each ignored bet
    for i, (key, details) in enumerate(bet_details.items(), 1):
        game_id, market, outcome = key
        print(f"{i}. {details['sport'].upper()}")
        print(f"   Game: {details['game']}")
        print(f"   Market: {market}")
        print(f"   Outcome: {outcome}")
        print(f"   Bookmaker: {details['bookmaker']}")
        print(f"   Failures: {details['failures']}")
        print(f"   Last Error: {details['last_notes'][:100]}...")
        print(f"   Game ID: {game_id}")
        print()
    
    print(f"{'='*80}")
    print(f"\nThese {len(failed_opportunities)} bet(s) will be skipped in future scans.")
    print(f"To change this threshold, set MAX_BET_FAILURES in your .env file.")
    print(f"Set MAX_BET_FAILURES=0 to disable this feature entirely.")
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Show bets being ignored due to multiple failures')
    parser.add_argument(
        '--threshold',
        type=int,
        default=3,
        help='Minimum number of failures to consider a bet ignored (default: 3)'
    )
    
    args = parser.parse_args()
    show_ignored_bets(max_failures=args.threshold)
