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
    
    def __init__(self, headless: bool = False, test_mode: bool = False, paper_trade: bool = False):
        """
        Initialize the auto bet placer.
        
        Args:
            headless: Whether to run browser in headless mode
            test_mode: If True, logs to test file instead of main bet history
            paper_trade: If True, logs to paper trading file without placing actual bets
        """
        self.paper_trade = paper_trade
        
        # Determine the log path based on mode
        if paper_trade:
            log_path = "data/paper_trade_history.csv"
        elif test_mode:
            log_path = "data/test_bet_history.csv"
        else:
            log_path = "data/bet_history.csv"
        
        # Initialize scanner and bet logger with the same log path
        self.scanner = PositiveEVScanner(log_path=log_path)
        self.bet_logger = BetLogger(log_path=log_path)
        self.automation = BrowserAutomation(headless=headless)
        self.kelly = KellyCriterion()
        
        self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Get available bookmakers from credentials (no validation needed, auto-detected)
        available_bookmakers = BookmakerCredentials.get_available_bookmakers()
        if not available_bookmakers and not paper_trade:
            print("⚠️  Warning: No bookmaker credentials found. Cannot place bets.")
    
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
        
        if self.paper_trade:
            print("\n📄 PAPER TRADE MODE - Logging bet without placing")
            # Log as if bet was placed (pending result) but don't actually place it
            self.bet_logger.log_bet(best_opp, bet_placed=True, notes="Paper trade - not actually placed")
            return {
                'success': True,
                'message': 'Paper trade logged successfully',
                'opportunity': best_opp,
                'paper_trade': True
            }
        
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


async def run_single_bet(dry_run: bool, paper_trade: bool, placer: AutoBetPlacer):
    """Run a single bet placement cycle."""
    result = await placer.place_best_bet(dry_run=dry_run)
    
    print("\n" + "="*80)
    print("📊 RESULT")
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
                expected_sharp = val.get('expected_sharp_odds')
                if expected_sharp:
                    print(f"      Expected: {expected_sharp:.2f}, Actual: {sharp_actual:.2f}")
                else:
                    print(f"      Actual: {sharp_actual:.2f}")
            else:
                print(f"      Actual: not found")
    
    return result


async def main():
    """
    Main function to run the automated bet placement system.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated bet placement system')
    parser.add_argument('--dry-run', '-d', action='store_true',
                       help='Dry run mode (no actual bets placed)')
    parser.add_argument('--paper-trade', '-p', action='store_true',
                       help='Paper trade mode (log without placing)')
    parser.add_argument('--interval', type=int, default=None,
                       help='Run continuously with this interval in minutes')
    parser.add_argument('--max-bets', type=int, default=None,
                       help='Maximum number of bets to place before stopping')
    
    args = parser.parse_args()
    
    print("="*80)
    print("🤖 AUTOMATED BET PLACEMENT SYSTEM")
    print("="*80)
    print(f"\n⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.paper_trade:
        print("\n📄 Running in PAPER TRADE mode (logging to paper_trade_history.csv)")
    elif args.dry_run:
        print("\n🔍 Running in DRY RUN mode (will not place actual bets)")
    else:
        print("\n⚠️  LIVE MODE - Will place actual bets!")
        print("   Press Ctrl+C within 5 seconds to cancel...")
        try:
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return
    
    if args.interval:
        print(f"\n🔄 Continuous mode: Running every {args.interval} minutes")
        if args.max_bets:
            print(f"   Will stop after {args.max_bets} bets")
    
    placer = AutoBetPlacer(headless=False, paper_trade=args.paper_trade)
    bets_placed = 0
    
    try:
        if args.interval:
            # Continuous mode
            import time
            while True:
                print("\n" + "="*80)
                print(f"🔄 Cycle {bets_placed + 1}")
                print("="*80)
                
                result = await run_single_bet(args.dry_run, args.paper_trade, placer)
                
                if result['success']:
                    bets_placed += 1
                    print(f"\n📈 Total bets placed: {bets_placed}")
                    
                    if args.max_bets and bets_placed >= args.max_bets:
                        print(f"\n✅ Reached maximum bets ({args.max_bets}). Stopping.")
                        break
                
                print(f"\n⏸️  Waiting {args.interval} minutes until next scan...")
                next_run = datetime.fromtimestamp(time.time() + args.interval * 60)
                print(f"   Next scan at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                
                await asyncio.sleep(args.interval * 60)
        else:
            # Single run mode
            result = await run_single_bet(args.dry_run, args.paper_trade, placer)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
        if args.interval:
            print(f"📊 Total bets placed: {bets_placed}")
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
