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
    echo "  scan                          - Scan for +EV opportunities"
    echo "  auto-bet [options]            - Automatically place best bet"
    echo "    --dry-run                   - Test mode (no actual bets)"
    echo "    --paper-trade               - Paper trade mode (log without placing)"
    echo "    --interval N                - Run continuously every N minutes"
    echo "    --max-bets N                - Stop after N bets (use with --interval)"
    echo "  bets summary                  - Show bet history summary"
    echo "  bets pending                  - List pending bets"
    echo "  bets update                   - Update bet results interactively"
    echo "  bets settle [--dry-run]       - Auto-settle bets using API scores"
    echo "  bets export                   - Export bets for analysis"
    echo "  backtest                      - Run historical backtest"
    echo "  ignored                       - Show bets ignored due to failures"
    echo "  paper summary                 - Show paper trading summary"
    echo "  paper pending                 - List pending paper trades"
    echo "  paper settle [--dry-run]      - Auto-settle paper trades"
    echo ""
    echo "Examples:"
    echo "  ./run.sh scan"
    echo "  ./run.sh auto-bet --dry-run"
    echo "  ./run.sh auto-bet --paper-trade"
    echo "  ./run.sh auto-bet --paper-trade --interval 15"
    echo "  ./run.sh auto-bet --interval 30 --max-bets 10"
    echo "  ./run.sh bets summary"
    echo "  ./run.sh bets settle"
    echo "  ./run.sh paper summary"
    echo "  ./run.sh paper settle"
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
    paper)
        # Paper trading commands - route to manage_bets with paper trade flag
        # Shift to get the subcommand and pass it before --paper-trade
        SUBCMD=$1
        shift
        $VENV_PYTHON scripts/manage_bets.py "$SUBCMD" --paper-trade "$@"
        ;;
    backtest)
        echo "📊 Running backtest..."
        $VENV_PYTHON -m src.utils.backtest "$@"
        ;;
    ignored)
        echo "🚫 Showing ignored bets..."
        $VENV_PYTHON scripts/show_ignored_bets.py "$@"
        ;;
    *)
        echo "❌ Unknown command: $COMMAND"
        echo "Run './run.sh' without arguments to see usage."
        exit 1
        ;;
esac
