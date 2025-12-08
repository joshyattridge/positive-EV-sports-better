"""
Browser Automation using Anthropic Claude API and Playwright MCP Server

This module provides functionality to automate browser tasks using natural language
instructions powered by Anthropic's Claude API and executed via Microsoft's Playwright MCP server.
"""

import os
import json
import re
from typing import Optional, Dict, Any, List
from pathlib import Path
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from action_logger import ActionLogger

# Load environment variables from .env file
load_dotenv()


class BrowserAutomation:
    """
    A class to automate browser tasks using Anthropic Claude and Playwright MCP server.
    """
    
    def __init__(self, anthropic_api_key: Optional[str] = None, headless: bool = False, 
                 action_log_path: str = "action_logs.json",
                 state_dir: str = "browser_states"):
        """
        Initialize the browser automation client.
        
        Args:
            anthropic_api_key: Anthropic API key. If not provided, will use ANTHROPIC_API_KEY env var.
            headless: Whether to run browser in headless mode
            action_log_path: Path to save successful action logs (organized by website and run timestamp)
            state_dir: Directory to store browser state files (cookies, storage, etc.)
        """
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key must be provided or set in ANTHROPIC_API_KEY environment variable")
        
        self.client = Anthropic(api_key=self.api_key)
        self.session = None
        self.available_tools = []
        self.headless = headless
        self.action_logger = ActionLogger(log_path=action_log_path)
        
        # State persistence setup
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.current_state_file = None
        self.use_persistent_profile = True  # Use --user-data-dir for full persistence
        
    def _get_state_file(self, website: Optional[str] = None) -> Path:
        """
        Get the state file path for a website.
        
        Args:
            website: Website domain (e.g., 'www.bet365.com'). If None, uses current website.
        
        Returns:
            Path to the state file
        """
        if website is None:
            website = self.action_logger.current_website or "default"
        # Clean website name for filename
        clean_name = website.replace("https://", "").replace("http://", "").replace("/", "_")
        return self.state_dir / f"{clean_name}_state.json"
    
    async def connect_to_playwright(self):
        """
        Connect to the Microsoft Playwright MCP server.
        
        Uses --user-data-dir for persistent browser profiles, which captures:
        - All cookies (including HttpOnly)
        - localStorage, sessionStorage
        - Browser cache, history
        - Extensions, settings
        """
        # Configure the Playwright MCP server connection
        args = ["@playwright/mcp@latest"]
        if self.headless:
            args.append("--headless")
        
        # Use user-data-dir for persistent browser profile
        # This captures EVERYTHING including HttpOnly cookies
        if self.use_persistent_profile and self.current_state_file:
            # Use the state file path's stem as the profile directory name
            profile_dir = self.state_dir / f"{self.current_state_file.stem}_profile"
            profile_dir.mkdir(exist_ok=True)
            args.extend(["--user-data-dir", str(profile_dir)])
            print(f"🔐 Using persistent browser profile: {profile_dir}")
        
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
        
    async def save_browser_state(self, website: Optional[str] = None) -> Optional[Path]:
        """
        Save the current browser state (cookies, storage, etc.).
        
        Note: When use_persistent_profile=True (default), browser state is automatically
        saved to disk by Playwright via --user-data-dir. This method still saves a JSON
        snapshot for reference/debugging.
        
        Args:
            website: Website domain to associate state with. If None, uses current website.
        
        Returns:
            Path to the saved state file, or None if save failed
        """
        if not self.session:
            print("⚠️ Cannot save state: not connected to browser")
            return None
        
        state_file = self._get_state_file(website)
        
        try:
            # Get cookies and storage via JavaScript evaluation
            result = await self.session.call_tool("browser_evaluate", {
                "function": """async () => {
                    // Get all cookies
                    const cookies = document.cookie.split(';').map(c => c.trim());
                    
                    // Get localStorage
                    const localStorageData = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        localStorageData[key] = localStorage.getItem(key);
                    }
                    
                    // Get sessionStorage  
                    const sessionStorageData = {};
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        sessionStorageData[key] = sessionStorage.getItem(key);
                    }
                    
                    return JSON.stringify({
                        cookies: cookies,
                        localStorage: localStorageData,
                        sessionStorage: sessionStorageData,
                        url: window.location.href,
                        timestamp: new Date().toISOString()
                    });
                }"""
            })
            
            # Extract the result from MCP response
            if hasattr(result, 'content') and result.content:
                # Parse the text content from the result
                content_item = result.content[0]
                if hasattr(content_item, 'text'):
                    text_content = content_item.text
                    
                    # The result comes as: ### Result\n"<json_string>"\n\n### Ran Playwright code...
                    # We need to extract the JSON string between quotes after "### Result"
                    lines = text_content.split('\n')
                    for line in lines:
                        line = line.strip()
                        # Skip header lines
                        if line.startswith('#') or not line:
                            continue
                        # Found the result line - it's a JSON string wrapped in quotes
                        if line.startswith('"') and line.endswith('"'):
                            # Remove outer quotes and unescape
                            state_data = json.loads(line)  # This parses the quoted JSON string
                            # state_data is now the actual JSON string, write it
                            state_file.write_text(state_data)
                            print(f"💾 Browser state saved to: {state_file}")
                            return state_file
                        elif line.startswith('{') or line.startswith('['):
                            # Direct JSON (shouldn't happen with our code but handle it)
                            json.loads(line)  # Validate
                            state_file.write_text(line)
                            print(f"💾 Browser state saved to: {state_file}")
                            return state_file
            
            print("⚠️ No state data returned from browser")
            return None
            
        except Exception as e:
            print(f"⚠️ Failed to save browser state: {e}")
            return None
    
    async def load_browser_state(self, website: Optional[str] = None) -> bool:
        """
        Load browser state (cookies, storage) from a saved file.
        
        Args:
            website: Website domain to load state for. If None, uses current website.
        
        Returns:
            True if state was loaded successfully, False otherwise
        """
        if not self.session:
            print("⚠️ Cannot load state: not connected to browser")
            return False
        
        state_file = self._get_state_file(website)
        
        if not state_file.exists():
            print(f"ℹ️ No saved state found for {website or 'current site'}")
            return False
        
        try:
            state_data = json.loads(state_file.read_text())
            
            # Restore cookies and storage via JavaScript
            restore_code = f"""
                async () => {{
                    const state = {json.dumps(state_data)};
                    
                    // Restore cookies
                    if (state.cookies && Array.isArray(state.cookies)) {{
                        state.cookies.forEach(cookie => {{
                            if (cookie) document.cookie = cookie;
                        }});
                    }}
                    
                    // Restore localStorage
                    if (state.localStorage) {{
                        Object.keys(state.localStorage).forEach(key => {{
                            localStorage.setItem(key, state.localStorage[key]);
                        }});
                    }}
                    
                    // Restore sessionStorage
                    if (state.sessionStorage) {{
                        Object.keys(state.sessionStorage).forEach(key => {{
                            sessionStorage.setItem(key, state.sessionStorage[key]);
                        }});
                    }}
                    
                    return 'State restored successfully';
                }}
            """
            
            result = await self.session.call_tool("browser_evaluate", {
                "function": restore_code
            })
            
            print(f"✅ Browser state loaded from: {state_file}")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to load browser state: {e}")
            return False
    
    async def close_browser(self, save_state: bool = True):
        """
        Close the browser and cleanup.
        
        Args:
            save_state: Whether to save browser state before closing
        """
        if self.session and save_state:
            await self.save_browser_state()
        
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
        # Extract website from task description
        url_pattern = r'https?://(?:www\.)?([^\s/]+)'
        url_match = re.search(url_pattern, task_description)
        url = url_match.group(0) if url_match else None
        
        # Extract domain for state file
        target_domain = None
        if url:
            parsed_url = url_match.group(0) if url_match else None
            if parsed_url:
                target_domain = parsed_url.split('/')[2] if '/' in parsed_url else parsed_url.replace('https://', '').replace('http://', '')
                self.current_state_file = self._get_state_file(target_domain)
        
        if not self.session:
            await self.connect_to_playwright()
        
        run_timestamp = self.action_logger.start_new_run(url)
        
        # If we have a saved state for this domain, mention it in the task
        if target_domain and self._get_state_file(target_domain).exists():
            print(f"💡 Saved state available for {target_domain} - will attempt to restore after navigation")
        
        # Enhance task description with tool calls from previous runs on this website
        enhanced_task = task_description
        previous_tool_calls = self.action_logger.get_all_tool_calls(website=self.action_logger.current_website)
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
                            self.action_logger.update_current_website(tool_args["url"])
                        
                        result = await self.execute_tool_call(tool_name, tool_args)
                        # Extract content from MCP response
                        if hasattr(result, 'content') and result.content:
                            tool_result = json.dumps([c.model_dump() if hasattr(c, 'model_dump') else str(c) for c in result.content])
                        else:
                            tool_result = str(result)
                        print(f"Tool result: {tool_result[:200]}...")
                        
                        # 🆕 RECORD EVERY TOOL CALL AUTOMATICALLY
                        self.action_logger.record_tool_call(tool_name, tool_args)
                        
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
                        self.action_logger.record_tool_call(tool_name, tool_args)
                        
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
                self.action_logger.print_run_summary()
                
                return {
                    "success": True,
                    "response": final_response,
                    "conversation_history": conversation_history,
                    "iterations": iteration + 1
                }
        
        # Print summary even if max iterations reached
        self.action_logger.print_run_summary()
        
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
