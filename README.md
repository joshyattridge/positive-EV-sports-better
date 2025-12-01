# Positive EV Sports Betting

A sports betting analysis tool for identifying positive expected value (EV) betting opportunities, powered by AI-driven browser automation.

## Overview

This project helps identify sports betting opportunities with positive expected value by comparing odds across different sportsbooks and calculating the true probability of outcomes. It includes an AI-powered browser automation tool that can perform any browser-based task using natural language instructions.

## Features

- 🤖 **AI Browser Automation**: Use natural language to automate any browser task
- 📊 Compare odds across multiple sportsbooks
- 💰 Calculate expected value for betting opportunities
- ✅ Identify positive EV bets
- 📈 Track betting performance

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
# Edit .env and add your OpenAI API key
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

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js (for Playwright MCP server)
- OpenAI API key

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
