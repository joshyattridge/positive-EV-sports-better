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
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.bet_logger import BetLogger


def view_summary():
    """Display summary of all bets."""
    logger = BetLogger()
    logger.print_summary()


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
    print("  python manage_bets.py export            - Export to analysis-ready CSV")
    print("\nExamples:")
    print("  python manage_bets.py summary")
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
    
    elif command == 'export':
        export_to_analysis()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
