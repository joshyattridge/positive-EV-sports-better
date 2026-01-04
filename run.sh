#!/bin/bash
# Helper script to run project scripts with the correct Python environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

# Enable unbuffered Python output (fixes logging in screen/background)
export PYTHONUNBUFFERED=1

# Check if running in Docker (no venv needed) or use venv
if [ -f "/.dockerenv" ] || [ -n "$DOCKER_CONTAINER" ]; then
    # Running in Docker - use system Python
    PYTHON_CMD="python3"
elif [ -f "$VENV_PYTHON" ]; then
    # Running locally with venv
    PYTHON_CMD="$VENV_PYTHON"
else
    # No venv found and not in Docker
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
        $PYTHON_CMD -m src.core.positive_ev_scanner "$@"
        ;;
    auto-bet)
        echo "🤖 Running automated bet placer..."
        $PYTHON_CMD scripts/auto_bet_placer.py "$@"
        ;;
    bets)
        $PYTHON_CMD scripts/manage_bets.py "$@"
        ;;
    paper)
        # Paper trading commands - route to manage_bets with paper trade flag
        # Shift to get the subcommand and pass it before --paper-trade
        SUBCMD=$1
        shift
        $PYTHON_CMD scripts/manage_bets.py "$SUBCMD" --paper-trade "$@"
        ;;
    backtest)
        echo "📊 Running backtest..."
        $PYTHON_CMD -m src.utils.backtest "$@"
        ;;
    ignored)
        echo "🚫 Showing ignored bets..."
        $PYTHON_CMD scripts/show_ignored_bets.py "$@"
        ;;
    *)
        echo "❌ Unknown command: $COMMAND"
        echo "Run './run.sh' without arguments to see usage."
        exit 1
        ;;
esac
