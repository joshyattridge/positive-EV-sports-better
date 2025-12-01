"""
Example usage of the Browser Automation tool

This file demonstrates how to use the browser automation functionality
for various tasks including sports betting research.
"""

import asyncio
from browser_automation import BrowserAutomation


async def example_simple_navigation():
    """Example: Place a bet on a sports event using the playwright MCP server."""
    automation = BrowserAutomation(headless=False)  # Set to True for headless mode
    
    try:
        task = """
        Navigate to https://www.bet365.com/#/AC/B1/C1/D8/E184564042/F3/G40/
        place a bet of £0.10 on Birmingham to win.
        username: ***REDACTED***
        password: ***REDACTED***

        After placing the bet you must confirm that the bet was placed successfully before ending the task.
        If you failed to place the bet you must try again until you succeed.
        """
        
        result = await automation.automate_task(task)
        print(f"\nResult: {result['response']}")
        print(f"Success: {result['success']}")
    finally:
        await automation.close_browser()

if __name__ == "__main__":
    # Run a simple example
    print("Running browser automation example...")
    asyncio.run(example_simple_navigation())
    
    # Or create your own custom task:
    # my_task = "Go to Google and search for 'positive expected value betting'"
    # result = asyncio.run(custom_task(my_task))
    # print(result)
