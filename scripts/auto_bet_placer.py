"""
Automated Bet Placement System

This script integrates the positive EV scanner, Kelly Criterion calculator,
and browser automation to automatically place the best betting opportunity.
"""

import asyncio
import os
from typing import Optional, Dict, List, Any
from datetime import datetime
from dotenv import load_dotenv
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.positive_ev_scanner import PositiveEVScanner
from src.automation.browser_automation import BrowserAutomation
from src.core.kelly_criterion import KellyCriterion
from src.utils.bet_logger import BetLogger
from anthropic import Anthropic

# Load environment variables
load_dotenv()


class AutoBetPlacer:
    """
    Automated bet placement system that finds the best opportunity
    and places the bet automatically.
    """
    
    def __init__(self, headless: bool = False):
        """
        Initialize the auto bet placer.
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.scanner = PositiveEVScanner()
        self.automation = BrowserAutomation(headless=headless)
        self.kelly = KellyCriterion()
        self.bet_logger = BetLogger()
        self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    def get_bookmaker_credentials(self, bookmaker_key: str) -> Dict[str, str]:
        """
        Get username and password for a specific bookmaker from environment variables.
        
        Args:
            bookmaker_key: The bookmaker key (e.g., 'bet365', 'williamhill')
            
        Returns:
            Dictionary with 'username' and 'password' keys
        """
        # Convert bookmaker key to uppercase for env var lookup
        env_prefix = bookmaker_key.upper()
        
        username = os.getenv(f'{env_prefix}_USERNAME')
        password = os.getenv(f'{env_prefix}_PASSWORD')
        
        if not username or not password:
            raise ValueError(
                f"Credentials not found for {bookmaker_key}. "
                f"Please set {env_prefix}_USERNAME and {env_prefix}_PASSWORD in .env file"
            )
        
        return {
            'username': username,
            'password': password
        }
    
    def find_best_opportunity(self) -> Optional[Dict[str, Any]]:
        """
        Scan all sports and return the single best betting opportunity.
        
        Returns:
            Best opportunity dictionary or None if no opportunities found
        """
        print("\n" + "="*80)
        print("🔍 SCANNING FOR BEST BETTING OPPORTUNITY")
        print("="*80 + "\n")
        
        # Scan all sports
        all_opportunities = self.scanner.scan_all_sports()
        
        if not all_opportunities:
            print("❌ No +EV opportunities found")
            return None
        
        # Flatten all opportunities into a single list
        all_opps_list = []
        for sport, opps in all_opportunities.items():
            all_opps_list.extend(opps)
        
        if not all_opps_list:
            print("❌ No +EV opportunities found")
            return None
        
        # Sort opportunities using the scanner's configured method
        sorted_opps = self.scanner.sort_opportunities(all_opps_list)
        
        # Apply one-bet-per-game filter if enabled
        filtered_opps = self.scanner.filter_one_bet_per_game(sorted_opps)
        
        # Get the best one (first after sorting and filtering)
        best_opp = filtered_opps[0]
        
        print(f"\n✅ BEST OPPORTUNITY FOUND:")
        print(f"   Sport: {best_opp['sport']}")
        print(f"   Game: {best_opp['game']}")
        print(f"   Market: {best_opp['market']}")
        print(f"   Outcome: {best_opp['outcome']}")
        print(f"   Bookmaker: {best_opp['bookmaker']}")
        print(f"   Odds: {best_opp['odds']:.2f}")
        print(f"   EV: +{best_opp['ev_percentage']:.2f}%")
        print(f"   Recommended Stake: £{best_opp['kelly_stake']['recommended_stake']:.2f}")
        print(f"   Expected Profit: £{best_opp['expected_profit']:.2f}")
        print(f"   URL: {best_opp['bookmaker_url']}")
        
        return best_opp
    
    def generate_bet_prompt(self, opportunity: Dict[str, Any], credentials: Dict[str, str]) -> str:
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
        bet_description = self._describe_bet(market, outcome, away_team, home_team)
        
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
    
    def _describe_bet(self, market: str, outcome: str, away_team: str, home_team: str) -> str:
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
    
    async def _verify_bet_placement(self, conversation_history: List[Dict], final_response: str) -> bool:
        """
        Ask the LLM to analyze the conversation history and determine if the bet was actually placed.
        
        Args:
            conversation_history: The full conversation history from the automation
            final_response: The final response from the automation
            
        Returns:
            True if bet was placed, False otherwise
        """
        verification_prompt = f"""Based on the conversation history and final response below, determine if a bet was ACTUALLY PLACED and CONFIRMED on the betting website.

A bet is considered "placed" ONLY if:
1. The bet slip was filled out correctly
2. The "Place Bet" or "Confirm" button was clicked
3. A confirmation message or bet reference was received from the bookmaker

