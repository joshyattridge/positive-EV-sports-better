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
from src.utils.error_logger import logger
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
            logger.warning(
                "No bookmaker credentials found. Cannot place bets. "
                "Please add credentials to .env file (e.g., FANDUEL_USERNAME and FANDUEL_PASSWORD)."
            )
    
    def find_best_opportunities(self, max_count: Optional[int] = 1) -> List[Dict[str, Any]]:
        """
        Scan all sports and return the best betting opportunities.
        
        Args:
            max_count: Maximum number of opportunities to return (None = all)
        
        Returns:
            List of opportunity dictionaries (empty if none found)
        """
        # Reset filter stats before scanning
        self.scanner.reset_filter_stats()
        self.scanner.reset_filter_stats()
        
        # Scan all sports
        all_opportunities = self.scanner.scan_all_sports()
        
        if not all_opportunities:
            # Get and log filter stats
            stats = self.scanner.get_filter_stats()
            total_filtered = sum(v for k, v in stats.items() if k.startswith('filtered_'))
            
            # Log critical issues
            if stats['no_sharp_odds'] > 0:
                logger.warning(f"{stats['no_sharp_odds']} opportunities had no sharp book odds (check SHARP_BOOKS config)")
            if stats['no_betting_bookmakers'] > 0:
                logger.warning(f"{stats['no_betting_bookmakers']} opportunities not from your betting bookmakers")
            
            if total_filtered > 0:
                logger.info(f"{total_filtered} opportunities filtered: {stats['filtered_already_bet']} already bet, {stats['filtered_too_far_ahead']} too far ahead, {stats['filtered_max_odds']} odds too high, {stats['filtered_min_ev']} below min EV")
            return []
        
        # Flatten all opportunities into a single list
        all_opps_list = []
        for sport, opps in all_opportunities.items():
            all_opps_list.extend(opps)
        
        if not all_opps_list:
            return []
        
        # Sort opportunities using the scanner's configured method
        sorted_opps = self.scanner.sort_opportunities(all_opps_list)
        
        # Apply one-bet-per-game filter if enabled
        filtered_opps = self.scanner.filter_one_bet_per_game(sorted_opps)
        
        # Get top N opportunities
        if max_count:
            top_opps = filtered_opps[:max_count]
        else:
            top_opps = filtered_opps
        
        print(f"\n✅ {len(top_opps)} opportunity(ies) found\n")
        for i, opp in enumerate(top_opps, 1):
            print(f"#{i}: {opp['game']} - {opp['outcome']} @ {opp['odds']:.2f} ({opp['bookmaker']}) | EV: +{opp['ev_percentage']:.2f}% | £{opp['kelly_stake']['recommended_stake']:.2f}")
        
        return top_opps
    
    def find_best_opportunity(self) -> Optional[Dict[str, Any]]:
        """
        Scan all sports and return the single best betting opportunity.
        
        Returns:
            Best opportunity dictionary or None if no opportunities found
        """
        opps = self.find_best_opportunities(max_count=1)
        return opps[0] if opps else None
    
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
    
    async def place_specific_bet(self, opportunity: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Place a specific betting opportunity.
        
        Args:
            opportunity: The opportunity dictionary to bet on
            dry_run: If True, only scan and generate prompt without placing bet
            
        Returns:
            Dictionary with results
        """
        # Get bookmaker credentials
        try:
            credentials = BookmakerCredentials.get_credentials(opportunity['bookmaker_key'])
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'opportunity': opportunity
            }
        
        # Generate betting prompt
        prompt = BetPlacementPromptGenerator.generate_bet_prompt(opportunity, credentials)
        
        if self.paper_trade:
            print("\n📄 Paper trading (not placing actual bet)")
            # Log as if bet was placed (pending result) but don't actually place it
            self.bet_logger.log_bet(opportunity, bet_placed=True, notes="Paper trade - not actually placed")
            return {
                'success': True,
                'message': 'Paper trade logged successfully',
                'opportunity': opportunity,
                'paper_trade': True
            }
        
        if dry_run:
            print("\n🔍 Dry run mode - skipping placement")
            # Log the bet as 'not_placed' in dry run mode
            self.bet_logger.log_bet(opportunity, bet_placed=False, notes="Dry run - bet not placed")
            return {
                'success': True,
                'message': 'Dry run completed',
                'opportunity': opportunity,
                'prompt': prompt
            }
        
        # Place the bet using browser automation
        print("\n🤖 Placing bet...")
        return await self._execute_bet_placement(opportunity, prompt)
    
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
        
        return await self.place_specific_bet(best_opp, dry_run=dry_run)
    
    async def _execute_bet_placement(self, opportunity: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """
        Execute the actual bet placement through browser automation.
        
        Args:
            opportunity: The opportunity dictionary
            prompt: The generated betting prompt
            
        Returns:
            Dictionary with results
        """
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
                sharp_links = opportunity.get('sharp_links', [])
                sharp_url = None
                sharp_odds = None
                
                if sharp_links:
                    # Try to find Pinnacle first, otherwise use the first available
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
                self.bet_logger.log_bet(opportunity, bet_placed=True, notes="Bet placed successfully via automation")
                
                # Now validate odds AFTER the bet is logged
                if sharp_url:
                    print("\n🔍 Validating odds...")
                    try:
                        validation_results = await self.automation.odds_validation(
                            bet_id=opportunity['game_id'],
                            bookmaker_odds=opportunity['odds'],
                            sharp_odds=sharp_odds,
                            sharp_url=sharp_url,
                            game=opportunity['game'],
                            market=opportunity['market'],
                            outcome=opportunity['outcome']
                        )
                        # Store sharp_url and expected sharp odds for later display
                        validation_results['sharp_url'] = sharp_url
                        validation_results['expected_sharp_odds'] = sharp_odds
                    except Exception as e:
                        print(f"⚠️ Odds validation failed: {e}")
                        validation_results = {'error': str(e)}
            else:
                failure_reason = result['response']
                self.bet_logger.log_bet(opportunity, bet_placed=False, notes=failure_reason)
            
            return {
                'success': result['success'] and bet_actually_placed,
                'message': result['response'],
                'opportunity': opportunity,
                'automation_result': result,
                'validation_results': validation_results
            }
            
        except Exception as e:
            # Log the bet as failed
            self.bet_logger.log_bet(opportunity, bet_placed=False, notes=f"Automation error: {str(e)}")
            
            return {
                'success': False,
                'message': f'Automation error: {str(e)}',
                'opportunity': opportunity,
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
    
    if result['success']:
        print(f"\n✅ {result['message']}")
    else:
        print(f"\n❌ {result['message']}")
    
    if 'opportunity' in result:
        opp = result['opportunity']
        print(f"   {opp['game']} - {opp['outcome']} @ {opp['odds']:.2f} | Stake: £{opp['kelly_stake']['recommended_stake']:.2f}")
    
    if 'validation_results' in result and result['validation_results']:
        val = result['validation_results']
        if 'error' not in val:
            bm_ok = val.get('bookmaker_correct')
            sharp_ok = val.get('sharp_correct')
            status = "✅ Validated" if (bm_ok and sharp_ok) else "⚠️ Odds mismatch"
            print(f"   {status}")
    
    return result


async def run_bet_cycle(dry_run: bool, paper_trade: bool, placer: AutoBetPlacer, max_bets: Optional[int] = None) -> int:
    """
    Run a single betting cycle - scan and place up to max_bets.
    
    Args:
        dry_run: Whether to run in dry run mode
        paper_trade: Whether to run in paper trade mode
        placer: The AutoBetPlacer instance
        max_bets: Maximum number of bets to place this cycle (None = 1)
    
    Returns:
        Number of bets successfully placed
    """
    bets_placed = 0
    
    if max_bets and max_bets > 1:
        # Find multiple opportunities
        opportunities = placer.find_best_opportunities(max_count=max_bets)
        
        if not opportunities:
            print("\n❌ No betting opportunities found")
            return 0
        
        for i, opp in enumerate(opportunities, 1):
            
            # Place this specific bet
            bet_time = datetime.now()
            result = await placer.place_specific_bet(opp, dry_run=dry_run)
            
            if result['success']:
                bets_placed += 1
                print(f"✅ [{bet_time.strftime('%H:%M:%S')}] {opp['game']} - {opp['outcome']} @ {opp['odds']:.2f} | £{opp['kelly_stake']['recommended_stake']:.2f}")
            else:
                error_msg = result.get('message', 'Unknown error')[:50]
                print(f"❌ [{bet_time.strftime('%H:%M:%S')}] Failed: {error_msg}")
                logger.error(f"Bet placement failed: {result.get('message', 'Unknown error')}")
            
            # Small delay between bets
            if i < len(opportunities):
                await asyncio.sleep(2)
    else:
        # Single bet mode
        result = await run_single_bet(dry_run, paper_trade, placer)
        if result['success']:
            bets_placed = 1
    
    return bets_placed


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
    parser.add_argument('--headless', action='store_true',
                       help='Run browser in headless mode')
    parser.add_argument('--interval', type=int, default=None,
                       help='Run continuously, scanning every X minutes')
    parser.add_argument('--max-bets', type=int, default=None,
                       help='Maximum number of bets to place per scan (default: 1)')
    
    args = parser.parse_args()
    
    mode = "Paper" if args.paper_trade else ("Dry run" if args.dry_run else "LIVE")
    interval_info = f" | {args.interval}min intervals" if args.interval else ""
    max_bets_info = f" | max {args.max_bets} bets" if args.max_bets else ""
    print(f"\n🤖 [{datetime.now().strftime('%H:%M:%S')}] {mode} mode{interval_info}{max_bets_info}")
    
    if not args.paper_trade and not args.dry_run:
        print("⚠️  LIVE MODE - Press Ctrl+C within 5 seconds to cancel...")
        try:
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            print("\n❌ Cancelled")
            return
    
    placer = AutoBetPlacer(headless=args.headless, paper_trade=args.paper_trade)
    total_bets_placed = 0
    cycle_count = 0
    
    try:
        if args.interval:
            # Continuous mode - run scanning every X minutes
            import time
            while True:
                cycle_count += 1
                cycle_start_time = datetime.now()
                print(f"\n[{cycle_start_time.strftime('%H:%M:%S')}] Cycle {cycle_count} - Scanning...")
                
                # Place up to max_bets this cycle (resets each cycle)
                cycle_bets_placed = await run_bet_cycle(args.dry_run, args.paper_trade, placer, args.max_bets)
                total_bets_placed += cycle_bets_placed
                
                if cycle_bets_placed > 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {cycle_bets_placed} placed | {total_bets_placed} total | Next: {datetime.fromtimestamp(time.time() + args.interval * 60).strftime('%H:%M:%S')}")
                
                await asyncio.sleep(args.interval * 60)
        else:
            # Single run mode - place up to max_bets
            bets_placed = await run_bet_cycle(args.dry_run, args.paper_trade, placer, args.max_bets)
            total_bets_placed = bets_placed

    except KeyboardInterrupt:
        print(f"\n\n🛑 Stopped - {total_bets_placed} bet(s) placed across {cycle_count} cycle(s)" if args.interval else f"\n\n🛑 Stopped")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await placer.close()
        print(f"\n⏰ Finished at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
