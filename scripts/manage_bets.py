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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.bet_logger import BetLogger
from src.utils.bet_repository import BetRepository
from src.utils.score_fetcher import ScoreFetcher


def view_summary():
    """Display summary of all bets."""
    repository = BetRepository()
    repository.print_summary()


def list_pending_bets():
    """List all pending bets that need results."""
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


def update_bet_result(timestamp: str, result: str, profit_loss: float = None):
    """
    Update a bet's result.
    
    Args:
        timestamp: Timestamp of the bet to update
        result: 'win', 'loss', 'void', or 'pending'
        profit_loss: Actual profit or loss amount
    """
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


def interactive_update():
    """Interactive mode to update bet results."""
    logger = BetLogger()
    
    # First, show pending bets
    list_pending_bets()
    
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
    
    update_bet_result(timestamp, result, profit_loss)


def auto_settle_bets(days_from: int = 3, dry_run: bool = False):
    """
    Automatically fetch scores and settle pending bets.
    
    Args:
        days_from: Number of days in the past to fetch scores (1-3)
        dry_run: If True, show what would be updated without making changes
    """
    logger = BetLogger()
    
    if not logger.log_path.exists():
        print("❌ No bet history file found")
        return
    
    print("\n" + "="*80)
    print("🔄 AUTO-SETTLING PENDING BETS")
    print("="*80 + "\n")
    
    if dry_run:
        print("🧪 DRY RUN MODE - No changes will be made\n")
    
    # Initialize score fetcher
    try:
        fetcher = ScoreFetcher()
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    # Read all bets
    with open(logger.log_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        bets = list(reader)
    
    # Group pending bets by sport
    pending_by_sport = {}
    for bet in bets:
        if bet.get('bet_result') == 'pending':
            sport = bet.get('sport')
            if sport not in pending_by_sport:
                pending_by_sport[sport] = []
            pending_by_sport[sport].append(bet)
    
    if not pending_by_sport:
        print("✅ No pending bets to settle!")
        return
    
    total_pending = sum(len(bets) for bets in pending_by_sport.values())
    print(f"Found {total_pending} pending bet(s) across {len(pending_by_sport)} sport(s)\n")
    
    settled_count = 0
    still_pending_count = 0
    
    # Process each sport
    for sport, sport_bets in pending_by_sport.items():
        print(f"📊 Fetching scores for {sport}...")
        scores = fetcher.get_scores(sport, days_from)
        
        if not scores:
            print(f"  ⚠️  No scores available for {sport}")
            still_pending_count += len(sport_bets)
            continue
        
        # Create a lookup dict by game_id
        scores_by_id = {game['id']: game for game in scores}
        
        print(f"  Found {len(scores)} game(s) with results\n")
        
        # Check each bet
        for bet in sport_bets:
            game_id = bet.get('game_id')
            timestamp = bet.get('timestamp')
            
            if game_id not in scores_by_id:
                print(f"  ⏳ {bet['game']}: Game not completed yet")
                still_pending_count += 1
                continue
            
            game_data = scores_by_id[game_id]
            
            # Determine result
            result, profit_loss_ratio = fetcher.determine_bet_result(
                game_data=game_data,
                market=bet['market'],
                outcome=bet['outcome'],
                bet_odds=float(bet['bet_odds'])
            )
            
            if result == 'pending':
                print(f"  ⏳ {bet['game']}: Game in progress")
                still_pending_count += 1
                continue
            
            # Calculate actual profit/loss based on stake
            stake = float(bet['recommended_stake'])
            if profit_loss_ratio is not None:
                actual_pl = stake * profit_loss_ratio
            else:
                actual_pl = 0.0
            
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
            
            scores_text = " vs ".join([f"{s['name']} {s['score']}" for s in game_data.get('scores', [])])
            print(f"  {emoji} {bet['game']}")
            print(f"     Scores: {scores_text}")
            print(f"     Bet: {bet['outcome']} @ {bet['bet_odds']}")
            print(f"     Result: {result_text}")
            
            # Update bet if not dry run
            if not dry_run:
                success = logger.update_bet_result(
                    timestamp=timestamp,
                    result=result,
                    actual_profit_loss=actual_pl,
                    notes=f"Auto-settled on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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


def export_to_analysis():
    """Export bet history to a format suitable for analysis."""
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
    print("  python manage_bets.py settle [--dry-run] - Auto-settle bets using API scores")
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
    
    command = sys.argv[1].lower()
    
    if command == 'summary':
        view_summary()
    
    elif command == 'pending':
        list_pending_bets()
    
    elif command == 'update':
        interactive_update()
    
    elif command == 'settle':
        # Check for dry-run flag
        dry_run = '--dry-run' in sys.argv
        auto_settle_bets(days_from=3, dry_run=dry_run)
    
    elif command == 'export':
        export_to_analysis()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
