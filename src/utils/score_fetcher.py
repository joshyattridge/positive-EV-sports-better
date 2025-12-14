"""
Score Fetcher

Fetches game scores from The Odds API to automatically settle bets.
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


class ScoreFetcher:
    """
    Fetches scores from The Odds API for completed games.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the score fetcher.
        
        Args:
            api_key: Your The Odds API key (optional, will read from .env if not provided)
        """
        self.api_key = api_key or os.getenv('ODDS_API_KEY')
        if not self.api_key:
            raise ValueError("ODDS_API_KEY must be provided or set in .env file")
        
        self.base_url = "https://api.the-odds-api.com/v4"
    
    def get_scores(self, sport: str, days_from: int = 3) -> List[Dict]:
        """
        Get scores for a specific sport.
        
        Args:
            sport: Sport key (e.g., 'americanfootball_nfl', 'soccer_epl')
            days_from: Number of days in the past to fetch (1-3)
            
        Returns:
            List of games with scores
        """
        url = f"{self.base_url}/sports/{sport}/scores"
        params = {
            'apiKey': self.api_key,
            'daysFrom': days_from,
            'dateFormat': 'iso'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # Print remaining requests
            remaining = response.headers.get('x-requests-remaining')
            used = response.headers.get('x-requests-used')
            if remaining:
                print(f"  API Requests - Used: {used}, Remaining: {remaining}")
            
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Error fetching scores for {sport}: {e}")
            return []
    
    def get_score_by_game_id(self, sport: str, game_id: str, days_from: int = 3) -> Optional[Dict]:
        """
        Get score for a specific game by its ID.
        
        Args:
            sport: Sport key
            game_id: Game ID from the odds API
            days_from: Number of days in the past to search
            
        Returns:
            Game data with scores, or None if not found
        """
        scores = self.get_scores(sport, days_from)
        
        for game in scores:
            if game.get('id') == game_id:
                return game
        
        return None
    
    def determine_bet_result(
        self, 
        game_data: Dict, 
        market: str, 
        outcome: str, 
        bet_odds: float
    ) -> tuple[str, Optional[float]]:
        """
        Determine if a bet won, lost, or was voided based on game scores.
        
        Args:
            game_data: Game data from scores API
            market: Market type (h2h, spreads, totals)
            outcome: The bet outcome/selection
            bet_odds: The odds at which the bet was placed
            
        Returns:
            Tuple of (result, profit_loss) where result is 'win', 'loss', or 'void'
        """
        if not game_data.get('completed'):
            return ('pending', None)
        
        scores = game_data.get('scores', [])
        if not scores or len(scores) < 2:
            return ('void', 0.0)
        
        home_team = game_data.get('home_team')
        away_team = game_data.get('away_team')
        
        # Find scores
        home_score = None
        away_score = None
        
        for score_entry in scores:
            if score_entry['name'] == home_team:
                home_score = int(score_entry['score'])
            elif score_entry['name'] == away_team:
                away_score = int(score_entry['score'])
        
        if home_score is None or away_score is None:
            return ('void', 0.0)
        
        # Determine result based on market type
        if market == 'h2h':
            return self._determine_h2h_result(outcome, home_team, away_team, home_score, away_score, bet_odds)
        elif market == 'spreads':
            return self._determine_spread_result(outcome, home_team, away_team, home_score, away_score, bet_odds)
        elif market == 'totals':
            return self._determine_totals_result(outcome, home_score, away_score, bet_odds)
        else:
            print(f"  ⚠️  Unknown market type: {market}")
            return ('void', 0.0)
    
    def _determine_h2h_result(
        self, 
        outcome: str, 
        home_team: str, 
        away_team: str, 
        home_score: int, 
        away_score: int,
        bet_odds: float
    ) -> tuple[str, float]:
        """Determine h2h (moneyline) bet result."""
        if home_score == away_score:
            # Draw - for h2h this is usually a void unless draw was the bet
            if outcome.lower() == 'draw':
                # Won by betting on draw
                return ('win', bet_odds - 1.0)
            else:
                # Void if match ended in draw and bet wasn't on draw
                return ('void', 0.0)
        
        winner = home_team if home_score > away_score else away_team
        
        if outcome == winner:
            # Won
            profit = bet_odds - 1.0  # profit = (odds * stake) - stake, normalized to stake=1
            return ('win', profit)
        else:
            # Lost
            return ('loss', -1.0)
    
    def _determine_spread_result(
        self, 
        outcome: str, 
        home_team: str, 
        away_team: str, 
        home_score: int, 
        away_score: int,
        bet_odds: float
    ) -> tuple[str, float]:
        """Determine spread bet result."""
        # Parse spread from outcome (e.g., "Team Name (+7.5)" or "Team Name (-3.5)")
        if '(' not in outcome or ')' not in outcome:
            print(f"  ⚠️  Cannot parse spread from outcome: {outcome}")
            return ('void', 0.0)
        
        team_name = outcome.split('(')[0].strip()
        spread_str = outcome.split('(')[1].split(')')[0].strip()
        
        try:
            spread = float(spread_str)
        except ValueError:
            print(f"  ⚠️  Invalid spread value: {spread_str}")
            return ('void', 0.0)
        
        # Determine if bet team is home or away
        if team_name == home_team:
            adjusted_score = home_score + spread
            opponent_score = away_score
        elif team_name == away_team:
            adjusted_score = away_score + spread
            opponent_score = home_score
        else:
            print(f"  ⚠️  Team name mismatch: {team_name}")
            return ('void', 0.0)
        
        if adjusted_score > opponent_score:
            # Won
            profit = bet_odds - 1.0
            return ('win', profit)
        elif adjusted_score == opponent_score:
            # Push
            return ('void', 0.0)
        else:
            # Lost
            return ('loss', -1.0)
    
    def _determine_totals_result(
        self, 
        outcome: str, 
        home_score: int, 
        away_score: int,
        bet_odds: float
    ) -> tuple[str, float]:
        """Determine totals (over/under) bet result."""
        total_score = home_score + away_score
        
        # Parse the over/under and line (e.g., "Over (+2.5)" or "Under (2.5)")
        if '(' not in outcome or ')' not in outcome:
            print(f"  ⚠️  Cannot parse totals from outcome: {outcome}")
            return ('void', 0.0)
        
        over_under = outcome.split('(')[0].strip().lower()
        line_str = outcome.split('(')[1].split(')')[0].strip()
        
        # Remove + if present
        line_str = line_str.replace('+', '')
        
        try:
            line = float(line_str)
        except ValueError:
            print(f"  ⚠️  Invalid totals line: {line_str}")
            return ('void', 0.0)
        
        if over_under == 'over':
            if total_score > line:
                # Won
                profit = bet_odds - 1.0
                return ('win', profit)
            elif total_score == line:
                # Push
                return ('void', 0.0)
            else:
                # Lost
                return ('loss', -1.0)
        elif over_under == 'under':
            if total_score < line:
                # Won
                profit = bet_odds - 1.0
                return ('win', profit)
            elif total_score == line:
                # Push
                return ('void', 0.0)
            else:
                # Lost
                return ('loss', -1.0)
        else:
            print(f"  ⚠️  Unknown over/under: {over_under}")
            return ('void', 0.0)
