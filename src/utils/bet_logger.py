"""
Bet Logger Module

This module provides functionality to log all placed bets to a CSV file
for tracking and analysis. Records comprehensive bet details including
opportunity info, kelly sizing, EV calculations, and leaves room for result tracking.
"""

import csv
import os
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class BetLogger:
    """
    A class to manage logging of placed bets to CSV files.
    
    Each bet record includes:
    - Timestamp
    - Game/event details
    - Bet selection and market
    - Bookmaker info
    - Odds information (bet odds, sharp average)
    - Kelly criterion sizing
    - EV calculations
    - Probabilities
    - Bet result (win/loss/pending) - to be filled in later
    """
    
    # CSV column headers
    CSV_HEADERS = [
        'timestamp',
        'date_placed',
        'game_id',
        'sport',
        'game',
        'commence_time',
        'market',
        'outcome',
        'bookmaker',
        'bookmaker_key',
        'bet_odds',
        'sharp_avg_odds',
        'true_probability_pct',
        'bookmaker_probability_pct',
        'ev_percentage',
        'bankroll',
        'kelly_percentage',
        'kelly_fraction',
        'recommended_stake',
        'expected_profit',
        'bookmaker_url',
        'bet_result',  # Empty - to be filled: 'win', 'loss', 'void', 'pending'
        'actual_profit_loss',  # Empty - to be filled with actual P/L
        'notes'  # Empty - for any additional notes
    ]
    
    def __init__(self, log_path: str = "data/bet_history.csv"):
        """
        Initialize the bet logger.
        
        Args:
            log_path: Path to save bet logs (CSV file)
        """
        self.log_path = Path(log_path)
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self):
        """
        Ensure the CSV file exists with proper headers.
        If the file doesn't exist, create it with headers.
        """
        if not self.log_path.exists():
            try:
                with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                    writer.writeheader()
                print(f"✅ Created new bet log file: {self.log_path}")
            except Exception as e:
                print(f"❌ Error creating bet log file: {e}")
    
    def log_bet(self, opportunity: Dict[str, Any], 
                bet_placed: bool = True,
                notes: str = "") -> bool:
        """
        Log a bet opportunity to the CSV file.
        
        Args:
            opportunity: The betting opportunity dictionary from PositiveEVScanner
            bet_placed: Whether the bet was actually placed (True) or just recorded (False)
            notes: Optional notes about the bet
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            # Extract Kelly stake info
            kelly_stake = opportunity.get('kelly_stake', {})
            
            # Prepare the bet record
            bet_record = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'date_placed': datetime.now().strftime('%Y-%m-%d'),
                'game_id': opportunity.get('game_id', ''),
                'sport': opportunity.get('sport', ''),
                'game': opportunity.get('game', ''),
                'commence_time': opportunity.get('commence_time', ''),
                'market': opportunity.get('market', ''),
                'outcome': opportunity.get('outcome', ''),
                'bookmaker': opportunity.get('bookmaker', ''),
                'bookmaker_key': opportunity.get('bookmaker_key', ''),
                'bet_odds': opportunity.get('odds', 0),
                'sharp_avg_odds': opportunity.get('sharp_avg_odds', 0),
                'true_probability_pct': opportunity.get('true_probability', 0),
                'bookmaker_probability_pct': opportunity.get('bookmaker_probability', 0),
                'ev_percentage': opportunity.get('ev_percentage', 0),
                'bankroll': kelly_stake.get('bankroll', 0),
                'kelly_percentage': kelly_stake.get('kelly_percentage', 0),
                'kelly_fraction': kelly_stake.get('kelly_fraction', 1.0),
                'recommended_stake': kelly_stake.get('recommended_stake', 0),
                'expected_profit': opportunity.get('expected_profit', 0),
                'bookmaker_url': opportunity.get('bookmaker_url', ''),
                'bet_result': 'pending' if bet_placed else 'not_placed',
                'actual_profit_loss': '',  # To be filled in later
                'notes': notes
            }
            
            # Append to CSV file
            with open(self.log_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                writer.writerow(bet_record)
            
            print(f"✅ Bet logged to {self.log_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error logging bet: {e}")
            return False
    
    def update_bet_result(self, 
                         timestamp: str,
                         result: str,
                         actual_profit_loss: Optional[float] = None,
                         notes: str = "") -> bool:
        """
        Update a bet's result after the game is complete.
        This reads the entire CSV, updates the matching row, and writes it back.
        
        Args:
            timestamp: The timestamp of the bet to update
            result: The result ('win', 'loss', 'void', 'pending')
            actual_profit_loss: The actual profit or loss amount
            notes: Additional notes to append
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Read all existing bets
            rows = []
            updated = False
            
            with open(self.log_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['timestamp'] == timestamp:
                        # Update this row
                        row['bet_result'] = result
                        if actual_profit_loss is not None:
                            row['actual_profit_loss'] = actual_profit_loss
                        if notes:
                            existing_notes = row.get('notes', '')
                            row['notes'] = f"{existing_notes} | {notes}" if existing_notes else notes
                        updated = True
                    rows.append(row)
            
            if not updated:
                print(f"⚠️  No bet found with timestamp: {timestamp}")
                return False
            
            # Write back all rows
            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"✅ Bet result updated: {result}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating bet result: {e}")
            return False
    
    def get_already_bet_game_ids(self) -> set:
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
                    'error': 'No bet history file found'
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
