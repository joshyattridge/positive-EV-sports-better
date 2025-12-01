"""
Browser Automation using OpenAI API and Playwright MCP Server

This module provides functionality to automate browser tasks using natural language
instructions powered by OpenAI's API and executed via Microsoft's Playwright MCP server.
"""

import os
import json
from typing import Optional, Dict, Any, List
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class BrowserAutomation:
    """
    A class to automate browser tasks using OpenAI and Playwright MCP server.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None, headless: bool = False):
        """
        Initialize the browser automation client.
        
        Args:
            openai_api_key: OpenAI API key. If not provided, will use OPENAI_API_KEY env var.
            headless: Whether to run browser in headless mode
        """
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY environment variable")
        
        self.client = OpenAI(api_key=self.api_key)
        self.session = None
        self.available_tools = []
        self.headless = headless
        
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
        
        # List available tools
        response = await self.session.list_tools()
        self.available_tools = response.tools
        print(f"Connected! {len(self.available_tools)} tools available")
        
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
    
    def _convert_tools_for_openai(self) -> List[Dict[str, Any]]:
        """
        Convert MCP tools to OpenAI function calling format.
        """
        openai_tools = []
        for tool in self.available_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            }
            openai_tools.append(openai_tool)
        return openai_tools
    
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
    
    async def automate_task(self, task_description: str, max_iterations: int = 20) -> Dict[str, Any]:
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
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a browser automation assistant. Use the available Playwright MCP tools "
                    "to complete the user's browser automation tasks. Execute the tools step by step "
                    "and provide clear feedback on what you're doing."
                )
            },
            {
                "role": "user",
                "content": task_description
            }
        ]
        
        openai_tools = self._convert_tools_for_openai()
        conversation_history = []
        
        for iteration in range(max_iterations):
            print(f"\n--- Iteration {iteration + 1} ---")
            
            # Get OpenAI's response
            response = self.client.chat.completions.create(
                model="gpt-5.1",
                messages=messages,
                tools=openai_tools,
                tool_choice="auto"
            )
            
            assistant_message = response.choices[0].message
            
            # Convert to dict for messages list
            message_dict = {
                "role": "assistant",
                "content": assistant_message.content
            }
            if assistant_message.tool_calls:
                message_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in assistant_message.tool_calls
                ]
            messages.append(message_dict)
            
            # Check if the assistant wants to call tools
            if assistant_message.tool_calls:
                print(f"Assistant is calling {len(assistant_message.tool_calls)} tool(s)...")
                
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    print(f"Calling tool: {tool_name}")
                    print(f"Arguments: {json.dumps(tool_args, indent=2)}")
                    
                    # Execute the tool via MCP
                    try:
                        result = await self.execute_tool_call(tool_name, tool_args)
                        # Extract content from MCP response
                        if hasattr(result, 'content') and result.content:
                            tool_result = json.dumps([c.model_dump() if hasattr(c, 'model_dump') else str(c) for c in result.content])
                        else:
                            tool_result = str(result)
                        print(f"Tool result: {tool_result[:200]}...")
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        })
                        
                        conversation_history.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": tool_result
                        })
                        
                    except Exception as e:
                        error_msg = f"Error executing tool {tool_name}: {str(e)}"
                        print(error_msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_msg
                        })
            else:
                # No more tool calls, task is complete
                final_response = assistant_message.content
                print(f"\nTask completed: {final_response}")
                
                return {
                    "success": True,
                    "response": final_response,
                    "conversation_history": conversation_history,
                    "iterations": iteration + 1
                }
        
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
