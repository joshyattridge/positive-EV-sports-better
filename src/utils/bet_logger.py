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
    
    def __init__(self, log_path: str = "data/bet_history.csv", test_mode: bool = False, reset: bool = False):
        """
        Initialize the bet logger.
        
        Args:
            log_path: Path to save bet logs (CSV file)
            test_mode: If True, logs to a test file instead of the main bet history
            reset: If True, creates a fresh CSV file (for backtesting). If False, appends to existing.
        """
        if test_mode:
            # When in test mode, use a separate test bet history file
            log_path = "data/test_bet_history.csv"
        
        self.log_path = Path(log_path)
        self.test_mode = test_mode
        
        if reset:
            # For backtesting: always start with a fresh file
            self._create_fresh_csv()
        else:
            # For live betting: append to existing file
            self._ensure_csv_exists()
    
    def _create_fresh_csv(self):
        """
        Create a fresh CSV file with headers, overwriting any existing file.
        Used for backtesting to ensure clean data.
        """
        try:
            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
            print(f"✅ Created fresh bet log file: {self.log_path}")
        except Exception as e:
            print(f"❌ Error creating bet log file: {e}")
    
    def _ensure_csv_exists(self):
        """
        Ensure the CSV file exists with proper headers.
        If the file doesn't exist, create it with headers.
        If it exists, keep appending to it (for live betting).
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
                notes: str = "",
                timestamp: Optional[str] = None) -> bool:
        """
        Log a bet opportunity to the CSV file.
        
        Args:
            opportunity: The betting opportunity dictionary from PositiveEVScanner
            bet_placed: Whether the bet was actually placed (True) or just recorded (False)
            notes: Optional notes about the bet
            timestamp: Optional timestamp to use (for backtesting). If None, uses current time.
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            # Extract Kelly stake info
            kelly_stake = opportunity.get('kelly_stake', {})
            
            # Use provided timestamp or current time
            if timestamp:
                log_timestamp = timestamp
                log_date = timestamp[:10] if len(timestamp) >= 10 else datetime.now().strftime('%Y-%m-%d')
            else:
                log_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_date = datetime.now().strftime('%Y-%m-%d')
            
            # Prepare the bet record
            bet_record = {
                'timestamp': log_timestamp,
                'date_placed': log_date,
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
            actual_fieldnames = None
            
            with open(self.log_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                actual_fieldnames = reader.fieldnames  # Get actual fieldnames from CSV
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
            
            # Write back all rows using actual fieldnames from the CSV
            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=actual_fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"✅ Bet result updated: {result}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating bet result: {e}")
            return False    # Backward compatibility: delegate to BetRepository
    def get_already_bet_game_ids(self) -> set:
        """Get a set of game IDs (delegates to BetRepository for backward compatibility)."""
        from src.utils.bet_repository import BetRepository
        repo = BetRepository(str(self.log_path))
        return repo.get_already_bet_game_ids()
    
    def get_failed_bet_opportunities(self, max_failures: int = 3) -> set:
        """Get failed bet opportunities (delegates to BetRepository for backward compatibility)."""
        from src.utils.bet_repository import BetRepository
        repo = BetRepository(str(self.log_path))
        return repo.get_failed_bet_opportunities(max_failures)
    
    def get_bet_summary(self) -> Dict[str, Any]:
        """Get bet summary (delegates to BetRepository for backward compatibility)."""
        from src.utils.bet_repository import BetRepository
        repo = BetRepository(str(self.log_path))
        return repo.get_bet_summary()
    
    def print_summary(self):
        """Print bet summary (delegates to BetRepository for backward compatibility)."""
        from src.utils.bet_repository import BetRepository
        repo = BetRepository(str(self.log_path))
        repo.print_summary()
