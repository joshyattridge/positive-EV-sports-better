"""
Browser Automation using Anthropic Claude API and Playwright MCP Server

This module provides functionality to automate browser tasks using natural language
instructions powered by Anthropic's Claude API and executed via Microsoft's Playwright MCP server.
"""

import os
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class BrowserAutomation:
    """
    A class to automate browser tasks using Anthropic Claude and Playwright MCP server.
    """
    
    def __init__(self, anthropic_api_key: Optional[str] = None, headless: bool = False, 
                 action_log_path: str = "action_logs.json"):
        """
        Initialize the browser automation client.
        
        Args:
            anthropic_api_key: Anthropic API key. If not provided, will use ANTHROPIC_API_KEY env var.
            headless: Whether to run browser in headless mode
            action_log_path: Path to save successful action logs (organized by website and run timestamp)
        """
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key must be provided or set in ANTHROPIC_API_KEY environment variable")
        
        self.client = Anthropic(api_key=self.api_key)
        self.session = None
        self.available_tools = []
        self.headless = headless
        self.action_log_path = Path(action_log_path)
        # Action logs structure: {website: {timestamp: {action_name: [tool_calls]}}}
        self.action_logs = self._load_action_logs()
        self.current_website = None  # Track the current website domain
        
    async def connect_to_playwright(self):
        """
        Connect to the Microsoft Playwright MCP server.
        """
        # Configure the Playwright MCP server connection
        args = ["@playwright/mcp@latest"]
        if self.headless:
            args.append("--headless")
        
        server_params = StdioServerParameters(
            command="npx",
            args=args,
            env=None
        )
        
        print(f"Connecting to Playwright MCP server (headless={self.headless})...")
        
        # Store the context managers to properly manage them
        self._stdio_context = stdio_client(server_params)
        self.read_stream, self.write_stream = await self._stdio_context.__aenter__()
        
        self._session_context = ClientSession(self.read_stream, self.write_stream)
        self.session = await self._session_context.__aenter__()
        
        # Initialize the connection
        await self.session.initialize()
        
        # List available tools and filter out screenshot
        response = await self.session.list_tools()
        self.available_tools = [
            tool for tool in response.tools 
            if tool.name != "browser_take_screenshot"
        ]
        print(f"Connected! {len(self.available_tools)} tools available (screenshot disabled)")
        
        return self.session
        
    async def close_browser(self):
        """
        Close the browser and cleanup.
        """
        if self.session:
            try:
                # Try to close the browser via MCP
                await self.session.call_tool("browser_close", {})
            except:
                pass
        
        # Properly exit the context managers
        if hasattr(self, '_session_context') and self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except:
                pass
        
        if hasattr(self, '_stdio_context') and self._stdio_context:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except:
                pass
        
        print("Browser closed")
    
    def _load_action_logs(self) -> Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]:
        """
        Load action logs from disk.
        
        Returns:
            Dictionary mapping websites to timestamps to action logs: {website: {timestamp: {action_name: [tool_calls]}}}
        """
        if self.action_log_path.exists():
            try:
                with open(self.action_log_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load action logs: {e}")
                return {}
        return {}
    
    def _save_action_logs(self):
        """
        Save action logs to disk.
        """
        try:
            with open(self.action_log_path, 'w') as f:
                json.dump(self.action_logs, f, indent=2)
            print(f"Action logs saved to {self.action_log_path}")
        except Exception as e:
            print(f"Warning: Could not save action logs: {e}")
    
    def _extract_domain(self, url: str) -> str:
        """
        Extract the domain from a URL and normalize it to match stored action logs.
        
        Args:
            url: Full URL string
            
        Returns:
            Normalized domain name (e.g., "www.bet365.com")
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            
            if not domain:
                return "unknown"
            
            # Normalize: check if domain exists with or without www. in action logs
            # First, check both variants
            domain_with_www = f"www.{domain}" if not domain.startswith('www.') else domain
            domain_without_www = domain[4:] if domain.startswith('www.') else domain
            
            # Check which variant exists in our logs
            if domain_with_www in self.action_logs:
                return domain_with_www
            elif domain_without_www in self.action_logs:
                return domain_without_www
            else:
                # If neither exists, default to the www. version for consistency
                return domain_with_www
        except:
            return "unknown"
    
    def update_current_website(self, url: str):
        """
        Update the current website being automated based on URL.
        
        Args:
            url: The URL being navigated to
        """
        self.current_website = self._extract_domain(url)
        print(f"🌐 Current website: {self.current_website}")
    
    def record_tool_call(self, run_timestamp: str, tool_name: str, tool_args: Dict[str, Any]):
        """
        Record every single tool call that is executed, regardless of success or LLM markers.
        This provides a complete audit trail of all browser actions.
        
        Args:
            run_timestamp: Timestamp identifying this run
            tool_name: Name of the tool that was called
            tool_args: Arguments passed to the tool
        """
        # Use current website or "unknown" if not set
        website = self.current_website or "unknown"
        
        # Ensure the website exists in action logs
        if website not in self.action_logs:
            self.action_logs[website] = {}
        
        # Ensure the run timestamp exists under this website as an array
        if run_timestamp not in self.action_logs[website]:
            self.action_logs[website][run_timestamp] = []
        
        # Record the tool call (just tool name and args)
        tool_call_record = {
            "tool": tool_name,
            "args": tool_args
        }
        
        self.action_logs[website][run_timestamp].append(tool_call_record)
        
        # Save after each tool call to ensure we don't lose data (but don't spam the console)
        try:
            with open(self.action_log_path, 'w') as f:
                json.dump(self.action_logs, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save tool call log: {e}")
    
    def get_all_tool_calls(self, website: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all tool calls from previous runs, optionally filtered by website.
        
        Args:
            website: Optional website domain to filter by (e.g., "example.com")
        
        Returns:
            List of all tool calls from previous runs
        """
        all_tool_calls = []
        
        # If website specified, only look at that website's logs
        if website:
            if website in self.action_logs:
                for run_timestamp, tool_calls in self.action_logs[website].items():
                    if isinstance(tool_calls, list):
                        all_tool_calls.extend(tool_calls)
        else:
            # Get tool calls from all websites
            for website_name, website_logs in self.action_logs.items():
                for run_timestamp, tool_calls in website_logs.items():
                    if isinstance(tool_calls, list):
                        all_tool_calls.extend(tool_calls)
        
        return all_tool_calls
    
    def _convert_tools_for_claude(self) -> List[Dict[str, Any]]:
        """
        Convert MCP tools to Claude tool format.
        """
        claude_tools = []
        for tool in self.available_tools:
            claude_tool = {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema
            }
            claude_tools.append(claude_tool)
        return claude_tools
    
    async def execute_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """
        Execute a tool call via the MCP session.
        
        Args:
            tool_name: Name of the tool to call
            tool_args: Arguments for the tool
            
        Returns:
            Result from the tool execution
        """
        if not self.session:
            raise RuntimeError("Not connected to Playwright server. Call connect_to_playwright() first.")
        
        result = await self.session.call_tool(tool_name, tool_args)
        return result
    
    async def automate_task(self, task_description: str, max_iterations: int = 40) -> Dict[str, Any]:
        """
        Automate a browser task using natural language description.
        
        Args:
            task_description: Natural language description of the task to automate
            max_iterations: Maximum number of iterations to attempt
            
        Returns:
            Dictionary containing the task results and conversation history
        """
        if not self.session:
            await self.connect_to_playwright()
        
        # Generate timestamp for this run
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"🕐 Run timestamp: {run_timestamp}")
        
        # Try to extract website from task description
        import re
        url_pattern = r'https?://(?:www\.)?([^\s/]+)'
        url_match = re.search(url_pattern, task_description)
        if url_match:
            full_url = url_match.group(0)
            self.update_current_website(full_url)
        
        # Enhance task description with tool calls from previous runs on this website
        enhanced_task = task_description
        previous_tool_calls = self.get_all_tool_calls(website=self.current_website)
        if previous_tool_calls:
            # Limit to most recent tool calls to avoid token overflow (last 50 calls)
            recent_calls = previous_tool_calls[-50:] if len(previous_tool_calls) > 50 else previous_tool_calls
            
            if recent_calls:
                enhanced_task += "\n\n--- Previously Executed Tool Calls (use as reference) ---\n"
                for call in recent_calls:
                    enhanced_task += f"  {json.dumps(call)}\n"
                enhanced_task += "\n--- End of Reference Tool Calls ---\n"
                print(f"📚 Added {len(recent_calls)} previous tool calls to task context")
        
        system_prompt = (
            "You are a browser automation assistant. Use the available Playwright MCP tools "
            "to complete the user's browser automation tasks.\n\n"
            "🎯 FIRST RESPONSE STRATEGY 🎯\n"
            "On your FIRST response, if you've been provided with 'Previously Executed Tool Calls' in the task:\n"
            "1. Analyze the tool call history to understand what worked before\n"
            "2. Attempt to execute ALL the necessary tool calls in ONE SHOT\n"
            "3. Chain together similar actions from the history that apply to this task\n"
            "4. Only request a snapshot if you need to see the current page state\n\n"
            "⚡ EFFICIENCY RULE - MINIMIZE API CALLS ⚡\n"
            "You MUST batch multiple independent tool calls in a SINGLE response whenever possible.\n\n"
            "DO batch together:\n"
            "✓ Navigation + snapshot (navigate then immediately snapshot)\n"
            "✓ Multiple form field fills (username, password, etc.)\n"
            "✓ Snapshot + any click/type that doesn't need to see snapshot first\n"
            "✓ Sequential actions from the action logs (click login, type password, click submit, etc.)\n"
            "✓ Any actions where order doesn't matter\n\n"
            "ONLY separate when:\n"
            "✗ Next action requires reading the result of the previous one\n"
            "✗ Page needs to load/change before next action\n"
            "✗ You need to verify the page state with a snapshot\n\n"
            "Keep text responses SHORT - one sentence max.\n\n"
            "💰 BET SIZE ENTRY TIP 💰\n"
            "When entering stake amounts in betting forms, use the browser_run_code tool with:\n"
            "await page.keyboard.type('0.10');\n"
            "This works more reliably than trying to enter the amount once the field is focused.\n"
            "Example: To bet £0.09, use: await page.keyboard.type('0.09');"
        )
        
        messages = [
            {
                "role": "user",
                "content": enhanced_task
            }
        ]
        
        claude_tools = self._convert_tools_for_claude()
        conversation_history = []
        
        for iteration in range(max_iterations):
            print(f"\n--- Iteration {iteration + 1} ---")
            
            # Truncate old tool results (keep only last tool result full, truncate older ones)
            # This dramatically reduces token usage while keeping recent context
            for i, message in enumerate(messages[:-1]):  # Skip the last message (most recent)
                if message.get("role") == "user" and isinstance(message.get("content"), list):
                    for content_item in message["content"]:
                        if content_item.get("type") == "tool_result":
                            original_content = content_item.get("content", "")
                            if len(original_content) > 50:
                                content_item["content"] = original_content[:50] + "...[old result truncated]"
        
            print(f"Sending messages to Claude (total messages: {len(messages)})...")
            
            # Calculate approximate token count (need to convert to JSON-serializable format)
            def make_serializable(obj):
                """Convert message objects to JSON-serializable format"""
                if hasattr(obj, 'model_dump'):
                    return obj.model_dump()
                elif isinstance(obj, list):
                    return [make_serializable(item) for item in obj]
                elif isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                else:
                    return str(obj)
            
            try:
                serializable_messages = [make_serializable(m) for m in messages]
                total_chars = sum(len(json.dumps(m)) for m in serializable_messages)
                print(f"Approximate character count in all messages: {total_chars}")
            except Exception as e:
                print(f"Could not calculate message size: {e}")
            
            # Get Claude's response
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=claude_tools
            )
            
            # Add assistant's response to messages
            assistant_message = {
                "role": "assistant",
                "content": response.content
            }
            messages.append(assistant_message)
            
            # Check if Claude wants to call tools
            tool_calls = [block for block in response.content if block.type == "tool_use"]
            
            if tool_calls:
                print(f"Assistant is calling {len(tool_calls)} tool(s)...")
                
                tool_results = []
                current_batch_tool_calls = []  # Track this batch of tool calls
                for tool_call in tool_calls:
                    tool_name = tool_call.name
                    tool_args = tool_call.input
                    
                    print(f"Calling tool: {tool_name}")
                    print(f"Arguments: {json.dumps(tool_args, indent=2)}")
                    
                    # Execute the tool via MCP
                    try:
                        # Track navigation to update current website
                        if tool_name == "browser_navigate" and "url" in tool_args:
                            self.update_current_website(tool_args["url"])
                        
                        result = await self.execute_tool_call(tool_name, tool_args)
                        # Extract content from MCP response
                        if hasattr(result, 'content') and result.content:
                            tool_result = json.dumps([c.model_dump() if hasattr(c, 'model_dump') else str(c) for c in result.content])
                        else:
                            tool_result = str(result)
                        print(f"Tool result: {tool_result[:200]}...")
                        
                        # 🆕 RECORD EVERY TOOL CALL AUTOMATICALLY
                        self.record_tool_call(run_timestamp, tool_name, tool_args)
                        
                        # Send FULL result to Claude initially (will be truncated in next iteration)
                        # This way the latest result is always complete
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": tool_result
                        })
                        
                        # Store FULL result in conversation history (not sent to API)
                        conversation_history.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": tool_result  # Full result stored here
                        })
                        
                        # Also track for current batch (for recording)
                        current_batch_tool_calls.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": tool_result
                        })
                        
                    except Exception as e:
                        error_msg = f"Error executing tool {tool_name}: {str(e)}"
                        print(error_msg)
                        
                        # 🆕 RECORD FAILED TOOL CALLS TOO
                        self.record_tool_call(run_timestamp, tool_name, tool_args)
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": error_msg,
                            "is_error": True
                        })
                
                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })
            else:
                # No more tool calls, check if we have a text response
                text_content = [block.text for block in response.content if hasattr(block, 'text')]
                final_response = ' '.join(text_content) if text_content else "Task completed"
                
                print(f"\nTask completed: {final_response}")
                
                # Print summary of recorded tool calls
                website = self.current_website or "unknown"
                if website in self.action_logs and run_timestamp in self.action_logs[website]:
                    total_tools = len(self.action_logs[website][run_timestamp])
                    print(f"📝 Recorded {total_tools} tool calls to action_logs.json")
                
                return {
                    "success": True,
                    "response": final_response,
                    "conversation_history": conversation_history,
                    "iterations": iteration + 1
                }
        
        # Print summary even if max iterations reached
        website = self.current_website or "unknown"
        if website in self.action_logs and run_timestamp in self.action_logs[website]:
            total_tools = len(self.action_logs[website][run_timestamp])
            print(f"📝 Recorded {total_tools} tool calls to action_logs.json")
        
        return {
            "success": False,
            "response": "Max iterations reached",
            "conversation_history": conversation_history,
            "iterations": max_iterations
        }


async def main():
    """
    Example usage of the BrowserAutomation class.
    """
    # Example task
    task = """
    Go to https://example.com, take a screenshot of the page, and tell me what you see.
    """
    
    automation = BrowserAutomation(headless=False)  # Set to True for headless mode
    
    try:
        result = await automation.automate_task(task)
        
        print("\n" + "="*50)
        print("FINAL RESULT")
        print("="*50)
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await automation.close_browser()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
