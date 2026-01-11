"""
Bookmaker Configuration Module

Handles bookmaker-specific configurations like URLs and search patterns.
"""

import urllib.parse


class BookmakerURLGenerator:
    """Generates bookmaker-specific URLs for betting markets."""
    
    @classmethod
    def generate_bookmaker_link(cls, bookmaker_key: str, sport: str, home_team: str, away_team: str) -> str:
        """
        Generate a Google search link for the specific game on the bookmaker's site.
        
        This is only used as a fallback when the Odds API doesn't provide a direct link.
        
        Args:
            bookmaker_key: The bookmaker identifier
            sport: Sport key
            home_team: Home team name
            away_team: Away team name
            
        Returns:
            Google search URL for the game on the bookmaker's site
        """
        # Clean up team names for search
        search_query = f"{away_team} {home_team}".replace(" @ ", " ")
        encoded_query = urllib.parse.quote(search_query)
        
        # Use Google search with bookmaker name as fallback
        # The Odds API should provide direct links in most cases
        return f'https://www.google.com/search?q={encoded_query}+{bookmaker_key}+betting'