A bet is NOT placed if:
- Odds didn't meet requirements
- The process was stopped or aborted
- There was an error or issue
- The automation couldn't complete the placement
- Only navigation or viewing occurred without final confirmation

Final Response: {final_response}

Answer with ONLY one word: "YES" if the bet was successfully placed and confirmed, or "NO" if it was not placed.
"""
        
        try:
            # Create a verification request
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[
                    {"role": "user", "content": verification_prompt}
                ]
            )
            
            answer = response.content[0].text.strip().upper()
            return answer == "YES"
            
        except Exception as e:
            print(f"⚠️ Error verifying bet placement: {e}")
            # Conservative default: assume bet was NOT placed if verification fails
            return False
    
    async def place_best_bet(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Find the best opportunity and automatically place the bet.
        
        Args:
            dry_run: If True, only scan and generate prompt without placing bet
            
        Returns:
            Dictionary with results
        """
        # Find best opportunity
        best_opp = self.find_best_opportunity()
        
        if not best_opp:
            return {
                'success': False,
                'message': 'No betting opportunities found'
            }
        
        # Get bookmaker credentials
        try:
            credentials = self.get_bookmaker_credentials(best_opp['bookmaker_key'])
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'opportunity': best_opp
            }
        
        # Generate betting prompt
        prompt = self.generate_bet_prompt(best_opp, credentials)
        
        print("\n" + "="*80)
        print("📝 GENERATED BET PLACEMENT PROMPT")
        print("="*80)
        print(prompt)
        
        if dry_run:
            print("\n🔍 DRY RUN MODE - Not placing bet")
            # Log the bet as 'not_placed' in dry run mode
            self.bet_logger.log_bet(best_opp, bet_placed=False, notes="Dry run - bet not placed")
            return {
                'success': True,
                'message': 'Dry run completed',
                'opportunity': best_opp,
                'prompt': prompt
            }
        
        # Place the bet using browser automation
        print("\n" + "="*80)
        print("🤖 STARTING AUTOMATED BET PLACEMENT")
        print("="*80 + "\n")
        try:
            result = await self.automation.automate_task(prompt, max_iterations=50)
            
            # Ask the LLM to verify if the bet was actually placed by analyzing the conversation
            bet_actually_placed = await self._verify_bet_placement(
                result.get('conversation_history', []),
                result['response']
            )
            
            # Log the bet to CSV
            if result['success'] and bet_actually_placed:
                self.bet_logger.log_bet(best_opp, bet_placed=True, notes="Bet placed successfully via automation")
            else:
                failure_reason = result['response']
                self.bet_logger.log_bet(best_opp, bet_placed=False, notes=failure_reason)
            
            return {
                'success': result['success'] and bet_actually_placed,
                'message': result['response'],
                'opportunity': best_opp,
                'automation_result': result
            }
            
        except Exception as e:
            # Log the bet as failed
            self.bet_logger.log_bet(best_opp, bet_placed=False, notes=f"Automation error: {str(e)}")
            
            return {
                'success': False,
                'message': f'Automation error: {str(e)}',
                'opportunity': best_opp,
                'error': str(e)
            }
        finally:
            await self.automation.close_browser()
    
    async def close(self):
        """
        Clean up resources.
        """
        await self.automation.close_browser()


async def main():
    """
    Main function to run the automated bet placement system.
    """
    print("="*80)
    print("🤖 AUTOMATED BET PLACEMENT SYSTEM")
    print("="*80)
    print(f"\n⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get mode from user
    import sys
    dry_run = '--dry-run' in sys.argv or '-d' in sys.argv
    
    if dry_run:
        print("\n🔍 Running in DRY RUN mode (will not place actual bets)")
    else:
        print("\n⚠️  LIVE MODE - Will place actual bets!")
        print("   Press Ctrl+C within 5 seconds to cancel...")
        try:
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return
    
    placer = AutoBetPlacer(headless=False)
    
    try:
        result = await placer.place_best_bet(dry_run=dry_run)
        
        print("\n" + "="*80)
        print("📊 FINAL RESULT")
        print("="*80)
        
        if result['success']:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
        
        if 'opportunity' in result:
            opp = result['opportunity']
            print(f"\n🎯 Opportunity Details:")
            print(f"   Game: {opp['game']}")
            print(f"   Selection: {opp['outcome']}")
            print(f"   Odds: {opp['odds']:.2f}")
            print(f"   Stake: £{opp['kelly_stake']['recommended_stake']:.2f}")
            print(f"   Expected Profit: £{opp['expected_profit']:.2f}")
        
        if 'automation_result' in result:
            auto = result['automation_result']
            print(f"\n🤖 Automation Stats:")
            print(f"   Iterations: {auto.get('iterations', 'N/A')}")
            print(f"   Tool calls: {len(auto.get('conversation_history', []))}")
        
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await placer.close()
        
        # Print bet history summary
        placer.bet_logger.print_summary()
        
        print("\n" + "="*80)
        print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
