"""
Utility script to view and analyze action logs from browser automation runs.
"""

import json
from pathlib import Path
from typing import Optional


def load_action_logs(log_path: str = "action_logs.json") -> dict:
    """Load action logs from file."""
    path = Path(log_path)
    if not path.exists():
        print(f"❌ No action logs found at {log_path}")
        return {}
    
    with open(path, 'r') as f:
        return json.load(f)


def list_websites(logs: dict):
    """List all websites that have been automated."""
    print("\n📊 WEBSITES IN LOGS:")
    print("=" * 80)
    for website in logs.keys():
        run_count = len(logs[website])
        print(f"  • {website} ({run_count} runs)")


def list_runs(logs: dict, website: str):
    """List all runs for a specific website."""
    if website not in logs:
        print(f"❌ No logs found for {website}")
        return
    
    print(f"\n🕐 RUNS FOR {website}:")
    print("=" * 80)
    for run_timestamp in logs[website].keys():
        run_data = logs[website][run_timestamp]
        tool_count = len(run_data.get("_all_tool_calls", []))
        print(f"  • {run_timestamp}")
        print(f"    - {tool_count} tool calls")


def view_all_tool_calls(logs: dict, website: str, run_timestamp: str):
    """View all tool calls for a specific run."""
    if website not in logs or run_timestamp not in logs[website]:
        print(f"❌ No logs found for {website} / {run_timestamp}")
        return
    
    tool_calls = logs[website][run_timestamp].get("_all_tool_calls", [])
    
    if not tool_calls:
        print(f"❌ No tool calls recorded for this run")
        return
    
    print(f"\n🔧 ALL TOOL CALLS FOR {website} / {run_timestamp}:")
    print("=" * 80)
    print(f"Total: {len(tool_calls)} tool calls\n")
    
    for i, call in enumerate(tool_calls, 1):
        tool = call.get("tool", "?")
        args = call.get("args", {})
        
        print(f"{i}. Tool: {tool}")
        print(f"   Args: {json.dumps(args, indent=10)[0:200]}...")
        print()


def view_latest_run(logs: dict, website: Optional[str] = None):
    """View the latest run for a website or across all websites."""
    if not logs:
        print("❌ No logs available")
        return
    
    if website:
        if website not in logs:
            print(f"❌ No logs found for {website}")
            return
        latest_run = max(logs[website].keys())
        print(f"\n🕐 LATEST RUN FOR {website}: {latest_run}")
        view_all_tool_calls(logs, website, latest_run)
    else:
        # Find the most recent run across all websites
        latest_website = None
        latest_run = None
        
        for site, runs in logs.items():
            for run in runs.keys():
                if latest_run is None or run > latest_run:
                    latest_run = run
                    latest_website = site
        
        if latest_website and latest_run:
            print(f"\n🕐 LATEST RUN ACROSS ALL WEBSITES")
            print(f"Website: {latest_website}")
            print(f"Run: {latest_run}")
            view_all_tool_calls(logs, latest_website, latest_run)


def interactive_menu():
    """Interactive menu to explore action logs."""
    logs = load_action_logs()
    
    if not logs:
        return
    
    while True:
        print("\n" + "=" * 80)
        print("ACTION LOG VIEWER")
        print("=" * 80)
        print("1. List all websites")
        print("2. List runs for a website")
        print("3. View all tool calls for a run")
        print("4. View latest run")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == "1":
            list_websites(logs)
        
        elif choice == "2":
            website = input("Enter website (e.g., www.bet365.com): ").strip()
            list_runs(logs, website)
        
        elif choice == "3":
            website = input("Enter website: ").strip()
            run = input("Enter run timestamp: ").strip()
            view_all_tool_calls(logs, website, run)
        
        elif choice == "4":
            view_latest = input("View latest for specific website? (y/n): ").strip().lower()
            if view_latest == 'y':
                website = input("Enter website: ").strip()
                view_latest_run(logs, website)
            else:
                view_latest_run(logs)
        
        elif choice == "5":
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    interactive_menu()
