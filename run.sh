#!/bin/bash
# Helper script to run project scripts with the correct Python environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage: ./run.sh <command>"
    echo ""
    echo "Commands:"
    echo "  scan                  - Scan for +EV opportunities"
    echo "  auto-bet [--dry-run]  - Automatically place best bet"
    echo "  bets summary          - Show bet history summary"
    echo "  bets pending          - List pending bets"
    echo "  bets update           - Update bet results interactively"
    echo "  bets export           - Export bets for analysis"
    echo "  backtest              - Run historical backtest"
    echo ""
    echo "Examples:"
    echo "  ./run.sh scan"
    echo "  ./run.sh auto-bet --dry-run"
    echo "  ./run.sh bets summary"
    exit 0
fi

# Parse command
COMMAND=$1
shift

case $COMMAND in
    scan)
        echo "🔍 Scanning for +EV opportunities..."
        $VENV_PYTHON -m src.core.positive_ev_scanner "$@"
        ;;
    auto-bet)
        echo "🤖 Running automated bet placer..."
        $VENV_PYTHON scripts/auto_bet_placer.py "$@"
        ;;
    bets)
        $VENV_PYTHON scripts/manage_bets.py "$@"
        ;;
    backtest)
        echo "📊 Running backtest..."
        $VENV_PYTHON -m src.utils.backtest "$@"
        ;;
    *)
        echo "❌ Unknown command: $COMMAND"
        echo "Run './run.sh' without arguments to see usage."
        exit 1
        ;;
esac
