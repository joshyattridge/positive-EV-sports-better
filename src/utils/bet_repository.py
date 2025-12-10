"""
Bet Repository Module

Handles reading and querying bet history data.
Separated from BetLogger to follow single responsibility principle.
"""

import csv
from typing import Dict, Any, Set
from pathlib import Path


class BetRepository:
    """
    Repository class for querying bet history data.
    Provides read-only access to bet logs.
    """
    
    def __init__(self, log_path: str = "data/bet_history.csv"):
        """
        Initialize the bet repository.
        
        Args:
            log_path: Path to the bet history CSV file
        """
        self.log_path = Path(log_path)
    
    def get_already_bet_game_ids(self) -> Set[str]:
        """
        Get a set of game IDs that already have bets placed on them.
        
        Returns:
            Set of game IDs (strings) that have bets in the history
        """
        game_ids = set()
        
        try:
            if not self.log_path.exists():
                return game_ids
            
            with open(self.log_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    game_id = row.get('game_id', '').strip()
                    # Only add if game_id exists and bet was actually placed (not 'not_placed')
                    if game_id and row.get('bet_result') != 'not_placed':
                        game_ids.add(game_id)
            
        except Exception as e:
            print(f"⚠️  Error reading bet history for game IDs: {e}")
        
        return game_ids
    
    def get_failed_bet_opportunities(self, max_failures: int = 3) -> Set[tuple]:
        """
        Get a set of unique bet opportunities that have failed multiple times.
        
        This identifies bets that have been attempted but not placed (failed) 
        multiple times, so they can be skipped in future runs.
        
        Args:
            max_failures: Maximum number of failures before ignoring (default: 3)
            
        Returns:
            Set of tuples (game_id, market, outcome) for failed bets
        """
        failed_bets = {}  # key: (game_id, market, outcome), value: failure count
        
        try:
            if not self.log_path.exists():
                return set()
            
            with open(self.log_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    game_id = row.get('game_id', '').strip()
                    market = row.get('market', '').strip()
                    outcome = row.get('outcome', '').strip()
                    bet_result = row.get('bet_result', '').strip()
                    
                    # Count failures (not_placed status)
                    if game_id and market and outcome and bet_result == 'not_placed':
                        key = (game_id, market, outcome)
                        failed_bets[key] = failed_bets.get(key, 0) + 1
            
            # Return only those that have failed >= max_failures times
            ignored_bets = {key for key, count in failed_bets.items() if count >= max_failures}
            
            if ignored_bets:
                print(f"🚫 Ignoring {len(ignored_bets)} bet opportunities that failed {max_failures}+ times")
            
            return ignored_bets
            
        except Exception as e:
            print(f"⚠️  Error reading failed bet history: {e}")
            return set()
    
    def get_bet_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all logged bets.
        
        Returns:
            Dictionary with bet statistics
        """
        try:
            if not self.log_path.exists():
                return {
                    'total_bets': 0,
                    'total_stake': 0,
                    'total_expected_profit': 0,
                    'total_actual_profit': 0,
                    'wins': 0,
                    'losses': 0,
                    'pending': 0,
                    'not_placed': 0,
                    'win_rate': 0
                }
            
            total_bets = 0
            total_stake = 0.0
            total_expected_profit = 0.0
            total_actual_profit = 0.0
            wins = 0
            losses = 0
            pending = 0
            not_placed = 0
            
            with open(self.log_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_bets += 1
                    
                    # Sum stakes and expected profits
                    try:
                        total_stake += float(row.get('recommended_stake', 0))
                        total_expected_profit += float(row.get('expected_profit', 0))
                    except (ValueError, TypeError):
                        pass
                    
                    # Count results
                    result = row.get('bet_result', 'pending')
                    if result == 'win':
                        wins += 1
                    elif result == 'loss':
                        losses += 1
                    elif result == 'pending':
                        pending += 1
                    elif result == 'not_placed':
                        not_placed += 1
                    
                    # Sum actual profit/loss
                    try:
                        apl = row.get('actual_profit_loss', '')
                        if apl and apl != '':
                            total_actual_profit += float(apl)
                    except (ValueError, TypeError):
                        pass
            
            return {
                'total_bets': total_bets,
                'total_stake': total_stake,
                'total_expected_profit': total_expected_profit,
                'total_actual_profit': total_actual_profit,
                'wins': wins,
                'losses': losses,
                'pending': pending,
                'not_placed': not_placed,
                'win_rate': (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            }
            
        except Exception as e:
            return {
                'error': f'Error reading bet history: {str(e)}'
            }
    
    def print_summary(self):
        """
        Print a summary of all logged bets.
        """
        summary = self.get_bet_summary()
        
        if 'error' in summary:
            print(f"⚠️  {summary['error']}")
            return
        
        print("\n" + "="*80)
        print("📊 BET HISTORY SUMMARY")
        print("="*80)
        print(f"Total Bets Logged: {summary['total_bets']}")
        print(f"Total Stake: £{summary['total_stake']:.2f}")
        print(f"Total Expected Profit: £{summary['total_expected_profit']:.2f}")
        print(f"\nBet Status:")
        print(f"  ✅ Wins: {summary['wins']}")
        print(f"  ❌ Losses: {summary['losses']}")
        print(f"  ⏳ Pending: {summary['pending']}")
        print(f"  🚫 Not Placed: {summary['not_placed']}")
        
        if summary['wins'] + summary['losses'] > 0:
            print(f"\n📈 Win Rate: {summary['win_rate']:.1f}%")
            print(f"💰 Actual P/L: £{summary['total_actual_profit']:.2f}")
        
        print("="*80 + "\n")
