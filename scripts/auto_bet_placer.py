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
from src.automation.prompt_generator import BetPlacementPromptGenerator
from src.core.kelly_criterion import KellyCriterion
from src.utils.bet_logger import BetLogger
from src.utils.config import BookmakerCredentials
from anthropic import Anthropic

# Load environment variables
load_dotenv()


class AutoBetPlacer:
    """
    Automated bet placement system that finds the best opportunity
    and places the bet automatically.
    """
    
    def __init__(self, headless: bool = False, test_mode: bool = False):
        """
        Initialize the auto bet placer.
        
        Args:
            headless: Whether to run browser in headless mode
            test_mode: If True, logs to test file instead of main bet history
        """
        self.scanner = PositiveEVScanner()
        self.automation = BrowserAutomation(headless=headless)
        self.kelly = KellyCriterion()
        self.bet_logger = BetLogger(test_mode=test_mode)
        self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Validate that all bookmakers in BETTING_BOOKMAKERS have credentials
        betting_bookmakers_str = os.getenv('BETTING_BOOKMAKERS', '')
        if betting_bookmakers_str:
            betting_bookmakers = [book.strip() for book in betting_bookmakers_str.split(',')]
            BookmakerCredentials.validate_bookmaker_credentials(betting_bookmakers)
    
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
            credentials = BookmakerCredentials.get_credentials(best_opp['bookmaker_key'])
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'opportunity': best_opp
            }
        
        # Generate betting prompt
        prompt = BetPlacementPromptGenerator.generate_bet_prompt(best_opp, credentials)
        
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
            
            # If bet was placed successfully, validate the odds
            validation_results = None
            if result['success'] and bet_actually_placed:
                # Get the first sharp book link (preferably Pinnacle)
                sharp_links = best_opp.get('sharp_links', [])
                if sharp_links:
                    # Try to find Pinnacle first, otherwise use the first available
                    sharp_url = None
                    sharp_odds = None
                    for sharp in sharp_links:
                        if 'pinnacle' in sharp['name'].lower():
                            sharp_url = sharp['link']
                            sharp_odds = sharp['odds']
                            break
                    
                    # If no Pinnacle, use first sharp book
                    if not sharp_url and sharp_links:
                        sharp_url = sharp_links[0]['link']
                        sharp_odds = sharp_links[0]['odds']
                    
            # Log the bet to CSV FIRST
            if result['success'] and bet_actually_placed:
                self.bet_logger.log_bet(best_opp, bet_placed=True, notes="Bet placed successfully via automation")
                
                # Now validate odds AFTER the bet is logged
                if sharp_url:
                    print("\n" + "="*80)
                    print("🔍 VALIDATING ODDS")
                    print("="*80 + "\n")
                    try:
                        validation_results = await self.automation.odds_validation(
                            bet_id=best_opp['game_id'],
                            bookmaker_odds=best_opp['odds'],
                            sharp_odds=sharp_odds,
                            sharp_url=sharp_url,
                            game=best_opp['game'],
                            market=best_opp['market'],
                            outcome=best_opp['outcome']
                        )
                        # Store sharp_url and expected sharp odds for later display
                        validation_results['sharp_url'] = sharp_url
                        validation_results['expected_sharp_odds'] = sharp_odds
                    except Exception as e:
                        print(f"⚠️ Odds validation failed: {e}")
                        validation_results = {'error': str(e)}
            else:
                failure_reason = result['response']
                self.bet_logger.log_bet(best_opp, bet_placed=False, notes=failure_reason)
            
            return {
                'success': result['success'] and bet_actually_placed,
                'message': result['response'],
                'opportunity': best_opp,
                'automation_result': result,
                'validation_results': validation_results
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
        
        if 'validation_results' in result and result['validation_results']:
            val = result['validation_results']
            print(f"\n🔍 Odds Validation:")
            if 'error' in val:
                print(f"   ⚠️ Validation Error: {val['error']}")
            else:
                bookmaker_status = "✅" if val.get('bookmaker_correct') else "❌"
                sharp_status = "✅" if val.get('sharp_correct') else "❌"
                bookmaker_actual = val.get('bookmaker_actual_odds')
                sharp_actual = val.get('sharp_actual_odds')
                
                print(f"   Bookmaker Odds: {bookmaker_status}")
                if bookmaker_actual:
                    print(f"      Expected: {opp['odds']:.2f}, Actual: {bookmaker_actual:.2f}")
                else:
                    print(f"      Expected: {opp['odds']:.2f}, Actual: not found")
                    
                print(f"   Sharp Book Odds: {sharp_status}")
                if sharp_actual:
                    # Get expected sharp odds from validation results
                    expected_sharp = val.get('expected_sharp_odds')
                    if expected_sharp:
                        print(f"      Expected: {expected_sharp:.2f}, Actual: {sharp_actual:.2f}")
                    else:
                        print(f"      Actual: {sharp_actual:.2f}")
                else:
                    print(f"      Actual: not found")
        
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
