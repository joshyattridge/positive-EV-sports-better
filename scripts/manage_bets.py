#!/usr/bin/env python3
"""
Bet Management Utility

This script provides utilities to:
- View bet history summary
- Update bet results (win/loss)
- Export bet history
- Analyze performance
"""

import sys
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.bet_logger import BetLogger
from src.utils.bet_repository import BetRepository
from src.utils.google_search_scraper import GoogleSearchScraper
from src.utils.espn_scores import ESPNScoresFetcher
from src.utils.bet_settler import BetSettler


def view_summary(paper_trade: bool = False):
    """Display summary of all bets."""
    if paper_trade:
        repository = BetRepository(log_path="data/paper_trade_history.csv")
    else:
        repository = BetRepository()
    repository.print_summary()


def list_pending_bets(paper_trade: bool = False):
    """List all pending bets that need results."""
    if paper_trade:
        logger = BetLogger(log_path="data/paper_trade_history.csv")
    else:
        logger = BetLogger()
    
    if not logger.log_path.exists():
        print("❌ No bet history file found")
        return
    
    print("\n" + "="*80)
    print("⏳ PENDING BETS (Awaiting Results)")
    print("="*80 + "\n")
    
    pending_count = 0
    
    with open(logger.log_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('bet_result') == 'pending':
                pending_count += 1
                print(f"{pending_count}. [{row['timestamp']}]")
                print(f"   Game: {row['game']}")
                print(f"   Selection: {row['outcome']}")
                print(f"   Market: {row['market']}")
                print(f"   Bookmaker: {row['bookmaker']}")
                print(f"   Odds: {row['bet_odds']}")
                print(f"   Stake: £{row['recommended_stake']}")
                print(f"   Commence: {row['commence_time']}")
                print()
    
    if pending_count == 0:
        print("✅ No pending bets - all bets have been settled!")
    else:
        print(f"Total pending bets: {pending_count}")
    
    print("="*80 + "\n")


def update_bet_result(timestamp: str, result: str, profit_loss: float = None, paper_trade: bool = False):
    """
    Update a bet's result.
    
    Args:
        timestamp: Timestamp of the bet to update
        result: 'win', 'loss', 'void', or 'pending'
        profit_loss: Actual profit or loss amount
        paper_trade: If True, update paper trade history instead
    """
    if paper_trade:
        logger = BetLogger(log_path="data/paper_trade_history.csv")
    else:
        logger = BetLogger()
    
    valid_results = ['win', 'loss', 'void', 'pending']
    if result.lower() not in valid_results:
        print(f"❌ Invalid result. Must be one of: {', '.join(valid_results)}")
        return
    
    success = logger.update_bet_result(
        timestamp=timestamp,
        result=result.lower(),
        actual_profit_loss=profit_loss,
        notes=f"Result updated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    if success:
        print(f"✅ Bet result updated successfully!")
        if result.lower() == 'win':
            print(f"   🎉 Winner! Profit: £{profit_loss:.2f}" if profit_loss else "   🎉 Winner!")
        elif result.lower() == 'loss':
            print(f"   😔 Lost. Loss: £{profit_loss:.2f}" if profit_loss else "   😔 Lost.")


def interactive_update(paper_trade: bool = False):
    """Interactive mode to update bet results."""
    if paper_trade:
        logger = BetLogger(log_path="data/paper_trade_history.csv")
    else:
        logger = BetLogger()
    
    # First, show pending bets
    list_pending_bets(paper_trade=paper_trade)
    
    if not logger.log_path.exists():
        return
    
    # Count pending bets
    pending_count = 0
    with open(logger.log_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('bet_result') == 'pending':
                pending_count += 1
    
    if pending_count == 0:
        return
    
    print("\n💡 To update a bet result, enter the timestamp from above.")
    print("   Or press Enter to cancel.\n")
    
    timestamp = input("Enter timestamp: ").strip()
    
    if not timestamp:
        print("Cancelled.")
        return
    
    result = input("Enter result (win/loss/void): ").strip().lower()
    
    if result not in ['win', 'loss', 'void']:
        print("❌ Invalid result. Must be: win, loss, or void")
        return
    
    profit_loss = None
    if result in ['win', 'loss']:
        pl_input = input(f"Enter actual profit/loss amount (or press Enter to skip): £").strip()
        if pl_input:
            try:
                profit_loss = float(pl_input)
                if result == 'loss' and profit_loss > 0:
                    profit_loss = -profit_loss  # Make losses negative
            except ValueError:
                print("⚠️  Invalid amount, proceeding without P/L value")
    
    update_bet_result(timestamp, result, profit_loss, paper_trade=paper_trade)


def auto_settle_bets(dry_run: bool = False, paper_trade: bool = False):
    """
    Automatically fetch scores and settle pending bets using ESPN API + SerpAPI.
    
    Args:
        dry_run: If True, show what would be updated without making changes
        paper_trade: If True, settle paper trade history instead
    """
    if paper_trade:
        logger = BetLogger(log_path="data/paper_trade_history.csv")
    else:
        logger = BetLogger()
    
    if not logger.log_path.exists():
        print("❌ No bet history file found")
        return
    
    print("\n" + "="*80)
    print("🔄 AUTO-SETTLING PENDING BETS")
    print("="*80 + "\n")
    
    if dry_run:
        print("🧪 DRY RUN MODE - No changes will be made\n")
    
    # Initialize ESPN + SerpAPI score fetcher
    try:
        google_scraper = GoogleSearchScraper()
        espn_fetcher = ESPNScoresFetcher(serpapi_fallback=google_scraper)
        print("✅ Using ESPN API with SerpAPI fallback for settlement\n")
    except ValueError as e:
        print(f"❌ {e}")
        print("   Make sure SERPAPI_KEY is set in your .env file")
        return
    
    # Read all bets
    with open(logger.log_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        bets = list(reader)
    
    # Filter pending bets
    pending_bets = [bet for bet in bets if bet.get('bet_result') == 'pending']
    
    if not pending_bets:
        print("✅ No pending bets to settle!")
        return
    
    print(f"Found {len(pending_bets)} pending bet(s)\n")
    
    settled_count = 0
    still_pending_count = 0
    
    # Process each bet
    for bet in pending_bets:
        game_str = bet.get('game', '')
        sport = bet.get('sport', '')
        timestamp = bet.get('timestamp')
        commence_time = bet.get('commence_time', '')
        
        # Parse teams from game string (e.g., "Away Team @ Home Team")
        if ' @ ' not in game_str:
            print(f"  ⚠️  Cannot parse teams from: {game_str}")
            still_pending_count += 1
            continue
        
        away_team, home_team = game_str.split(' @ ')
        away_team = away_team.strip()
        home_team = home_team.strip()
        
        # Parse game date
        try:
            from datetime import datetime as dt
            # Handle multiple date formats
            if 'UTC' in commence_time:
                # Format: "2025-12-17 20:00 UTC"
                game_date = dt.strptime(commence_time, '%Y-%m-%d %H:%M UTC')
            else:
                # ISO format: "2025-12-17T20:00:00Z"
                game_date = dt.fromisoformat(commence_time.replace('Z', '+00:00'))
        except Exception as e:
            print(f"  ⚠️  Cannot parse date '{commence_time}' for: {game_str}")
            still_pending_count += 1
            continue
        
        # Fetch game result using ESPN + SerpAPI
        result_data = espn_fetcher.get_game_result(
            sport=sport,
            team1=away_team,
            team2=home_team,
            game_date=game_date
        )
        
        if not result_data:
            print(f"  ⏳ {game_str}: No result found yet")
            still_pending_count += 1
            continue
        # Determine bet result based on market type
        home_score = result_data['home_score']
        away_score = result_data['away_score']
        market = bet['market']
        outcome = bet['outcome']
        bet_odds = float(bet['bet_odds'])
        stake = float(bet['recommended_stake'])
        
        # Use unified BetSettler to determine result
        try:
            result, actual_pl = BetSettler.determine_bet_result(
                market=market,
                outcome=outcome,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                bet_odds=bet_odds,
                stake=stake
            )
        except ValueError as e:
            print(f"  ⚠️  {e}")
            still_pending_count += 1
            continuending_count += 1
            continue
        
        # Display result
        if result == 'win':
            emoji = "🎉"
            result_text = f"WON (+£{actual_pl:.2f})"
        elif result == 'loss':
            emoji = "😔"
            result_text = f"LOST (£{actual_pl:.2f})"
        else:  # void
            emoji = "↩️"
            result_text = "VOID (£0.00)"
        
        source = result_data.get('source', 'unknown').upper()
        print(f"  {emoji} {game_str}")
        print(f"     Scores: {away_team} {away_score} @ {home_team} {home_score} (via {source})")
        print(f"     Bet: {outcome} @ {bet_odds}")
        print(f"     Result: {result_text}")
        
        # Update bet if not dry run
        if not dry_run:
            success = logger.update_bet_result(
                timestamp=timestamp,
                result=result,
                actual_profit_loss=actual_pl,
                notes=f"Auto-settled via {source} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            if success:
                settled_count += 1
                print(f"     ✅ Updated in database")
            else:
                print(f"     ❌ Failed to update")
        else:
            settled_count += 1
        
        print()
    
    # Summary
    print("="*80)
    if dry_run:
        print(f"🧪 DRY RUN COMPLETE")
        print(f"   Would settle: {settled_count} bet(s)")
        print(f"   Still pending: {still_pending_count} bet(s)")
    else:
        print(f"✅ AUTO-SETTLE COMPLETE")
        print(f"   Settled: {settled_count} bet(s)")
        print(f"   Still pending: {still_pending_count} bet(s)")
    print("="*80 + "\n")
def export_to_analysis(paper_trade: bool = False):
    """Export bet history to a format suitable for analysis."""
    if paper_trade:
        logger = BetLogger(log_path="data/paper_trade_history.csv")
    else:
        logger = BetLogger()
    
    if not logger.log_path.exists():
        print("❌ No bet history file found")
        return
    
    output_path = Path("bet_analysis_export.csv")
    
    # Read and calculate additional metrics
    with open(logger.log_path, 'r', newline='', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        rows = list(reader)
    
    # Add calculated fields
    for row in rows:
        try:
            # Calculate ROI
            stake = float(row.get('recommended_stake', 0))
            apl = row.get('actual_profit_loss', '')
            if apl and stake > 0:
                roi = (float(apl) / stake) * 100
                row['roi_percent'] = f"{roi:.2f}"
            else:
                row['roi_percent'] = ''
            
            # Mark settled vs pending
            row['settled'] = 'Yes' if row.get('bet_result') in ['win', 'loss', 'void'] else 'No'
            
        except (ValueError, TypeError):
            row['roi_percent'] = ''
            row['settled'] = 'No'
    
    # Write with additional columns
    if rows:
        fieldnames = list(rows[0].keys())
        with open(output_path, 'w', newline='', encoding='utf-8') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"✅ Exported {len(rows)} bets to {output_path}")
        print("   This file includes ROI calculations and is ready for analysis in Excel/Google Sheets")


def print_usage():
    """Print usage information."""
    print("\n📊 Bet Management Utility")
    print("\nUsage:")
    print("  python manage_bets.py summary           - Show bet history summary")
    print("  python manage_bets.py pending           - List pending bets")
    print("  python manage_bets.py update            - Interactive mode to update results")
    print("  python manage_bets.py settle [--dry-run] - Auto-settle bets using ESPN + SerpAPI")
    print("  python manage_bets.py export            - Export to analysis-ready CSV")
    print("\nExamples:")
    print("  python manage_bets.py summary")
    print("  python manage_bets.py settle            # Automatically settle completed bets")
    print("  python manage_bets.py settle --dry-run  # Preview what would be settled")
    print("  python manage_bets.py update")
    print()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    # Check for paper trade mode
    paper_trade = '--paper-trade' in sys.argv
    
    command = sys.argv[1].lower()
    
    if command == 'summary':
        view_summary(paper_trade=paper_trade)
    
    elif command == 'pending':
        list_pending_bets(paper_trade=paper_trade)
    
    elif command == 'update':
        interactive_update(paper_trade=paper_trade)
    
    elif command == 'settle':
        # Check for dry-run flag
        dry_run = '--dry-run' in sys.argv
        auto_settle_bets(dry_run=dry_run, paper_trade=paper_trade)
    
    elif command == 'export':
        export_to_analysis(paper_trade=paper_trade)
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
