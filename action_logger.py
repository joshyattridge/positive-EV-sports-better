"""
Action Logger Module

This module provides functionality to log and retrieve browser automation tool calls.
Logs are organized by website and run timestamp to track automation history.
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


class ActionLogger:
    """
    A class to manage logging and retrieval of browser automation actions.
    
    Action logs are structured as:
    {
        website: {
            timestamp: [
                {tool: "tool_name", args: {...}},
                ...
            ]
        }
    }
    """
    
    def __init__(self, log_path: str = "action_logs.json"):
        """
        Initialize the action logger.
        
        Args:
            log_path: Path to save action logs
        """
        self.log_path = Path(log_path)
        self.action_logs = self._load_action_logs()
        self.current_website = None
        self.current_run_timestamp = None
        
    def _load_action_logs(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Load action logs from disk.
        
        Returns:
            Dictionary mapping websites to timestamps to action logs: 
            {website: {timestamp: [tool_calls]}}
        """
        if self.log_path.exists():
            try:
                with open(self.log_path, 'r') as f:
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
            with open(self.log_path, 'w') as f:
                json.dump(self.action_logs, f, indent=2)
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
    
    def start_new_run(self, url: Optional[str] = None) -> str:
        """
        Start a new automation run, generating a timestamp and optionally setting the website.
        
        Args:
            url: Optional URL to extract website from
            
        Returns:
            The run timestamp
        """
        self.current_run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if url:
            self.update_current_website(url)
        
        print(f"🕐 Run timestamp: {self.current_run_timestamp}")
        return self.current_run_timestamp
    
    def update_current_website(self, url: str):
        """
        Update the current website being automated based on URL.
        
        Args:
            url: The URL being navigated to
        """
        self.current_website = self._extract_domain(url)
        print(f"🌐 Current website: {self.current_website}")
    
    def record_tool_call(self, tool_name: str, tool_args: Dict[str, Any], 
                        run_timestamp: Optional[str] = None):
        """
        Record a tool call that was executed.
        This provides a complete audit trail of all browser actions.
        
        Args:
            tool_name: Name of the tool that was called
            tool_args: Arguments passed to the tool
            run_timestamp: Optional timestamp (uses current_run_timestamp if not provided)
        """
        # Use provided timestamp or current run timestamp
        timestamp = run_timestamp or self.current_run_timestamp
        if not timestamp:
            print("Warning: No run timestamp set. Call start_new_run() first.")
            return
        
        # Use current website or "unknown" if not set
        website = self.current_website or "unknown"
        
        # Ensure the website exists in action logs
        if website not in self.action_logs:
            self.action_logs[website] = {}
        
        # Ensure the run timestamp exists under this website as an array
        if timestamp not in self.action_logs[website]:
            self.action_logs[website][timestamp] = []
        
        # Record the tool call (just tool name and args)
        tool_call_record = {
            "tool": tool_name,
            "args": tool_args
        }
        
        self.action_logs[website][timestamp].append(tool_call_record)
        
        # Save after each tool call to ensure we don't lose data
        try:
            with open(self.log_path, 'w') as f:
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
    
    def get_run_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current run's recorded tool calls.
        
        Returns:
            Dictionary with run statistics
        """
        if not self.current_run_timestamp:
            return {"error": "No active run"}
        
        website = self.current_website or "unknown"
        
        if (website in self.action_logs and 
            self.current_run_timestamp in self.action_logs[website]):
            tool_calls = self.action_logs[website][self.current_run_timestamp]
            return {
                "website": website,
                "timestamp": self.current_run_timestamp,
                "total_tool_calls": len(tool_calls),
                "tool_calls": tool_calls
            }
        
        return {
            "website": website,
            "timestamp": self.current_run_timestamp,
            "total_tool_calls": 0,
            "tool_calls": []
        }
    
    def print_run_summary(self):
        """
        Print a summary of the current run's recorded tool calls.
        """
        summary = self.get_run_summary()
        
        if "error" in summary:
            print(f"⚠️  {summary['error']}")
            return
        
        total = summary["total_tool_calls"]
        if total > 0:
            print(f"📝 Recorded {total} tool calls to {self.log_path}")
        else:
            print(f"📝 No tool calls recorded for this run")
