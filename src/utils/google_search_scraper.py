#!/usr/bin/env python3
"""
SerpAPI Sports Results integration for fetching sports scores.

This module provides a clean interface to SerpAPI's Google Sports Results API
for looking up historical sports game results.
"""

import os
import requests
import re
from typing import Optional, Tuple, Dict, List
from datetime import datetime
import time
from pathlib import Path
import json


class GoogleSearchScraper:
    """Fetches sports scores using SerpAPI Google Sports Results API."""
    
    def __init__(self, api_key: Optional[str] = None, search_engine_id: Optional[str] = None,
                 cache_dir: str = 'data/serpapi_cache'):
        """
        Initialize SerpAPI scraper.
        
        Args:
            api_key: SerpAPI API key (or set SERPAPI_KEY env var)
            search_engine_id: Deprecated (kept for backward compatibility)
            cache_dir: Directory to cache search results
        """
        # Try SerpAPI key first, fall back to old Google key for migration
        self.api_key = api_key or os.getenv('SERPAPI_KEY') or os.getenv('GOOGLE_SEARCH_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "SerpAPI key required. Set SERPAPI_KEY environment variable "
                "or pass api_key parameter. Get your key at: "
                "https://serpapi.com/manage-api-key (100 free searches/month)"
            )
        
        self.base_url = "https://serpapi.com/search.json"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 10 requests per second max
        
        # Statistics
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'successful_parses': 0,
            'failed_parses': 0
        }
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for a search query."""
        import hashlib
        return hashlib.md5(query.encode()).hexdigest()
    
    def _get_game_cache_key(self, away_team: str, home_team: str, game_date: str) -> str:
        """
        Generate a normalized cache key for a game based on teams and date.
        This ensures cache hits regardless of query format variations.
        
        Args:
            away_team: Away team name
            home_team: Home team name
            game_date: Game date in ISO format (YYYY-MM-DD or ISO timestamp)
        
        Returns:
            MD5 hash of normalized game identifier
        """
        import hashlib
        
        # Normalize date to YYYY-MM-DD format
        try:
            if 'T' in game_date or 'Z' in game_date:
                # ISO timestamp format
                date_obj = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
            else:
                # Already in YYYY-MM-DD format
                date_obj = datetime.strptime(game_date[:10], '%Y-%m-%d')
            normalized_date = date_obj.strftime('%Y-%m-%d')
        except:
            # Fallback: use first 10 chars
            normalized_date = game_date[:10]
        
        # Normalize team names (lowercase, strip whitespace)
        team1 = away_team.lower().strip()
        team2 = home_team.lower().strip()
        
        # Sort teams alphabetically to handle order variations
        teams = sorted([team1, team2])
        
        # Create normalized key: date_team1_team2
        normalized_key = f"{normalized_date}_{teams[0]}_{teams[1]}_serpapi"
        
        return hashlib.md5(normalized_key.encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Load search result from cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict):
        """Save search result to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save to cache: {e}")
    
    def _rate_limit(self):
        """Enforce rate limiting between API requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def search_sports_score(self, query: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Search for sports scores using SerpAPI's Google Sports Results API.
        This uses SerpAPI to extract structured score data from Google's score boxes.
        
        Args:
            query: Search query string
            use_cache: Whether to use cached results
            
        Returns:
            SerpAPI response with sports_results containing structured score data
        """
        cache_key = self._get_cache_key(query + "_serpapi")
        
        if use_cache:
            cached_result = self._load_from_cache(cache_key)
            if cached_result:
                self.stats['cache_hits'] += 1
                return cached_result
        
        self._rate_limit()
        
        # SerpAPI parameters for Google Sports Results
        params = {
            'api_key': self.api_key,
            'engine': 'google',
            'q': query,
            'location': 'United States',
            'gl': 'us',
            'hl': 'en',
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            self.stats['api_calls'] += 1
            
            # Save to cache
            if use_cache:
                self._save_to_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            print(f"⚠️  SerpAPI error: {e}")
            return None

    def search(self, query: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Perform Google search via SerpAPI and return raw results.
        
        Args:
            query: Search query string
            use_cache: Whether to use cached results
            
        Returns:
            SerpAPI response dict or None if error
        """
        # Use sports-specific search
        return self.search_sports_score(query, use_cache)
    
    def parse_score_from_results(self, search_results: Dict, away_team: str, home_team: str) -> Optional[Tuple[int, int, str]]:
        """
        Parse score from SerpAPI sports results.
        
        Args:
            search_results: SerpAPI response with sports_results
            away_team: Away team name
            home_team: Home team name
            
        Returns:
            Tuple of (away_score, home_score, winner) or None if not found
        """
        if not search_results:
            return None
        
        # SerpAPI returns structured sports data in sports_results
        sports_results = search_results.get('sports_results', {})
        
        # Try game_spotlight first (live/recent games)
        game_spotlight = sports_results.get('game_spotlight', {})
        if game_spotlight and 'teams' in game_spotlight:
            score = self._extract_score_from_teams(game_spotlight['teams'], away_team, home_team)
            if score:
                return score
        
        # Try games list (scheduled/recent games)
        games = sports_results.get('games', [])
        for game in games:
            if 'teams' in game:
                score = self._extract_score_from_teams(game['teams'], away_team, home_team)
                if score:
                    return score
        
        # Fallback: Try to parse from organic_results (for less popular leagues)
        organic_results = search_results.get('organic_results', [])
        if organic_results:
            score = self._parse_score_from_organic_results(organic_results, away_team, home_team)
            if score:
                return score
        
        return None
    
    def _extract_score_from_teams(self, teams: List[Dict], away_team: str, home_team: str) -> Optional[Tuple[int, int, str]]:
        """
        Extract scores from SerpAPI teams data.
        
        Args:
            teams: List of team dicts with name and score
            away_team: Away team name to match
            home_team: Home team name to match
            
        Returns:
            Tuple of (away_score, home_score, winner) or None
        """
        if len(teams) != 2:
            return None
        
        team1 = teams[0]
        team2 = teams[1]
        
        # Get team names
        team1_name = team1.get('name', '')
        team2_name = team2.get('name', '')
        
        # Get scores (could be string or dict with 'total')
        team1_score_data = team1.get('score')
        team2_score_data = team2.get('score')
        
        # Extract numeric scores
        team1_score = self._parse_score_value(team1_score_data)
        team2_score = self._parse_score_value(team2_score_data)
        
        if team1_score is None or team2_score is None:
            return None
        
        # Match team names (fuzzy matching)
        team1_is_away = self._team_matches(team1_name, away_team)
        team1_is_home = self._team_matches(team1_name, home_team)
        team2_is_away = self._team_matches(team2_name, away_team)
        team2_is_home = self._team_matches(team2_name, home_team)
        
        # Determine which team is which
        if team1_is_away and team2_is_home:
            away_score, home_score = team1_score, team2_score
        elif team1_is_home and team2_is_away:
            away_score, home_score = team2_score, team1_score
        else:
            # Can't match teams reliably, assume team1 is away
            away_score, home_score = team1_score, team2_score
        
        # Determine winner
        if away_score > home_score:
            winner = away_team
        elif home_score > away_score:
            winner = home_team
        else:
            winner = "Draw"
        
        return (away_score, home_score, winner)
    
    def _parse_score_value(self, score_data) -> Optional[int]:
        """Parse score value from various formats."""
        if score_data is None:
            return None
        
        if isinstance(score_data, (int, float)):
            return int(score_data)
        
        if isinstance(score_data, str):
            try:
                return int(score_data)
            except ValueError:
                return None
        
        # Dict format with 'total' key (NBA/NFL quarters)
        if isinstance(score_data, dict):
            # Try 'T' for total first (NFL/NBA format)
            if 'T' in score_data:
                try:
                    return int(score_data['T'])
                except (ValueError, TypeError):
                    pass
            # Try 'total' key
            if 'total' in score_data:
                try:
                    return int(score_data['total'])
                except (ValueError, TypeError):
                    pass
        
        return None
    
    def _team_matches(self, team_name1: str, team_name2: str) -> bool:
        """Check if two team names match (case-insensitive, partial match)."""
        if not team_name1 or not team_name2:
            return False
        
        name1 = team_name1.lower().strip()
        name2 = team_name2.lower().strip()
        
        # Exact match
        if name1 == name2:
            return True
        
        # Partial match (one contains the other)
        if name1 in name2 or name2 in name1:
            return True
        
        # Common abbreviations (e.g., "Man United" vs "Manchester United")
        # Remove common words
        common_words = {'fc', 'f.c.', 'united', 'city', 'the', 'a'}
        words1 = set(name1.split()) - common_words
        words2 = set(name2.split()) - common_words
        
        # If any significant words match
        if words1 & words2:
            return True
        
        return False
    
    def _parse_score_from_organic_results(self, organic_results: List[Dict], away_team: str, home_team: str) -> Optional[Tuple[int, int, str]]:
        """
        Parse score from organic search results (fallback for non-structured data).
        
        Args:
            organic_results: List of organic search results
            away_team: Away team name
            home_team: Home team name
            
        Returns:
            Tuple of (away_score, home_score, winner) or None if not found
        """
        import re
        
        # Common score patterns in titles/snippets
        # Pattern 1: "Team1 8, Team2 1" or "Team1 8 - Team2 1"
        # Pattern 2: "Team1 defeats Team2 11-5" or "Team1 11, Team2 5"
        score_patterns = [
            r'(\d+)\s*[-,]\s*(\d+)',  # "8-1" or "8, 1"
            r'(\d+)\s+Final\s+(\d+)',  # "8 Final 1"
            r'defeat(?:ed|s?).*?(\d+)\s*[-,]\s*(\d+)',  # "defeated ... 11-5"
        ]
        
        for result in organic_results[:5]:  # Check first 5 results
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            text = f"{title} {snippet}"
            
            # Try to find both team names in the text
            has_away = any(self._team_matches(word, away_team) for word in text.split())
            has_home = any(self._team_matches(word, home_team) for word in text.split())
            
            if not (has_away or has_home):
                continue
            
            # Try to extract score
            for pattern in score_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    try:
                        # Get first score match
                        score1, score2 = int(matches[0][0]), int(matches[0][1])
                        
                        # Determine which team is which based on text position
                        # Check if away team appears before home team in text
                        away_pos = min([text.lower().find(word.lower()) for word in away_team.split() if word.lower() in text.lower()] + [999999])
                        home_pos = min([text.lower().find(word.lower()) for word in home_team.split() if word.lower() in text.lower()] + [999999])
                        
                        if away_pos < home_pos:
                            away_score, home_score = score1, score2
                        else:
                            away_score, home_score = score2, score1
                        
                        # Determine winner
                        if away_score > home_score:
                            winner = away_team
                        elif home_score > away_score:
                            winner = home_team
                        else:
                            winner = "Draw"
                        
                        return (away_score, home_score, winner)
                    except (ValueError, IndexError):
                        continue
        
        return None

    def get_game_result(self, sport: str, away_team: str, home_team: str, 
                       game_date: str) -> Optional[Dict]:
        """
        Get game result by searching Google via SerpAPI.
        Uses normalized cache keys to ensure cache hits across query variations.
        
        Args:
            sport: Sport name (e.g., "NFL", "NBA", "Premier League")
            away_team: Away team name
            home_team: Home team name
            game_date: Game date (YYYY-MM-DD format or ISO timestamp)
            
        Returns:
            Dict with keys: away_score, home_score, winner, source, query
            Or None if not found
        """
        # Generate normalized cache key for this game
        game_cache_key = self._get_game_cache_key(away_team, home_team, game_date)
        
        # Check normalized cache first
        cached_result = self._load_from_cache(game_cache_key)
        if cached_result:
            self.stats['cache_hits'] += 1
            parsed_score = self.parse_score_from_results(cached_result, away_team, home_team)
            
            if parsed_score:
                away_score, home_score, winner = parsed_score
                self.stats['successful_parses'] += 1
                
                return {
                    'away_score': away_score,
                    'home_score': home_score,
                    'winner': winner,
                    'source': 'serpapi',
                    'query': 'cached'
                }
        
        # Format the search query with exact dates
        # Try multiple query formats to maximize chances of finding scores
        try:
            date_obj = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
            date_full = date_obj.strftime("%d %B %Y")  # "01 January 2025"
            date_short = date_obj.strftime("%B %d, %Y")  # "January 01, 2025"
            date_iso = date_obj.strftime("%Y-%m-%d")  # "2025-01-01"
        except:
            date_full = game_date[:10]
            date_short = game_date[:10]
            date_iso = game_date[:10]
        
        # Try multiple query variations - all with exact dates for better precision
        queries = [
            f"{away_team} vs {home_team} {date_short} score",
            f"{home_team} vs {away_team} {date_short} final score",
            f"{home_team} {away_team} {date_full} score",
            f"{away_team} {home_team} score {date_iso}",
            f"{sport} {away_team} vs {home_team} {date_short}",
        ]
        
        # First: Check old cache files for any of these query variations (no API calls)
        for query in queries:
            old_cache_key = self._get_cache_key(query + "_serpapi")
            cached_result = self._load_from_cache(old_cache_key)
            
            if cached_result:
                self.stats['cache_hits'] += 1
                parsed_score = self.parse_score_from_results(cached_result, away_team, home_team)
                
                if parsed_score:
                    away_score, home_score, winner = parsed_score
                    self.stats['successful_parses'] += 1
                    
                    # Save to normalized cache for next time
                    self._save_to_cache(game_cache_key, cached_result)
                    
                    return {
                        'away_score': away_score,
                        'home_score': home_score,
                        'winner': winner,
                        'source': 'serpapi',
                        'query': f'cached:{query}'
                    }
        
        # Second: If not in any cache, try API calls (only if needed)
        for query in queries:
            # Make API call
            search_results = self.search_sports_score(query, use_cache=False)
            
            if not search_results:
                continue
            
            # Parse score from results
            parsed_score = self.parse_score_from_results(search_results, away_team, home_team)
            
            if parsed_score:
                away_score, home_score, winner = parsed_score
                self.stats['successful_parses'] += 1
                
                # Save to normalized cache key for future lookups
                self._save_to_cache(game_cache_key, search_results)
                
                return {
                    'away_score': away_score,
                    'home_score': home_score,
                    'winner': winner,
                    'source': 'serpapi',
                    'query': query
                }
        
        # If all queries failed
        self.stats['failed_parses'] += 1
        return None
    
    def print_stats(self):
        """Print usage statistics."""
        print(f"\n📊 SerpAPI Statistics:")
        print(f"   Total queries: {self.stats['total_queries']}")
        print(f"   Cache hits: {self.stats['cache_hits']}")
        print(f"   API calls: {self.stats['api_calls']}")
        print(f"   Successful parses: {self.stats['successful_parses']}")
        print(f"   Failed parses: {self.stats['failed_parses']}")
        if self.stats['successful_parses'] + self.stats['failed_parses'] > 0:
            success_rate = (self.stats['successful_parses'] / (self.stats['successful_parses'] + self.stats['failed_parses'])) * 100
            print(f"   Success rate: {success_rate:.1f}%")
        if self.stats['api_calls'] > 0:
            # SerpAPI pricing: $50/month for 5000 searches or $0.01/search
            print(f"   Searches used: {self.stats['api_calls']} (100 free/month included)")
