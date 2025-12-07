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

## Browser Automation

The project includes a powerful browser automation tool (`browser_automation.py`) that uses:

- **OpenAI API (GPT-4)**: For understanding natural language instructions
- **Microsoft Playwright MCP Server**: For executing browser actions with accessibility-based automation

### Quick Start

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

# Kelly Criterion Bankroll Management
BANKROLL=1000          # Your total betting bankroll
KELLY_FRACTION=0.25    # Fraction of Kelly to use (0.25 = quarter Kelly, 0.5 = half Kelly, 1.0 = full Kelly)
```

5. **Run an example**:

```bash
python examples.py
```

### Simple Usage Example

```python
import asyncio
from browser_automation import BrowserAutomation

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

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
