"""
Bookmaker Configuration Module

Handles bookmaker-specific configurations like URLs and search patterns.
"""

import urllib.parse


class BookmakerURLGenerator:
    """Generates bookmaker-specific URLs for betting markets."""
    
    # Bookmaker search URL templates
    SEARCH_URLS = {
        'williamhill': 'https://sports.williamhill.com/betting/en-gb/football?q={query}',
        'ladbrokes_uk': 'https://sports.ladbrokes.com/en-gb/betting/football?q={query}',
        'coral': 'https://sports.coral.co.uk/en-gb/betting/football?q={query}',
        'paddypower': 'https://www.paddypower.com/football?q={query}',
        'skybet': 'https://m.skybet.com/football?search={query}',
        'betway': 'https://betway.com/en-gb/sports/evt/{query}',
        'betvictor': 'https://www.betvictor.com/en-gb/sports/football?q={query}',
        'unibet_uk': 'https://www.unibet.co.uk/betting/sports/filter/all/all/all?search={query}',
        'betfred': 'https://www.betfred.com/sport/football?q={query}',
        'sport888': 'https://www.888sport.com/football?q={query}'
    }
    
    # Bookmaker site domains for fallback Google search
    SITE_DOMAINS = {
        'williamhill': 'sports.williamhill.com',
        'ladbrokes_uk': 'sports.ladbrokes.com',
        'coral': 'sports.coral.co.uk',
        'paddypower': 'paddypower.com',
        'skybet': 'skybet.com',
        'betway': 'betway.com',
        'betvictor': 'betvictor.com',
        'unibet_uk': 'unibet.co.uk',
        'betfred': 'betfred.com',
        'sport888': '888sport.com'
    }
    
    @classmethod
    def generate_bookmaker_link(cls, bookmaker_key: str, sport: str, home_team: str, away_team: str) -> str:
        """
        Generate a search link for the specific game on the bookmaker's site.
        
        Since exact match URLs require game IDs that aren't provided by the API,
        we create a search query that will take you directly to the match.
        
        Args:
            bookmaker_key: The bookmaker identifier
            sport: Sport key
            home_team: Home team name
            away_team: Away team name
            
        Returns:
            Search URL for the specific game
        """
        # Clean up team names for search
        search_query = f"{away_team} {home_team}".replace(" @ ", " ")
        encoded_query = urllib.parse.quote(search_query)
        
        # If bookmaker has a search URL template, use it
        if bookmaker_key in cls.SEARCH_URLS:
            return cls.SEARCH_URLS[bookmaker_key].format(query=encoded_query)
        else:
            # Fallback: Google search for the game on that bookmaker's site
            domain = cls.SITE_DOMAINS.get(bookmaker_key, bookmaker_key)
            return f'https://www.google.com/search?q={encoded_query}+site:{domain}'
