"""
Configuration Management Module

Handles loading and validation of configuration from environment variables.
"""

import os
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class BookmakerCredentials:
    """Manages bookmaker credentials from environment variables."""
    
    @staticmethod
    def get_credentials(bookmaker_key: str) -> Dict[str, str]:
        """
        Get username and password for a specific bookmaker from environment variables.
        
        Args:
            bookmaker_key: The bookmaker key (e.g., 'bet365', 'williamhill')
            
        Returns:
            Dictionary with 'username' and 'password' keys
            
        Raises:
            ValueError: If credentials are not found
        """
        # Convert bookmaker key to uppercase for env var lookup
        env_prefix = bookmaker_key.upper()
        
        username = os.getenv(f'{env_prefix}_USERNAME')
        password = os.getenv(f'{env_prefix}_PASSWORD')
        
        if not username or not password:
            raise ValueError(
                f"Credentials not found for {bookmaker_key}. "
                f"Please set {env_prefix}_USERNAME and {env_prefix}_PASSWORD in .env file"
            )
        
        return {
            'username': username,
            'password': password
        }
    
    @staticmethod
    def get_available_bookmakers() -> List[str]:
        """
        Auto-detect bookmakers that have credentials configured.
        
        Returns:
            List of bookmaker keys that have both username and password set
        """
        # List of all possible bookmakers from Odds API
        all_bookmakers = [
            # US Bookmakers
            'betanysports', 'betmgm', 'betonlineag', 'betrivers', 'betus', 'bovada',
            'draftkings', 'everygame', 'fanatics', 'fanduel', 'gtbets', 'lowvig',
            'mybookieag', 'williamhill_us',
            # UK Bookmakers
            'betfair_ex_uk', 'betfair_sb_uk', 'betvictor', 'betway', 'boylesports',
            'coral', 'grosvenor', 'ladbrokes_uk', 'livescorebet', 'paddypower',
            'skybet', 'unibet_uk', 'virginbet', 'williamhill',
            # EU Bookmakers
            'betclic_fr', 'betfair_ex_eu', 'betsson', 'casumo', 'codere_it',
            'coolbet', 'leovegas', 'leovegas_se', 'marathonbet', 'matchbook',
            'nordicbet', 'onexbet', 'parionssport_fr', 'pinnacle', 'pmu_fr',
            'smarkets', 'sport888', 'tipico_de', 'unibet', 'unibet_fr',
            'unibet_nl', 'unibet_se', 'winamax_de', 'winamax_fr',
            # AU Bookmakers
            'betfair_ex_au', 'betr_au', 'betright', 'boombet', 'dabble_au',
            'ladbrokes_au', 'neds', 'playup', 'pointsbetau', 'sportsbet',
            'tab', 'tabtouch'
        ]
        
        available_bookmakers = []
        
        for bookmaker_key in all_bookmakers:
            env_prefix = bookmaker_key.upper()
            username = os.getenv(f'{env_prefix}_USERNAME')
            password = os.getenv(f'{env_prefix}_PASSWORD')
            
            if username and password:
                available_bookmakers.append(bookmaker_key)
        
        return available_bookmakers
    
    @staticmethod
    def validate_bookmaker_credentials(bookmaker_keys: List[str]) -> None:
        """
        Validate that all bookmakers have credentials configured.
        
        Args:
            bookmaker_keys: List of bookmaker keys to validate
            
        Raises:
            ValueError: If any bookmaker is missing credentials
        """
        if not bookmaker_keys:
            return  # No bookmakers to validate
        
        missing_credentials = []
        
        for bookmaker_key in bookmaker_keys:
            env_prefix = bookmaker_key.upper()
            username = os.getenv(f'{env_prefix}_USERNAME')
            password = os.getenv(f'{env_prefix}_PASSWORD')
            
            if not username or not password:
                missing_credentials.append(bookmaker_key)
        
        if missing_credentials:
            error_msg = (
                f"Missing credentials for bookmaker(s): {', '.join(missing_credentials)}\n"
                f"Please set the following environment variables in your .env file:\n"
            )
            for bookmaker in missing_credentials:
                env_prefix = bookmaker.upper()
                error_msg += f"  - {env_prefix}_USERNAME\n"
                error_msg += f"  - {env_prefix}_PASSWORD\n"
            raise ValueError(error_msg)
