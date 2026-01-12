# Positive EV Sports Betting

A sports betting analysis tool for identifying positive expected value (EV) betting opportunities, powered by AI-driven browser automation.

## Overview

This project helps identify sports betting opportunities with positive expected value by comparing odds across different sportsbooks and calculating the true probability of outcomes. It includes an AI-powered browser automation tool that can perform any browser-based task using natural language instructions.

## Features

- 🤖 **AI Browser Automation**: Use natural language to automate any browser task
- 📊 Compare odds across multiple sportsbooks
- 💰 Calculate expected value for betting opportunities
- ✅ Identify positive EV bets
- � **Kelly Criterion Bankroll Management**: Optimal bet sizing using 100% Kelly Criterion
- �📈 Track betting performance

## The Odds API Pricing & Cost Optimization

This project uses [The Odds API](https://the-odds-api.com/) to fetch live sports betting odds. Understanding the pricing model is crucial for optimizing your costs.

### Pricing Model

The Odds API charges based on **requests** and **regions**:

- **1 API call = 1 credit per sport** (for a single region and market)
- **Multiple markets** multiply the cost (e.g., 2 markets = 2× credits)
- **Bookmakers vs Regions**:
  - **1-10 bookmakers** = 1 region equivalent
  - **11-20 bookmakers** = 2 regions equivalent
  - **21-30 bookmakers** = 3 regions equivalent
  - **regions=uk** (gives 18-20 bookmakers) = 1 region equivalent
  - **regions=us** (gives 20-30 bookmakers) = 1 region equivalent

### Cost Calculation Example

If you scan with the default configuration:
- **143 sports** configured in BETTING_SPORTS
- **2 markets** (h2h, totals)
- **15 specific bookmakers** (11-20 range = 2 regions)

**Cost per scan:**
- Only ~30-50 sports have active events at any time
- Each sport costs: 2 markets × 2 regions = **4 credits**
- **Total: ~120-200 credits per scan**

### **IMPORTANT: Optimize Your Bookmaker Configuration**

To minimize API costs, **round your total bookmaker count to the nearest 10** (including sharp bookmakers):

#### ✅ Optimal Configurations:

- **10 bookmakers total** (sharp + betting books) = 1 region = **cheapest**
- **20 bookmakers total** = 2 regions
- **30 bookmakers total** = 3 regions

#### ❌ Wasteful Configurations:

- **11 bookmakers** = 2 regions (same cost as 20!)
- **15 bookmakers** = 2 regions (you're paying for 20 but only getting 15)
- **21 bookmakers** = 3 regions (same cost as 30!)

### Recommended Setup

**For UK bettors (BEST VALUE):**
```bash
# .env configuration
SHARP_BOOKS=betfair_ex_uk,matchbook,smarkets  # 3 sharp books
# Configure 7 betting bookmaker credentials for total of 10

# OR use regions for even better value:
# Use regions=uk in the code (gives you 18-20 bookmakers for 1 region cost)
```

**For 20 bookmakers:**
```bash
SHARP_BOOKS=pinnacle,betfair_ex_uk,matchbook  # 3 sharp books
# Configure 17 betting bookmaker credentials for total of 20
```

### Cost Reduction Strategies

1. **Use regions instead of specific bookmakers** (recommended for UK/US):
   - `regions=uk` gives you 18-20 UK bookmakers for 1 region cost
   - More bookmakers than 10-15 specific ones, but half the cost!

2. **Increase cache duration** (in positive_ev_scanner.py):
   - Default: 60 seconds
   - Recommended: 300-900 seconds (5-15 minutes)
   - Reduces API calls if you scan frequently

3. **Focus on fewer sports**:
   - Edit BETTING_SPORTS to only include leagues you bet on
   - Reduces total API calls per scan

4. **Count your bookmakers**:
   - Count SHARP_BOOKS + configured betting bookmaker credentials
   - Round to 10, 20, or 30 to avoid wasting credits
   - Don't use 11-19 bookmakers (you pay for 20 anyway!)

### Current API Usage

Check your current usage:
```bash
# This command will show your remaining credits
./run.sh scan
# Look for: "Odds API Usage: X requests used, Y requests remaining"
```

### Example Cost Savings

**Before optimization:**
- 15 bookmakers × 2 markets = 4 credits per sport
- 50 active sports = 200 credits per scan
- 500 scans per month = 100,000 credits

**After optimization (using regions=uk):**
- regions=uk × 2 markets = 2 credits per sport
- 50 active sports = 100 credits per scan
- 500 scans per month = 50,000 credits
- **Savings: 50%** 💰

---

## Browser Automation

The project includes a powerful browser automation tool (`browser_automation.py`) that uses:

- **OpenAI API (GPT-4)**: For understanding natural language instructions
- **Microsoft Playwright MCP Server**: For executing browser actions with accessibility-based automation

## Project Structure

```
positive-EV-sports-better/
├── src/                      # Source code
│   ├── core/                # Core betting logic
│   │   ├── positive_ev_scanner.py  # +EV opportunity scanner
│   │   └── kelly_criterion.py      # Kelly Criterion bet sizing
│   ├── automation/          # Browser automation
│   │   ├── browser_automation.py   # AI-powered browser control
│   │   └── action_logger.py        # Action logging
│   └── utils/               # Utilities
│       ├── bet_logger.py           # Bet tracking/logging
│       └── backtest.py             # Historical backtesting
├── scripts/                 # Executable scripts
│   ├── auto_bet_placer.py  # Automated bet placement
│   └── manage_bets.py      # Bet management utility
├── data/                    # Data files
│   ├── bet_history.csv     # Bet records
│   ├── action_logs.json    # Browser action logs
│   ├── backtest_cache/     # Cached backtest data
│   └── browser_states/     # Saved browser sessions
├── requirements.txt        # Python dependencies
├── .env                    # Configuration (create from .env.example)
└── README.md              # This file
```

### Quick Start

#### Option 1: Using Docker (Recommended)

1. **Clone the repository**:

```bash
git clone https://github.com/***REDACTED***dge/positive-EV-sports-better.git
cd positive-EV-sports-better
```

2. **Set up your environment**:

```bash
cp .env.example .env
# Edit .env and add your API keys and bankroll settings
```

3. **Build the Docker image**:

```bash
docker build -t positive-ev-sports-better .
```

4. **Run with Docker**:

```bash
# Scan for +EV opportunities
docker run --rm -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh scan

# Auto-bet (dry run)
docker run --rm -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh auto-bet --dry-run

# View bet history
docker run --rm -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh bets summary

# Settle bets
docker run --rm -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh bets settle

# Run default (auto-bet placer)
docker run --rm -v "$(pwd)/data:/app/data" positive-ev-sports-better
```

**Note**: The `-v "$(pwd)/data:/app/data"` flag mounts your local data directory so bet history persists between runs.

#### Option 2: Local Installation

1. **Clone the repository**:

```bash
git clone https://github.com/***REDACTED***dge/positive-EV-sports-better.git
cd positive-EV-sports-better
```

2. **Set up Python virtual environment**:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Set up your environment**:

```bash
cp .env.example .env
# Edit .env and add your API keys and bankroll settings
```

### Configuration

Edit your `.env` file with the following settings:

```bash
# API Keys
ODDS_API_KEY=your_odds_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Sharp Books (for true probability calculation)
SHARP_BOOKS=pinnacle,betfair_ex_uk,betfair_ex_eu,betfair_ex_au

# Betting Bookmakers (where to place bets)
BETTING_BOOKMAKERS=bet365,williamhill,ladbrokes_uk,coral,paddypower,skybet

# Sports/Leagues to scan
BETTING_SPORTS=soccer_epl,soccer_spain_la_liga,soccer_germany_bundesliga

# Minimum EV threshold (0.02 = 2%)
MIN_EV_THRESHOLD=0.02

# Maximum odds filter (5.0 = max 5x odds, set to 0.0 to disable)
MAX_ODDS=5.0

# Maximum days ahead filter (2.0 = only games within 2 days, set to 0 to disable)
MAX_DAYS_AHEAD=2.0

# Kelly Criterion Bankroll Management
BANKROLL=1000          # Your total betting bankroll
KELLY_FRACTION=0.25    # Fraction of Kelly to use (0.25 = quarter Kelly, 0.5 = half Kelly, 1.0 = full Kelly)
MIN_KELLY_PERCENTAGE=0.02  # Minimum Kelly percentage (0.02 = 2%, filters out tiny stakes)
BET_ROUNDING=0         # Round bets to nearest multiple (0=no rounding, 1=nearest £1, 5=nearest £5, 10=nearest £10)

# Failure Handling
MAX_BET_FAILURES=3     # Skip bets that fail this many times (set to 0 to disable)
```

5. **Activate virtual environment** (if not already active):

```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

6. **Run the tools**:

```bash
# Using the helper script (recommended)
./run.sh scan                    # Scan for +EV opportunities
./run.sh auto-bet --dry-run     # Place bets automatically (dry run)
./run.sh bets summary           # View bet history
./run.sh bets pending           # List pending bets
./run.sh bets update            # Update bet results
./run.sh bets export            # Export for analysis

# Or directly with venv Python
.venv/bin/python -m src.core.positive_ev_scanner
.venv/bin/python scripts/auto_bet_placer.py --dry-run
.venv/bin/python scripts/manage_bets.py summary
```

### Docker Usage

The project includes full Docker support for easy deployment and portability.

**Build the Docker image:**

```bash
docker build -t positive-ev-sports-better .
```

**Run any command:**

```bash
# Note: Add --env-file .env to load your API keys and configuration
# Scan for opportunities
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh scan

# Auto-bet with dry run
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh auto-bet --dry-run

# Paper trade continuously every 15 minutes
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh auto-bet --paper-trade --interval 15

# View bet summary
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh bets summary

# Settle bets automatically
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" positive-ev-sports-better ./run.sh bets settle

# Run default command (auto-bet placer)
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" positive-ev-sports-better
```

**Using docker-compose:**

```bash
# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

**Deploy to AWS:**

See [AWS-DEPLOYMENT.md](AWS-DEPLOYMENT.md) for detailed instructions on deploying to AWS EC2, ECS, or Lightsail.

### Helper Script (`run.sh`)

The project includes a convenient helper script that automatically uses the correct Python environment:

```bash
./run.sh <command> [options]
```

**Available Commands:**

- `scan` - Scan for positive EV betting opportunities
- `auto-bet [options]` - Automatically place the best bet
  - `--dry-run` - Test mode (no actual bets placed)
  - `--paper-trade` - Paper trade mode (log without placing)
  - `--interval N` - Run continuously every N minutes (waits between scans)
  - `--max-bets N` - Stop after placing N bets (works with or without --interval)
- `bets summary` - Show bet history summary
- `bets pending` - List pending bets awaiting results
- `bets update` - Interactively update bet results (win/loss)
- `bets settle` - Auto-settle bets using real game scores
- `bets export` - Export bet history for analysis
- `paper summary` - Show paper trading summary
- `paper pending` - List pending paper trades
- `paper settle` - Auto-settle paper trades
- `backtest` - Run historical backtesting
- `ignored` - Show bets being ignored due to repeated failures

**Examples:**

```bash
# Scan for opportunities
./run.sh scan

# Test automated betting (safe mode)
./run.sh auto-bet --dry-run

# Live paper trading (logs without placing real bets)
./run.sh auto-bet --paper-trade

# Continuous paper trading - every 15 minutes
./run.sh auto-bet --paper-trade --interval 15

# Place 10 paper trades rapidly (back-to-back scans)
./run.sh auto-bet --paper-trade --max-bets 10

# Continuous live betting - every 30 minutes, max 10 bets
./run.sh auto-bet --interval 30 --max-bets 10

# Place actual bet once (be careful!)
./run.sh auto-bet

# Check your bet history
./run.sh bets summary

# Auto-settle completed bets
./run.sh bets settle

# Paper trading results
./run.sh paper summary
./run.sh paper settle

# Update a bet result manually
./run.sh bets update

# View bets being ignored due to repeated failures
./run.sh ignored
```

### Paper Trading

Test your strategy with real market data without risking money. See [PAPER_TRADING.md](PAPER_TRADING.md) for full documentation.

**Quick start:**

```bash
# Single paper trade
./run.sh auto-bet --paper-trade

# Continuous paper trading (every 15 minutes)
./run.sh auto-bet --paper-trade --interval 15

# Place 10 paper trades as fast as possible
./run.sh auto-bet --paper-trade --max-bets 10

# Run for specific duration (96 bets at 15min intervals)
./run.sh auto-bet --paper-trade --interval 15 --max-bets 96

# View results
./run.sh paper summary
./run.sh paper settle
```

Paper trades are stored separately in `data/paper_trade_history.csv` and can be auto-settled using real game results.

### Automatic Failure Handling

The system automatically tracks bets that fail to place multiple times and will ignore them in future scans to avoid repeated failures. This is controlled by the `MAX_BET_FAILURES` setting in your `.env` file (default: 3).

**How it works:**

- If a bet fails to place (e.g., due to odds changes, website issues), it's logged with `not_placed` status
- After 3 failures (or your configured threshold), that specific bet opportunity is automatically skipped
- The system tracks each unique combination of game_id + market + outcome separately

**Managing ignored bets:**

```bash
# View currently ignored bets
./run.sh ignored

# Change the threshold (in .env file)
MAX_BET_FAILURES=5    # More tolerant - ignore after 5 failures
MAX_BET_FAILURES=2    # Less tolerant - ignore after 2 failures
MAX_BET_FAILURES=0    # Disable feature - never ignore failed bets
```

### Simple Usage Example

```python
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.automation.browser_automation import BrowserAutomation

async def main():
    automation = BrowserAutomation(headless=False)

    try:
        result = await automation.automate_task(
            "Go to example.com and take a screenshot"
        )
        print(result['response'])
    finally:
        await automation.close_browser()

asyncio.run(main())
```

### Usage Examples

Check out `examples.py` for various use cases:

- Simple website navigation
- Sports odds research
- Form filling
- Custom automation tasks

### Custom Tasks

You can automate any browser task with natural language:

```python
automation = BrowserAutomation()
await automation.connect_to_playwright()

result = await automation.automate_task("""
    Go to a sports betting website,
    find today's NBA games,
    compare the odds,
    and take screenshots of the best opportunities
""")
```

## Kelly Criterion Bankroll Management

The scanner uses the **Kelly Criterion** formula to calculate optimal bet sizing based on your edge:

```
f* = (bp - q) / b

Where:
- f* = fraction of bankroll to bet
- b = decimal odds - 1
- p = true probability of winning
- q = probability of losing (1 - p)
```

### How It Works:

- Set your **BANKROLL** in the `.env` file
- Kelly calculates the optimal percentage to bet
- Bet sizes scale with your actual bankroll

### Features:

- **Fractional Kelly**: Use 25% Kelly (recommended), 50% Kelly, or full Kelly
- **Bankroll-Based**: All bets calculated as percentage of your total bankroll
- **Expected Profit**: Shows anticipated return per bet
- **Dynamic Sizing**: Bets automatically scale as your bankroll grows/shrinks
- **Risk Management**: Lower fractions = less variance, more conservative
- **Minimum Kelly Filter**: Filter out bets with stakes too small to be practical

### Kelly Fraction Guide:

- **1.0 (Full Kelly)**: Maximum growth, but high variance - can lose 50%+ of bankroll
- **0.5 (Half Kelly)**: Good balance of growth and safety - recommended for most
- **0.25 (Quarter Kelly)**: Conservative approach - much lower variance
- **0.1-0.2**: Very conservative - minimal risk

### Example Output:

```
💵 RECOMMENDED BET SIZE (25% Kelly):
   Stake: £11.38
   Kelly %: 1.14% of bankroll
   Expected Profit: £0.80
```

With a £1000 bankroll and 25% Kelly fraction:

- Full Kelly would be 4.55% (£45.50)
- 25% Kelly = 1.14% of bankroll = £11.38

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js (for Playwright MCP server)
- OpenAI API key

## Testing

The project includes a comprehensive test suite with 170+ unit tests covering all modules.

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_kelly_criterion.py

# Use the convenient test runner script
./run_tests.sh              # Run all tests
./run_tests.sh coverage     # Run with coverage
./run_tests.sh kelly        # Run Kelly Criterion tests only
```

### Test Coverage

- **Kelly Criterion**: 15 tests - bet sizing, expected profit calculations
- **Positive EV Scanner**: 35 tests - EV calculations, odds conversions, sorting
- **Bet Logger**: 25 tests - logging, tracking, summary generation
- **Backtest**: 25 tests - historical testing, caching, reports
- **Action Logger**: 30 tests - automation logging, data redaction
- **Auto Bet Placer**: 20 tests - bet placement, verification
- **Manage Bets**: 15 tests - CLI functions, result updates

See [TEST_SUITE_SUMMARY.md](TEST_SUITE_SUMMARY.md) for detailed test documentation.

### Continuous Integration

Tests run automatically on every push via GitHub Actions. See `.github/workflows/tests.yml`.

## License

MIT License

## Contributing

Contributions are welcome! Please:

1. Write tests for new features
2. Ensure all tests pass: `pytest`
3. Maintain test coverage above 80%
4. Submit a Pull Request
