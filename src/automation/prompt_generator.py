"""
Prompt Generator Module

Generates prompts for browser automation tasks, specifically for bet placement.
"""

from typing import Dict, Any


class BetPlacementPromptGenerator:
    """Generates prompts for automated bet placement."""
    
    @staticmethod
    def generate_bet_prompt(opportunity: Dict[str, Any], credentials: Dict[str, str]) -> str:
        """
        Generate a detailed prompt for the browser automation to place the bet.
        
        Args:
            opportunity: The betting opportunity dictionary
            credentials: Dictionary with username and password
            
        Returns:
            Detailed prompt string for browser automation
        """
        # Extract key information
        bookmaker_name = opportunity['bookmaker']
        bookmaker_url = opportunity['bookmaker_url']
        game = opportunity['game']
        market = opportunity['market']
        outcome = opportunity['outcome']
        odds = opportunity['odds']
        stake = opportunity['kelly_stake']['recommended_stake']
        username = credentials['username']
        password = credentials['password']
        
        # Parse home and away teams
        if '@' in game:
            away_team, home_team = [team.strip() for team in game.split('@')]
        else:
            away_team = game
            home_team = game
        
        # Determine what to bet on based on market and outcome
        bet_description = BetPlacementPromptGenerator._describe_bet(market, outcome, away_team, home_team)
        
        # Generate the prompt
        prompt = f"""
🎯 AUTOMATED BET PLACEMENT TASK

📊 BETTING DETAILS:
- Bookmaker: {bookmaker_name}
- Website: {bookmaker_url}
- Game: {game}
- Market: {market}
- Selection: {bet_description}
- Required Odds: {odds:.2f} (or better)
- Stake Amount: £{stake:.2f}

🔐 LOGIN CREDENTIALS:
- Username: {username}
- Password: {password}

📝 STEP-BY-STEP INSTRUCTIONS:

1. Navigate to: {bookmaker_url}

2. If not already logged in, find and click the login button
   - Look for "Login", "Sign In", "My Account" buttons
   - Enter username: {username}
   - Enter password: {password}
   - Click submit/login button

3. Search for the match: {game}
   - Use the search function if available
   - Or navigate through the sport sections to find the match
   
4. Locate the {market} market for this match

5. Find and click on the selection: {outcome}
   - Verify the odds are {odds:.2f} or better
   - If odds are worse than {odds:.2f}, DO NOT place the bet and report the issue

6. Enter stake amount: £{stake:.2f}
   - Find the stake input field in the bet slip
   - Clear any existing value
   - Type exactly: {stake:.2f}

7. Review the bet slip to confirm:
   - Selection: {outcome}
   - Odds: {odds:.2f} or better
   - Stake: £{stake:.2f}
   - All details match the requirements

8. Place the bet
   - Click "Place Bet" or "Confirm Bet" button
   - Wait for confirmation

9. Verify bet placement
   - Look for confirmation message
   - Take note of bet reference number if available
   - Report success or any errors

⚠️ IMPORTANT NOTES:
- Only proceed if odds are {odds:.2f} or BETTER (higher decimal odds)
- If odds have changed to worse than {odds:.2f}, STOP and report
- Double-check all details before placing the bet
- If you encounter any popups or cookie consent, handle them appropriately
- If the website layout is different than expected, adapt and find the relevant elements
- Report any errors or issues clearly

ACTION_SUCCESS: place_bet_for_{opportunity['bookmaker_key']}
"""
        
        return prompt
    
    @staticmethod
    def _describe_bet(market: str, outcome: str, away_team: str, home_team: str) -> str:
        """
        Create a human-readable description of what to bet on.
        
        Args:
            market: Market type (h2h, spreads, totals)
            outcome: The outcome name
            away_team: Away team name
            home_team: Home team name
            
        Returns:
            Human-readable bet description
        """
        if market == 'h2h':
            # Moneyline/Match Winner
            if outcome == away_team:
                return f"{away_team} to win"
            elif outcome == home_team:
                return f"{home_team} to win"
            else:
                return f"Draw"
        
        elif market == 'spreads':
            # Point spread/handicap
            if '(' in outcome and ')' in outcome:
                team = outcome.split('(')[0].strip()
                spread = outcome.split('(')[1].split(')')[0].strip()
                return f"{team} {spread}"
            return outcome
        
        elif market == 'totals':
            # Over/Under
            if '(' in outcome and ')' in outcome:
                over_under = outcome.split('(')[0].strip()
                total = outcome.split('(')[1].split(')')[0].strip()
                return f"{over_under} {total} points"
            return outcome
        
        return outcome
