"""
ESPN API Scores Fetcher

Fetches real game results from ESPN's unofficial API.
Falls back to SerpAPI for sports not covered by ESPN.
"""

import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
import time
from pathlib import Path
import json


class ESPNScoresFetcher:
    """
    Fetch sports scores from ESPN API with SerpAPI fallback.
    """
    
    # Mapping of our sport keys to ESPN API endpoints
    ESPN_SPORT_MAP = {
        # American Football
        'americanfootball_nfl': ('football', 'nfl'),
        'americanfootball_nfl_preseason': ('football', 'nfl'),
        'americanfootball_ncaaf': ('football', 'college-football'),
        'americanfootball_cfl': ('football', 'cfl'),
        'americanfootball_ufl': ('football', 'ufl'),
        
        # Baseball
        'baseball_mlb': ('baseball', 'mlb'),
        'baseball_mlb_preseason': ('baseball', 'mlb'),
        'baseball_ncaa': ('baseball', 'college-baseball'),
        'baseball_npb': ('baseball', 'jpn.1'),  # Japan
        'baseball_kbo': ('baseball', 'kor.1'),  # Korea
        'baseball_milb': ('baseball', 'milb'),  # Minor League Baseball
        
        # Basketball
        'basketball_nba': ('basketball', 'nba'),
        'basketball_nba_preseason': ('basketball', 'nba'),
        'basketball_wnba': ('basketball', 'wnba'),
        'basketball_ncaab': ('basketball', 'mens-college-basketball'),
        'basketball_wncaab': ('basketball', 'womens-college-basketball'),
        'basketball_euroleague': ('basketball', 'euro'),
        'basketball_nbl': ('basketball', 'nbl'),  # Australia
        
        # Ice Hockey
        'icehockey_nhl': ('hockey', 'nhl'),
        'icehockey_nhl_preseason': ('hockey', 'nhl'),
        'icehockey_ahl': ('hockey', 'ahl'),
        'icehockey_sweden_hockey_league': ('hockey', 'swe.1'),
        'icehockey_sweden_allsvenskan': ('hockey', 'swe.2'),
        'icehockey_liiga': ('hockey', 'fin.1'),  # American Hockey League
        
        # Australian Rules Football
        'aussierules_afl': ('football', 'afl'),
        
        # Rugby League
        'rugbyleague_nrl': ('rugby-league', 'nrl'),
        
        # Rugby Union
        'rugbyunion_six_nations': ('rugby-union', 'six-nations'),
        
        # Soccer - Major Leagues
        'soccer_epl': ('soccer', 'eng.1'),  # English Premier League
        'soccer_efl_champ': ('soccer', 'eng.2'),  # Championship
        'soccer_england_league1': ('soccer', 'eng.3'),
        'soccer_england_league2': ('soccer', 'eng.4'),
        'soccer_spl': ('soccer', 'sco.1'),  # Scottish Premier League
        'soccer_germany_bundesliga': ('soccer', 'ger.1'),
        'soccer_germany_bundesliga2': ('soccer', 'ger.2'),
        'soccer_spain_la_liga': ('soccer', 'esp.1'),
        'soccer_spain_segunda_division': ('soccer', 'esp.2'),
        'soccer_italy_serie_a': ('soccer', 'ita.1'),
        'soccer_italy_serie_b': ('soccer', 'ita.2'),
        'soccer_france_ligue_one': ('soccer', 'fra.1'),
        'soccer_france_ligue_two': ('soccer', 'fra.2'),
        'soccer_netherlands_eredivisie': ('soccer', 'ned.1'),
        'soccer_portugal_primeira_liga': ('soccer', 'por.1'),
        'soccer_belgium_first_div': ('soccer', 'bel.1'),
        'soccer_turkey_super_league': ('soccer', 'tur.1'),
        'soccer_switzerland_superleague': ('soccer', 'sui.1'),
        'soccer_austria_bundesliga': ('soccer', 'aut.1'),
        'soccer_greece_super_league': ('soccer', 'gre.1'),
        'soccer_denmark_superliga': ('soccer', 'den.1'),
        'soccer_sweden_allsvenskan': ('soccer', 'swe.1'),
        'soccer_norway_eliteserien': ('soccer', 'nor.1'),
        'soccer_poland_ekstraklasa': ('soccer', 'pol.1'),
        'soccer_brazil_campeonato': ('soccer', 'bra.1'),
        'soccer_brazil_serie_b': ('soccer', 'bra.2'),
        'soccer_argentina_primera_division': ('soccer', 'arg.1'),
        'soccer_mexico_ligamx': ('soccer', 'mex.1'),
        'soccer_usa_mls': ('soccer', 'usa.1'),
        'soccer_australia_aleague': ('soccer', 'aus.1'),
        'soccer_japan_j_league': ('soccer', 'jpn.1'),
        'soccer_korea_kleague1': ('soccer', 'kor.1'),
        'soccer_china_superleague': ('soccer', 'chn.1'),
        'soccer_league_of_ireland': ('soccer', 'irl.1'),
        'soccer_sweden_superettan': ('soccer', 'swe.2'),
        'soccer_finland_veikkausliiga': ('soccer', 'fin.1'),
        
        # Soccer - Tournaments
        'soccer_uefa_champs_league': ('soccer', 'uefa.champions'),
        'soccer_uefa_europa_league': ('soccer', 'uefa.europa'),
        'soccer_uefa_europa_conference_league': ('soccer', 'uefa.europa.conf'),
        'soccer_uefa_nations_league': ('soccer', 'uefa.nations'),
        'soccer_fa_cup': ('soccer', 'eng.fa'),
        'soccer_england_efl_cup': ('soccer', 'eng.league_cup'),
        'soccer_fifa_world_cup': ('soccer', 'fifa.world'),
        'soccer_uefa_european_championship': ('soccer', 'uefa.euro'),
        'soccer_conmebol_copa_america': ('soccer', 'conmebol.america'),
        'soccer_conmebol_copa_libertadores': ('soccer', 'conmebol.libertadores'),
        'soccer_conmebol_copa_sudamericana': ('soccer', 'conmebol.sudamericana'),
        'soccer_concacaf_gold_cup': ('soccer', 'concacaf.gold'),
        'soccer_concacaf_leagues_cup': ('soccer', 'concacaf.leagues.cup'),
        'soccer_africa_cup_of_nations': ('soccer', 'caf.nations'),
        'soccer_fifa_world_cup_womens': ('soccer', 'fifa.wwc'),
        'soccer_fifa_club_world_cup': ('soccer', 'fifa.cwc'),
        'soccer_uefa_champs_league_women': ('soccer', 'uefa.champions.women'),
        
        # Tennis - Major Tournaments
        'tennis_atp_aus_open_singles': ('tennis', 'atp'),
        'tennis_atp_french_open': ('tennis', 'atp'),
        'tennis_atp_wimbledon': ('tennis', 'atp'),
        'tennis_atp_us_open': ('tennis', 'atp'),
        'tennis_wta_aus_open_singles': ('tennis', 'wta'),
        'tennis_wta_french_open': ('tennis', 'wta'),
        'tennis_wta_wimbledon': ('tennis', 'wta'),
        'tennis_wta_us_open': ('tennis', 'wta'),
        
        # MMA
        'mma_mixed_martial_arts': ('mma', 'ufc'),
        
        # Golf (limited)
        'golf_masters_tournament_winner': ('golf', 'pga'),
        'golf_pga_championship_winner': ('golf', 'pga'),
        'golf_us_open_winner': ('golf', 'pga'),
        'golf_the_open_championship_winner': ('golf', 'pga'),
    }
    
    def __init__(self, serpapi_fallback=None):
        """
        Initialize ESPN scores fetcher.
        
        Args:
            serpapi_fallback: Optional GoogleSearchScraper instance for fallback
        """
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports"
        self.serpapi_fallback = serpapi_fallback
        
        # Statistics
        self.stats = {
            'espn_requests': 0,
            'espn_successes': 0,
            'espn_failures': 0,
            'espn_matches': 0,  # Track actual game matches
            'serpapi_fallbacks': 0,
            'total_failures': 0,
            'cache_dir': Path('data/espn_cache')
        }
        
        # Create cache directory
        self.stats['cache_dir'].mkdir(exist_ok=True, parents=True)
        
    def _get_cache_path(self, sport: str, date: str) -> Path:
        """Get cache file path for a sport/date combination."""
        cache_key = f"{sport}_{date}.json"
        return self.stats['cache_dir'] / cache_key
    
    def _load_from_cache(self, sport: str, date: str) -> Optional[Dict]:
        """Load cached ESPN response."""
        cache_path = self._get_cache_path(sport, date)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return None
    
    def _save_to_cache(self, sport: str, date: str, data: Dict):
        """Save ESPN response to cache."""
        cache_path = self._get_cache_path(sport, date)
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"   ⚠️  Cache save error: {e}")
    
    def _fetch_espn_scores(self, sport: str, league: str, date: str) -> Optional[Dict]:
        """
        Fetch scores from ESPN API for a specific sport/league/date.
        
        Args:
            sport: ESPN sport category (e.g., 'football', 'basketball')
            league: ESPN league code (e.g., 'nfl', 'nba')
            date: Date string in YYYYMMDD format
            
        Returns:
            Dict with game data or None if failed
        """
        # Check cache first
        cache_key = f"{sport}_{league}"
        cached = self._load_from_cache(cache_key, date)
        if cached:
            return cached
        
        url = f"{self.base_url}/{sport}/{league}/scoreboard"
        params = {'dates': date}
        
        try:
            self.stats['espn_requests'] += 1
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            self.stats['espn_successes'] += 1
            
            # Cache the response
            self._save_to_cache(cache_key, date, data)
            
            return data
        except Exception as e:
            self.stats['espn_failures'] += 1
            return None
    
    def _parse_espn_result(self, game: Dict, target_teams: List[str], sport: str = '') -> Optional[Dict]:
        """
        Parse ESPN game data to extract result.
        
        Args:
            game: ESPN game object
            target_teams: List of team names we're looking for
            sport: Sport key for matching logic
            
        Returns:
            Dict with winner/scores or None
        """
        try:
            # Check if game is completed
            if game.get('status', {}).get('type', {}).get('completed') != True:
                return None
            
            competitions = game.get('competitions', [])
            if not competitions:
                return None
            
            competition = competitions[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) != 2:
                return None
            
            # Correctly identify home and away teams
            # ESPN marks homeAway as 'home' or 'away'
            home_team = None
            away_team = None
            home_score = 0
            away_score = 0
            
            for competitor in competitors:
                team_name = competitor.get('team', {}).get('displayName', '')
                score = float(competitor.get('score', 0))
                is_home = competitor.get('homeAway') == 'home'
                
                if is_home:
                    home_team = team_name
                    home_score = score
                else:
                    away_team = team_name
                    away_score = score
            
            if not home_team or not away_team:
                return None
            
            # Match team names (case-insensitive partial match)
            teams_found = [home_team.lower(), away_team.lower()]
            target_lower = [t.lower() for t in target_teams]
            
            # Build a simple matching function
            def teams_match(target: str, found: str) -> bool:
                """Check if target team/player matches found team/player."""
                # Normalize both strings
                target_norm = target.lower().strip()
                found_norm = found.lower().strip()
                
                # Exact match (after normalization)
                if target_norm == found_norm:
                    return True
                
                # Remove common prefixes/suffixes for comparison
                ignore_words = {'fc', 'sc', 'cf', 'ac', 'bk', 'the', 'afc', 'vs', '@', 'and', 'jk', 'de', 'el', 'la', 'united', 'city'}
                
                target_words = [w for w in target_norm.split() if len(w) > 2 and w not in ignore_words]
                found_words = [w for w in found_norm.split() if len(w) > 2 and w not in ignore_words]
                
                if not target_words or not found_words:
                    return False
                
                # Count how many words match exactly or as substrings
                matched_words = 0
                used_found_words = set()  # Track which found words we've matched to avoid double-matching
                
                for tw in target_words:
                    # Look for EXACT word match first (best)
                    if tw in found_words and tw not in used_found_words:
                        matched_words += 1
                        used_found_words.add(tw)
                    else:
                        # Allow substring match for longer words (handles variations)
                        for fw in found_words:
                            if fw in used_found_words:
                                continue
                            if len(tw) >= 5 and len(fw) >= 5:
                                # One is substring of other AND similar length
                                if (tw in fw or fw in tw) and abs(len(tw) - len(fw)) <= 3:
                                    matched_words += 1
                                    used_found_words.add(fw)
                                    break
                
                # Require ALL target words to match for strictness
                # This prevents false positives like "Manchester United" matching "Manchester City"
                return matched_words == len(target_words)
            
            # Try to match both target teams to the found teams
            matched = 0
            for target in target_lower:
                if any(teams_match(target, found) for found in teams_found):
                    matched += 1
            
            # Require at least one match for tennis (player names vary),
            # or both for team sports (more reliable)
            min_matches = 1 if 'tennis' in sport else 2
            
            if matched < min_matches:
                return None
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'completed': True,
                'source': 'espn'
            }
        except:
            return None
    
    def get_game_result(self, sport: str, team1: str, team2: str, 
                       game_date: datetime) -> Optional[Dict]:
        """
        Get game result, trying ESPN first then falling back to SerpAPI.
        
        Args:
            sport: Sport key (e.g., 'basketball_nba')
            team1: First team name
            team2: Second team name
            game_date: Game datetime
            
        Returns:
            Dict with game result or None
        """
        # Format date for ESPN API (YYYYMMDD)
        espn_date = game_date.strftime('%Y%m%d')
        
        # Check if ESPN supports this sport
        if sport in self.ESPN_SPORT_MAP:
            espn_sport, espn_league = self.ESPN_SPORT_MAP[sport]
            
            # Fetch ESPN data
            espn_data = self._fetch_espn_scores(espn_sport, espn_league, espn_date)
            
            if espn_data and 'events' in espn_data:
                # Search through games for our match
                for event in espn_data['events']:
                    result = self._parse_espn_result(event, [team1, team2], sport)
                    if result:
                        self.stats['espn_matches'] += 1
                        return result
        
        # ESPN didn't work or doesn't support this sport - try SerpAPI
        if self.serpapi_fallback:
            self.stats['serpapi_fallbacks'] += 1
            try:
                # Convert datetime to string format expected by SerpAPI
                game_date_str = game_date.strftime('%Y-%m-%d') if hasattr(game_date, 'strftime') else str(game_date)
                
                result = self.serpapi_fallback.get_game_result(
                    sport=sport,
                    away_team=team1,  # team1 is away, team2 is home
                    home_team=team2,
                    game_date=game_date_str
                )
                if result:
                    result['source'] = 'serpapi'
                    return result
            except Exception as e:
                pass
        
        self.stats['total_failures'] += 1
        return None
    
    def print_stats(self):
        """Print usage statistics."""
        print(f"\n{'='*80}")
        print(f"ESPN/SERPAPI USAGE STATISTICS")
        print(f"{'='*80}")
        print(f"ESPN API:")
        print(f"  Requests: {self.stats['espn_requests']}")
        print(f"  Successes: {self.stats['espn_successes']}")
        print(f"  Failures: {self.stats['espn_failures']}")
        print(f"\nSerpAPI Fallbacks: {self.stats['serpapi_fallbacks']}")
        print(f"Total Failures: {self.stats['total_failures']}")
        
        if self.stats['espn_requests'] > 0:
            success_rate = (self.stats['espn_successes'] / self.stats['espn_requests']) * 100
            print(f"\nESPN Success Rate: {success_rate:.1f}%")
        
        # Calculate actual ESPN match rate (successes that returned a match)
        espn_matches = self.stats.get('espn_matches', 0)
        if self.stats['espn_successes'] > 0:
            match_rate = (espn_matches / self.stats['espn_successes']) * 100
            print(f"ESPN Match Rate: {match_rate:.1f}% ({espn_matches} games matched out of {self.stats['espn_successes']} successful API calls)")
        
        print(f"{'='*80}\n")
