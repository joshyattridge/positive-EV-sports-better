"""
Bet Settlement Logic

Unified bet settlement logic for determining bet results across all modes
(backtesting, live betting, paper trading). Uses ESPN API + SerpAPI.
"""

from typing import Dict, Tuple, Optional


class BetSettler:
    """
    Unified bet settlement logic for all market types.
    """
    
    @staticmethod
    def determine_bet_result(
        market: str,
        outcome: str,
        home_team: str,
        away_team: str,
        home_score: float,
        away_score: float,
        bet_odds: float,
        stake: float
    ) -> Tuple[str, float]:
        """
        Determine bet result based on market type and game scores.
        
        Args:
            market: Market type ('h2h', 'h2h_3_way', 'totals', 'spreads')
            outcome: The bet outcome/selection
            home_team: Home team name
            away_team: Away team name
            home_score: Final home team score
            away_score: Final away team score
            bet_odds: Odds at which bet was placed
            stake: Amount staked on the bet
            
        Returns:
            Tuple of (result, profit_loss) where:
                - result is 'win', 'loss', or 'void'
                - profit_loss is the actual profit/loss amount
        """
        if market in ['h2h', 'h2h_3_way']:
            return BetSettler._settle_h2h(
                outcome, home_team, away_team, 
                home_score, away_score, bet_odds, stake
            )
        elif market == 'totals':
            return BetSettler._settle_totals(
                outcome, home_score, away_score, bet_odds, stake
            )
        elif market == 'spreads':
            return BetSettler._settle_spreads(
                outcome, home_team, away_team,
                home_score, away_score, bet_odds, stake
            )
        else:
            raise ValueError(f"Unsupported market type: {market}")
    
    @staticmethod
    def _settle_h2h(
        outcome: str,
        home_team: str,
        away_team: str,
        home_score: float,
        away_score: float,
        bet_odds: float,
        stake: float
    ) -> Tuple[str, float]:
        """Settle head-to-head (moneyline) bet."""
        outcome_lower = outcome.lower()
        home_lower = home_team.lower()
        away_lower = away_team.lower()
        
        # Determine which team was bet on
        bet_on_home = outcome_lower in home_lower or home_lower in outcome_lower
        bet_on_away = outcome_lower in away_lower or away_lower in outcome_lower
        
        # Handle draw
        if home_score == away_score:
            if 'draw' in outcome_lower:
                return ('win', stake * (bet_odds - 1))
            else:
                return ('void', 0.0)
        
        # Determine winner
        if bet_on_home and home_score > away_score:
            return ('win', stake * (bet_odds - 1))
        elif bet_on_away and away_score > home_score:
            return ('win', stake * (bet_odds - 1))
        else:
            return ('loss', -stake)
    
    @staticmethod
    def _settle_totals(
        outcome: str,
        home_score: float,
        away_score: float,
        bet_odds: float,
        stake: float
    ) -> Tuple[str, float]:
        """Settle totals (over/under) bet."""
        total_score = home_score + away_score
        
        # Parse Over/Under and line
        if 'Over' in outcome:
            try:
                # Extract the line, removing parentheses if present
                line_str = outcome.split()[-1].strip('()').lstrip('+')
                line = float(line_str)
                if total_score > line:
                    return ('win', stake * (bet_odds - 1))
                elif total_score == line:
                    return ('void', 0.0)
                else:
                    return ('loss', -stake)
            except (ValueError, IndexError):
                raise ValueError(f"Cannot parse totals line from outcome: {outcome}")
        
        elif 'Under' in outcome:
            try:
                # Extract the line, removing parentheses if present
                line_str = outcome.split()[-1].strip('()').lstrip('+')
                line = float(line_str)
                if total_score < line:
                    return ('win', stake * (bet_odds - 1))
                elif total_score == line:
                    return ('void', 0.0)
                else:
                    return ('loss', -stake)
            except (ValueError, IndexError):
                raise ValueError(f"Cannot parse totals line from outcome: {outcome}")
        
        else:
            raise ValueError(f"Cannot parse Over/Under from outcome: {outcome}")
    
    @staticmethod
    def _settle_spreads(
        outcome: str,
        home_team: str,
        away_team: str,
        home_score: float,
        away_score: float,
        bet_odds: float,
        stake: float
    ) -> Tuple[str, float]:
        """Settle spread bet."""
        # Parse team name and spread from outcome (e.g., "Team Name (+7.5)")
        if '(' not in outcome or ')' not in outcome:
            raise ValueError(f"Cannot parse spread from outcome: {outcome}")
        
        team_name = outcome.split('(')[0].strip()
        spread_str = outcome.split('(')[1].split(')')[0].strip()
        
        try:
            spread = float(spread_str)
        except ValueError:
            raise ValueError(f"Invalid spread value: {spread_str}")
        
        # Determine which team was bet on and apply spread
        team_lower = team_name.lower()
        home_lower = home_team.lower()
        away_lower = away_team.lower()
        
        if team_lower in home_lower or home_lower in team_lower:
            adjusted_score = home_score + spread
            opponent_score = away_score
        elif team_lower in away_lower or away_lower in team_lower:
            adjusted_score = away_score + spread
            opponent_score = home_score
        else:
            raise ValueError(f"Cannot match team '{team_name}' to home '{home_team}' or away '{away_team}'")
        
        # Determine result
        if adjusted_score > opponent_score:
            return ('win', stake * (bet_odds - 1))
        elif adjusted_score == opponent_score:
            return ('void', 0.0)
        else:
            return ('loss', -stake)
    
    @staticmethod
    def determine_bet_result_backtest(
        bet: Dict,
        home_team: str,
        away_team: str,
        home_score: float,
        away_score: float,
        espn_home: Optional[str] = None,
        espn_away: Optional[str] = None
    ) -> str:
        """
        Determine bet result for backtesting (returns 'won'/'lost' without P/L calculation).
        
        This is used in backtest.py where P/L is calculated separately.
        
        Args:
            bet: Bet dictionary with 'market', 'outcome', 'odds' keys
            home_team: Home team name from odds API
            away_team: Away team name from odds API
            home_score: Final home score
            away_score: Final away score
            espn_home: ESPN's home team name (may differ from odds API)
            espn_away: ESPN's away team name (may differ from odds API)
            
        Returns:
            'won', 'lost', or None if cannot determine
        """
        market = bet['market']
        outcome = bet['outcome']
        
        if market in ['h2h', 'h2h_3_way']:
            outcome_lower = outcome.lower()
            home_lower = home_team.lower()
            away_lower = away_team.lower()
            
            # Also check ESPN team names if provided
            espn_home_lower = espn_home.lower() if espn_home else ""
            espn_away_lower = espn_away.lower() if espn_away else ""
            
            # Determine which team was bet on
            bet_on_home = (outcome_lower in home_lower or home_lower in outcome_lower or
                          outcome_lower in espn_home_lower or espn_home_lower in outcome_lower)
            bet_on_away = (outcome_lower in away_lower or away_lower in outcome_lower or
                          outcome_lower in espn_away_lower or espn_away_lower in outcome_lower)
            
            # Check if bet won
            if bet_on_home and home_score > away_score:
                return 'won'
            elif bet_on_away and away_score > home_score:
                return 'won'
            elif 'draw' in outcome_lower and home_score == away_score:
                return 'won'
            else:
                return 'lost'
        
        elif market == 'totals':
            total_score = home_score + away_score
            
            if 'Over' in outcome:
                try:
                    line = float(outcome.split()[-1])
                    return 'won' if total_score > line else 'lost'
                except (ValueError, IndexError):
                    return None
            elif 'Under' in outcome:
                try:
                    line = float(outcome.split()[-1])
                    return 'won' if total_score < line else 'lost'
                except (ValueError, IndexError):
                    return None
        
        # Spreads not fully implemented in backtest
        return None
