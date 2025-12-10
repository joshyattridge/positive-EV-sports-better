"""
Manual Playwright execution functions.

This module provides functions for manual Playwright browser control,
where each function takes an MCP session and performs a specific action.
"""

from mcp import ClientSession
from typing import Dict, Any


async def snapshot(session: ClientSession) -> Dict[str, Any]:
    """
    Capture an accessibility snapshot of the current page.
    
    Args:
        session: The MCP ClientSession object from BrowserAutomation
        
    Returns:
        Result from the browser_snapshot tool
    """
    result = await session.call_tool("browser_snapshot", {})
    return result


async def navigate(session: ClientSession, url: str) -> Any:
    """
    Navigate to a specified URL.
    
    Args:
        session: The MCP ClientSession object from BrowserAutomation
        url: The URL to navigate to
        
    Returns:
        Result from the browser_navigate tool
        
    Raises:
        Exception: If navigation fails
    """
    result = await session.call_tool("browser_navigate", {"url": url})
    return result
