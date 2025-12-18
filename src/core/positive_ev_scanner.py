"""
Positive EV Sports Betting Opportunity Scanner

Uses The Odds API to find positive expected value betting opportunities
by comparing odds across multiple sportsbooks against sharp bookmakers.
"""

import requests
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
import time
import os
import pickle
from pathlib import Path
from dotenv import load_dotenv
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.core.kelly_criterion import KellyCriterion
from src.utils.bet_logger import BetLogger
from src.utils.bet_repository import BetRepository
from src.utils.odds_utils import decimal_to_fractional, calculate_implied_probability, calculate_ev
from src.utils.bookmaker_config import BookmakerURLGenerator
from src.utils.config import BookmakerCredentials

# Load environment variables from .env file
load_dotenv()


class PositiveEVScanner:
    """
    Scanner to identify positive expected value betting opportunities
    by comparing odds across sportsbooks.
    """
    
    def __init__(self, api_key: str = None, log_path: str = None):
        """
        Initialize the scanner with The Odds API key.
        
        Args:
            api_key: Your The Odds API key (optional, will read from .env if not provided)
            log_path: Path to bet history CSV (optional, defaults to data/bet_history.csv)
        """
        # Read from environment variables if not provided
        self.api_key = api_key or os.getenv('ODDS_API_KEY')
        if not self.api_key:
            raise ValueError("ODDS_API_KEY must be provided or set in .env file")
        
        self.base_url = "https://api.the-odds-api.com/v4"
        
        # Sharp bookmakers - read from env or use defaults
        sharp_books_str = os.getenv('SHARP_BOOKS', 'pinnacle,betfair_ex_uk,betfair_ex_eu,betfair_ex_au,matchbook,smarkets')
        self.sharp_books = [book.strip() for book in sharp_books_str.split(',')]
        
        # Betting bookmakers - auto-detect from credentials
        self.betting_bookmakers = BookmakerCredentials.get_available_bookmakers()
        if not self.betting_bookmakers:
            print("⚠️  Warning: No bookmaker credentials found. Please add credentials to .env file.")
        
        # Minimum EV threshold - read from env or use default
        self.min_ev_threshold = float(os.getenv('MIN_EV_THRESHOLD', '0.02'))
        
        # Minimum true probability threshold - read from env or use default (0.0 = no filter)
        self.min_true_probability = float(os.getenv('MIN_TRUE_PROBABILITY', '0.0'))
        
        # Minimum Kelly percentage threshold - read from env or use default (0.0 = no filter)
        self.min_kelly_percentage = float(os.getenv('MIN_KELLY_PERCENTAGE', '0.0'))
        
        # Maximum odds threshold - read from env or use default (0.0 = no filter)
        self.max_odds = float(os.getenv('MAX_ODDS', '0.0'))
        
        # Maximum days ahead filter - read from env or use default (0 = no filter)
        self.max_days_ahead = float(os.getenv('MAX_DAYS_AHEAD', '0'))
        
        # API regions - read from env or use default
        self.api_regions = os.getenv('API_REGIONS', 'us,uk,eu,au')
        
        # Markets - read from env or use default
        self.markets = os.getenv('MARKETS', 'h2h,spreads,totals')
        
        # Odds format - hardcoded to decimal for EV calculations
        self.odds_format = 'decimal'
        
        # Kelly fraction - read from env or use default
        self.kelly_fraction = float(os.getenv('KELLY_FRACTION', '1.0'))
        
        # Initialize Kelly Criterion calculator
        self.kelly = KellyCriterion()
        
        # Initialize bet logger and repository with custom log path if provided
        if log_path:
            self.bet_logger = BetLogger(log_path=log_path)
            self.bet_repository = BetRepository(log_path=log_path)
        else:
            self.bet_logger = BetLogger()
            self.bet_repository = BetRepository()
        
        # Build optimized bookmakers list (your betting bookmakers + sharp books)
        self.optimized_bookmakers = list(set(self.betting_bookmakers + self.sharp_books))
        
        # Persistent file-based caching for odds data (30 minute cache)
        self._cache_file = Path('data/.odds_cache.pkl')
        self._cache_file.parent.mkdir(exist_ok=True)
        self._cache_duration = 60  # 1 minute in seconds
        self._odds_cache = self._load_cache()
        
        # Concurrent request settings
        # 10 concurrent workers - aggressive but safe based on API rate limiting
        # The API uses burst protection (429 status) rather than hard limits
        # If you hit 429 errors, the requests module will automatically handle retries
        self.max_concurrent_requests = 10
        
        # Sorting configuration - read from env or use defaults
        self.order_by = os.getenv('ORDER_BY', 'expected_profit').lower()
        self.sort_order = os.getenv('SORT_ORDER', 'desc').lower()
        
        # Filtering configuration - read from env or use defaults
        self.one_bet_per_game = os.getenv('ONE_BET_PER_GAME', 'false').lower() == 'true'
        self.skip_already_bet_games = os.getenv('SKIP_ALREADY_BET_GAMES', 'true').lower() == 'true'
        self.max_bet_failures = int(os.getenv('MAX_BET_FAILURES', '3'))
        
    def _load_cache(self) -> Dict:
        """Load cache from disk if it exists and is valid."""
        try:
            if self._cache_file.exists():
                with open(self._cache_file, 'rb') as f:
                    cache = pickle.load(f)
                # Clean up expired entries
                current_time = time.time()
                cache = {k: v for k, v in cache.items() 
                        if current_time - v[1] < self._cache_duration}
                if cache:
                    print(f"📦 Loaded {len(cache)} cached sport(s) from disk")
                return cache
        except Exception as e:
            print(f"⚠️  Could not load cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self._cache_file, 'wb') as f:
                pickle.dump(self._odds_cache, f)
        except Exception as e:
            print(f"⚠️  Could not save cache: {e}")
    
    def get_available_sports(self) -> List[Dict]:
        """
        Get list of available sports.
        
        Returns:
            List of available sports
        """
        url = f"{self.base_url}/sports"
        params = {
            'apiKey': self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching sports: {e}")
            return []
    
    def get_events(self, sport: str) -> List[Dict]:
        """
        Get list of upcoming events for a sport (FREE - doesn't count against quota).
        Use this to check if events exist before calling get_odds().
        
        Args:
            sport: Sport key (e.g., 'soccer_epl')
            
        Returns:
            List of events (without odds)
        """
        url = f"{self.base_url}/sports/{sport}/events"
        params = {
            'apiKey': self.api_key,
            'dateFormat': 'iso'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching events for {sport}: {e}")
            return []
    
    def get_odds(self, sport: str, markets: str = 'h2h') -> List[Dict]:
        """
        Get odds for a specific sport with caching and optimization.
        Handles invalid markets gracefully by retrying with valid markets only.
        
        Args:
            sport: Sport key (e.g., 'americanfootball_nfl')
            markets: Comma-separated markets (h2h, spreads, totals)
            
        Returns:
            List of games with odds from multiple bookmakers
        """
        # Check cache first (30 minute cache)
        cache_key = f"{sport}_{markets}"
        current_time = time.time()
        
        if cache_key in self._odds_cache:
            cached_data, cache_time = self._odds_cache[cache_key]
            if current_time - cache_time < self._cache_duration:
                cache_age_minutes = int((current_time - cache_time) / 60)
                print(f"💾 Using cached odds for {sport} (cached {cache_age_minutes}m ago)")
                return cached_data
        
        url = f"{self.base_url}/sports/{sport}/odds"
        
        # Use specific bookmakers for better control
        # Up to 10 bookmakers = 1 region equivalent
        params = {
            'apiKey': self.api_key,
            'bookmakers': ','.join(self.optimized_bookmakers),
            'markets': markets,
            'oddsFormat': self.odds_format,
            'dateFormat': 'iso'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # Print remaining requests and usage info
            remaining = response.headers.get('x-requests-remaining')
            used = response.headers.get('x-requests-used')
            last_cost = response.headers.get('x-requests-last')
            
            if remaining:
                print(f"📊 API Usage - Remaining: {remaining}, Used: {used}, Last Cost: {last_cost}")
            
            data = response.json()
            
            # Cache the result in memory and persist to disk
            self._odds_cache[cache_key] = (data, current_time)
            self._save_cache()
            
            return data
        except requests.exceptions.HTTPError as e:
            # Handle 422 error (invalid market for sport) by retrying with valid markets
            if e.response.status_code == 422:
                market_list = [m.strip() for m in markets.split(',')]
                if len(market_list) > 1:
                    print(f"⚠️  Some markets not available for {sport}, trying individual markets...")
                    
                    # Try each market individually
                    all_games = []
                    successful_markets = []
                    
                    for market in market_list:
                        try:
                            params['markets'] = market
                            response = requests.get(url, params=params)
                            response.raise_for_status()
                            
                            games = response.json()
                            if games:
                                # Merge games data (avoiding duplicates by game ID)
                                if not all_games:
                                    all_games = games
                                    successful_markets.append(market)
                                else:
                                    # Merge bookmaker data for existing games
                                    game_dict = {g['id']: g for g in all_games}
                                    for game in games:
                                        if game['id'] in game_dict:
                                            # Merge bookmakers for this game
                                            existing_game = game_dict[game['id']]
                                            for bookmaker in game.get('bookmakers', []):
                                                # Check if this bookmaker already exists
                                                existing_bookmaker = next(
                                                    (b for b in existing_game.get('bookmakers', []) 
                                                     if b['key'] == bookmaker['key']),
                                                    None
                                                )
                                                if existing_bookmaker:
                                                    # Merge markets
                                                    existing_bookmaker['markets'].extend(bookmaker.get('markets', []))
                                                else:
                                                    # Add new bookmaker
                                                    existing_game.setdefault('bookmakers', []).append(bookmaker)
                                        else:
                                            # Add new game
                                            all_games.append(game)
                                            game_dict[game['id']] = game
                                    successful_markets.append(market)
                        except requests.exceptions.HTTPError as market_error:
                            if market_error.response.status_code == 422:
                                print(f"   ⊗ Market '{market}' not available for {sport}")
                            else:
                                print(f"   ⚠️  Error fetching market '{market}': {market_error}")
                        except Exception as market_error:
                            print(f"   ⚠️  Error fetching market '{market}': {market_error}")
                    
                    if all_games:
                        if successful_markets:
                            print(f"   ✓ Successfully fetched markets: {', '.join(successful_markets)}")
                        
                        # Cache with successful markets only
                        success_cache_key = f"{sport}_{'_'.join(successful_markets)}"
                        self._odds_cache[success_cache_key] = (all_games, current_time)
                        self._save_cache()
                        
                        return all_games
                    else:
                        print(f"⚠️  No valid markets available for {sport}")
                        return []
                else:
                    print(f"⚠️  Market '{markets}' not available for {sport}")
                    return []
            else:
                print(f"Error fetching odds for {sport}: {e}")
                return []
        except Exception as e:
            print(f"Error fetching odds for {sport}: {e}")
            return []
    
    # Backward compatibility: delegate to utility functions
    def calculate_implied_probability(self, decimal_odds: float) -> float:
        """Calculate implied probability from decimal odds (delegates to odds_utils)."""
        return calculate_implied_probability(decimal_odds)
    
    def decimal_to_fractional(self, decimal_odds: float) -> str:
        """Convert decimal odds to fractional (delegates to odds_utils)."""
        return decimal_to_fractional(decimal_odds)
    
    def calculate_ev(self, bet_odds: float, true_probability: float) -> float:
        """Calculate expected value (delegates to odds_utils)."""
        return calculate_ev(bet_odds, true_probability)
    
    def generate_bookmaker_link(self, bookmaker_key: str, sport: str, home_team: str, away_team: str) -> str:
        """Generate bookmaker link (delegates to BookmakerURLGenerator)."""
        return BookmakerURLGenerator.generate_bookmaker_link(bookmaker_key, sport, home_team, away_team)
    
    def get_sharp_average(self, outcomes: List[Dict], outcome_name: str) -> Optional[float]:
        """
        Get average odds from sharp bookmakers for a specific outcome.
        
        Args:
            outcomes: List of bookmaker outcomes
            outcome_name: Name of the outcome to find
            
        Returns:
            Average decimal odds from sharp books, or None if not available
        """
        sharp_odds = []
        
        for bookmaker in outcomes:
            if bookmaker['key'] in self.sharp_books:
                # Find the specific outcome
                for market in bookmaker.get('markets', []):
                    for outcome in market.get('outcomes', []):
                        if outcome['name'] == outcome_name:
                            sharp_odds.append(outcome['price'])
        
        if sharp_odds:
            return sum(sharp_odds) / len(sharp_odds)
        return None
    
    def analyze_games_for_ev(self, games: List[Dict], sport: str, 
                            already_bet_game_ids: Optional[Set[str]] = None,
                            reference_time: Optional[datetime] = None) -> List[Dict]:
        """
        Analyze a list of games for +EV opportunities.
        This is the core analysis logic used by both live scanning and backtesting.
        
        Args:
            games: List of games with odds data
            sport: Sport key for context
            already_bet_game_ids: Set of game IDs to skip (or None to use repository)
            reference_time: Time to use for filtering live games (None = use current time)
            
        Returns:
            List of positive EV opportunities
        """
        opportunities = []
        
        if not games:
            return opportunities
        
        # Use provided game IDs or fetch from repository
        if already_bet_game_ids is None:
            already_bet_game_ids = set()
            if self.skip_already_bet_games:
                already_bet_game_ids = self.bet_repository.get_already_bet_game_ids()
        
        # Get failed bet opportunities to ignore (if max_failures > 0)
        failed_opportunities = set()
        if self.max_bet_failures > 0:
            failed_opportunities = self.bet_repository.get_failed_bet_opportunities(max_failures=self.max_bet_failures)
        
        
        for game in games:
            # Get game ID from API
            game_id = game.get('id', '')
            
            # Skip games that already have bets
            if game_id and game_id in already_bet_game_ids:
                continue
            
            # Skip live games (use reference_time for backtesting, current time for live)
            commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
            check_time = reference_time if reference_time else datetime.now(commence_time.tzinfo)
            if commence_time <= check_time:
                continue
            
            # Skip games too far in the future if max_days_ahead is set (only for live scanning)
            if self.max_days_ahead > 0 and reference_time is None:
                now = datetime.now(commence_time.tzinfo)
                time_until_game = (commence_time - now).total_seconds() / 86400  # Convert to days
                if time_until_game > self.max_days_ahead:
                    continue
            
            home_team = game['home_team']
            away_team = game['away_team']
            commence_time_str = commence_time.strftime('%Y-%m-%d %H:%M %Z')
            
            bookmakers = game.get('bookmakers', [])
            
            if not bookmakers:
                continue
            
            # Process each market type from config (e.g., h2h, spreads, totals, h2h_3_way)
            markets_list = [m.strip() for m in self.markets.split(',')]
            for market_type in markets_list:
                # Get all outcomes for this market across all bookmakers
                market_data = {}
                # Track number of outcomes per bookmaker to separate 2-way from 3-way markets
                bookmaker_outcome_counts = {}
                
                for bookmaker in bookmakers:
                    # Get bookmaker-level link (least specific)
                    bookmaker_link = bookmaker.get('link')
                    
                    for market in bookmaker.get('markets', []):
                        if market['key'] == market_type:
                            # Get market link (more specific)
                            market_link = market.get('link')
                            
                            # Track outcome count for this bookmaker's market
                            outcome_count = len(market.get('outcomes', []))
                            bookmaker_outcome_counts[bookmaker['key']] = outcome_count
                            
                            for outcome in market.get('outcomes', []):
                                outcome_key = outcome['name']
                                if 'point' in outcome:
                                    outcome_key += f" ({outcome['point']:+.1f})"
                                
                                if outcome_key not in market_data:
                                    market_data[outcome_key] = []
                                
                                # Get outcome/betslip link (most specific) - prioritize this
                                outcome_link = outcome.get('link')
                                
                                # Use most specific link available: outcome > market > bookmaker > game
                                best_link = outcome_link or market_link or bookmaker_link or game.get('link')
                                
                                market_data[outcome_key].append({
                                    'bookmaker': bookmaker['key'],
                                    'title': bookmaker['title'],
                                    'odds': outcome['price'],
                                    'link': best_link,  # Use most specific link available
                                    'outcome_count': outcome_count  # Track for filtering
                                })
                
                # Analyze each outcome
                for outcome_name, odds_list in market_data.items():
                    # Determine the most common outcome count for this market
                    # This ensures we compare 2-way with 2-way and 3-way with 3-way
                    outcome_counts = [o.get('outcome_count', 0) for o in odds_list]
                    if not outcome_counts:
                        continue
                    
                    # Use the most common outcome count (2-way or 3-way)
                    from collections import Counter
                    most_common_count = Counter(outcome_counts).most_common(1)[0][0]
                    
                    # Filter to only include bookmakers with matching outcome count
                    filtered_odds_list = [o for o in odds_list if o.get('outcome_count', 0) == most_common_count]
                    
                    # Get sharp book average as baseline (only from matching outcome count)
                    sharp_odds = [o['odds'] for o in filtered_odds_list if o['bookmaker'] in self.sharp_books]
                    
                    if not sharp_odds:
                        continue
                    
                    sharp_avg = sum(sharp_odds) / len(sharp_odds)
                    true_probability = calculate_implied_probability(sharp_avg)
                    
                    # Check each bookmaker's odds (only those with matching outcome count)
                    for odds_data in filtered_odds_list:
                        if odds_data['bookmaker'] in self.sharp_books:
                            continue  # Skip the sharp books themselves
                        
                        # Only show opportunities for betting bookmakers
                        if odds_data['bookmaker'] not in self.betting_bookmakers:
                            continue
                        
                        bet_odds = odds_data['odds']
                        ev = calculate_ev(bet_odds, true_probability)
                        
                        # Apply max odds filter
                        if self.max_odds > 0 and bet_odds > self.max_odds:
                            continue
                        
                        # Apply both EV and probability filters
                        if ev >= self.min_ev_threshold and true_probability >= self.min_true_probability:
                            # Skip opportunities that have failed multiple times
                            opportunity_key = (game_id, market_type, outcome_name)
                            if opportunity_key in failed_opportunities:
                                continue
                            
                            # Get bookmaker link from API if available, otherwise generate one
                            bookmaker_url = odds_data.get('link') or BookmakerURLGenerator.generate_bookmaker_link(
                                odds_data['bookmaker'],
                                sport,
                                home_team,
                                away_team
                            )
                            
                            # Calculate bookmaker's implied probability
                            bookmaker_probability = calculate_implied_probability(bet_odds)
                            
                            # Calculate full Kelly first (without fraction) to filter bet quality
                            kelly_stake_full = self.kelly.calculate_kelly_stake(
                                decimal_odds=bet_odds,
                                true_probability=true_probability,
                                kelly_fraction=1.0  # Full Kelly for filtering
                            )
                            
                            # Apply minimum Kelly percentage filter on FULL Kelly (before risk management)
                            # kelly_percentage is 0-100, min_kelly_percentage is 0-1
                            if kelly_stake_full['kelly_percentage'] < (self.min_kelly_percentage * 100):
                                continue
                            
                            # Now calculate actual stake with Kelly fraction for risk management
                            kelly_stake = self.kelly.calculate_kelly_stake(
                                decimal_odds=bet_odds,
                                true_probability=true_probability,
                                kelly_fraction=self.kelly_fraction
                            )
                            
                            # Calculate expected profit
                            expected_profit = self.kelly.calculate_expected_profit(
                                stake=kelly_stake['recommended_stake'],
                                decimal_odds=bet_odds,
                                true_probability=true_probability
                            )
                            
                            # Collect sharp book links for verification
                            sharp_links = []
                            for sharp_data in odds_list:
                                if sharp_data['bookmaker'] in self.sharp_books:
                                    sharp_link = sharp_data.get('link')
                                    if sharp_link:
                                        sharp_links.append({
                                            'name': sharp_data['title'],
                                            'odds': sharp_data['odds'],
                                            'link': sharp_link
                                        })
                            
                            opportunities.append({
                                'game_id': game_id,
                                'sport': sport,
                                'game': f"{away_team} @ {home_team}",
                                'commence_time': commence_time_str,
                                'market': market_type,
                                'outcome': outcome_name,
                                'bookmaker': odds_data['title'],
                                'bookmaker_key': odds_data['bookmaker'],
                                'odds': bet_odds,
                                'sharp_avg_odds': sharp_avg,
                                'ev_percentage': ev * 100,
                                'true_probability': true_probability * 100,
                                'bookmaker_probability': bookmaker_probability * 100,
                                'bookmaker_url': bookmaker_url,
                                'sharp_links': sharp_links,
                                'kelly_stake': kelly_stake,
                                'expected_profit': expected_profit
                            })
        
        return opportunities
    
    def find_positive_ev_opportunities(self, sport: str, markets: str = 'h2h') -> List[Dict]:
        """
        Find positive EV opportunities for a sport by fetching live odds.
        
        Args:
            sport: Sport key
            markets: Markets to analyze
            
        Returns:
            List of positive EV opportunities
        """
        print(f"\n{'='*80}")
        print(f"Scanning {sport.upper()} for +EV opportunities...")
        print(f"{'='*80}\n")
        
        # First check if there are any events (FREE endpoint)
        events = self.get_events(sport)
        if not events:
            print(f"ℹ️  No upcoming events for {sport}, skipping odds fetch")
            return []
        
        print(f"✓ Found {len(events)} events for {sport}, fetching odds...")
        games = self.get_odds(sport, markets)
        
        if not games:
            print("No games found or API error.")
            return []
        
        # Get already-bet game IDs if filtering is enabled
        already_bet_game_ids: Set[str] = set()
        if self.skip_already_bet_games:
            already_bet_game_ids = self.bet_repository.get_already_bet_game_ids()
            if already_bet_game_ids:
                print(f"🚫 Filtering out {len(already_bet_game_ids)} games with existing bets")
        
        # Use core analysis method
        return self.analyze_games_for_ev(games, sport, already_bet_game_ids)
    
    def scan_all_sports(self, sport_keys: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """
        Scan multiple sports for +EV opportunities using concurrent requests.
        
        Args:
            sport_keys: List of sport keys to scan, or None to read from env
            
        Returns:
            Dictionary mapping sport to list of opportunities
        """
        if sport_keys is None:
            # Read from environment variable or use defaults
            betting_sports_str = os.getenv('BETTING_SPORTS', 'soccer_epl,soccer_england_championship,soccer_spain_la_liga,soccer_germany_bundesliga,soccer_italy_serie_a,soccer_france_ligue_one,soccer_uefa_champs_league,soccer_uefa_europa_league')
            sport_keys = [sport.strip() for sport in betting_sports_str.split(',')]
        
        all_opportunities = {}
        
        # Use ThreadPoolExecutor for concurrent scanning
        print(f"🚀 Scanning {len(sport_keys)} sports with up to {self.max_concurrent_requests} concurrent requests...")
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent_requests) as executor:
            # Submit all sports for concurrent processing
            future_to_sport = {
                executor.submit(self.find_positive_ev_opportunities, sport, self.markets): sport 
                for sport in sport_keys
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_sport):
                sport = future_to_sport[future]
                try:
                    opportunities = future.result()
                    if opportunities:
                        all_opportunities[sport] = opportunities
                        print(f"✓ {sport}: Found {len(opportunities)} opportunities")
                except Exception as e:
                    print(f"⚠️  Error scanning {sport}: {e}")
        
        return all_opportunities
    
    def sort_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Sort opportunities based on configured sort criteria.
        
        Args:
            opportunities: List of opportunities to sort
            
        Returns:
            Sorted list of opportunities
        """
        # Determine sort key based on ORDER_BY setting
        sort_key_map = {
            'ev': lambda x: x['ev_percentage'],
            'kelly': lambda x: x['kelly_stake']['kelly_percentage'],
            'expected_profit': lambda x: x['expected_profit'],
            'odds': lambda x: x['odds'],
            'match_time': lambda x: x['commence_time']
        }
        
        # Get the sort key function, default to expected_profit
        sort_key = sort_key_map.get(self.order_by, sort_key_map['expected_profit'])
        
        # Determine reverse flag (desc = True, asc = False)
        reverse = (self.sort_order == 'desc')
        
        # Sort and return
        return sorted(opportunities, key=sort_key, reverse=reverse)
    
    def filter_one_bet_per_game(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Filter opportunities to show only the best bet per game.
        
        Args:
            opportunities: List of opportunities (should already be sorted)
            
        Returns:
            Filtered list with only one opportunity per game
        """
        if not self.one_bet_per_game:
            return opportunities
        
        seen_games = set()
        filtered = []
        
        for opp in opportunities:
            game_key = opp['game']
            if game_key not in seen_games:
                seen_games.add(game_key)
                filtered.append(opp)
        
        return filtered
    
    def print_opportunities(self, opportunities: Dict[str, List[Dict]]):
        """
        Print all positive EV opportunities in a readable format.
        
        Args:
            opportunities: Dictionary of opportunities by sport
        """
        total_count = sum(len(opps) for opps in opportunities.values())
        
        print(f"\n{'='*80}")
        print(f"POSITIVE EV OPPORTUNITIES FOUND: {total_count}")
        print(f"{'='*80}\n")
        
        if total_count == 0:
            print("No +EV opportunities found at this time.")
            return
        
        # Display sort settings
        sort_labels = {
            'ev': 'Expected Value %',
            'kelly': 'Kelly %',
            'expected_profit': 'Expected Profit',
            'odds': 'Odds',
            'match_time': 'Match Time'
        }
        sort_label = sort_labels.get(self.order_by, 'Expected Profit')
        order_label = 'Highest first' if self.sort_order == 'desc' else 'Lowest first'
        print(f"🔢 Sorted by: {sort_label} ({order_label})")
        
        if self.one_bet_per_game:
            print(f"🎯 Filter: ONE BET PER GAME (showing best opportunity per match)")
        else:
            print(f"🎯 Filter: ALL BETS (showing all opportunities including duplicates)")
        print()
        
        for sport, opps in opportunities.items():
            # Sort opportunities using configured method
            opps = self.sort_opportunities(opps)
            
            # Apply one-bet-per-game filter if enabled
            original_count = len(opps)
            opps = self.filter_one_bet_per_game(opps)
            filtered_count = len(opps)
            
            print(f"\n{'─'*80}")
            if self.one_bet_per_game and original_count != filtered_count:
                print(f"📊 {sport.upper().replace('_', ' ')}: {filtered_count} opportunities (filtered from {original_count})")
            else:
                print(f"📊 {sport.upper().replace('_', ' ')}: {filtered_count} opportunities")
            print(f"{'─'*80}\n")
            
            for i, opp in enumerate(opps, 1):
                # Convert odds to fractional
                frac_odds = decimal_to_fractional(opp['odds'])
                frac_sharp = decimal_to_fractional(opp['sharp_avg_odds'])
                
                # Get Kelly stake info
                kelly_info = opp['kelly_stake']
                
                print(f"{i}. 🎯 {opp['game']}")
                print(f"   📅 {opp['commence_time']}")
                print(f"   🎲 Market: {opp['market'].upper()}")
                print(f"   🏆 Bet: {opp['outcome']}")
                print(f"   💰 Bookmaker: {opp['bookmaker']}")
                print(f"   📈 Odds: {opp['odds']:.2f} ({frac_odds}) | Sharp: {opp['sharp_avg_odds']:.2f} ({frac_sharp})")
                print(f"   ✅ Expected Value: +{opp['ev_percentage']:.2f}%")
                print(f"   🎲 True Probability: {opp['true_probability']:.1f}% | Bookmaker: {opp['bookmaker_probability']:.1f}%")
                print(f"   ")
                kelly_fraction_display = f"({self.kelly_fraction * 100:.0f}% Kelly)" if self.kelly_fraction != 1.0 else "(Full Kelly)"
                print(f"   💵 RECOMMENDED BET SIZE {kelly_fraction_display}:")
                print(f"      Stake: £{kelly_info['recommended_stake']:.2f}")
                print(f"      Kelly %: {kelly_info['kelly_percentage']:.2f}% of bankroll")
                print(f"      Expected Profit: £{opp['expected_profit']:.2f}")
                print(f"   ")
                print(f"   ➤ PLACE BET HERE: {opp['bookmaker_url']}")
                
                # Display sharp book links for verification
                if opp['sharp_links']:
                    print(f"   ")
                    print(f"   📊 VERIFY WITH SHARP BOOKS:")
                    for sharp in opp['sharp_links']:
                        sharp_frac = decimal_to_fractional(sharp['odds'])
                        print(f"      • {sharp['name']}: {sharp['odds']:.2f} ({sharp_frac}) - {sharp['link']}")
                
                print()


def main():
    """
    Main function to run the positive EV scanner.
    """
    # Initialize scanner (reads from .env file)
    scanner = PositiveEVScanner()
    
    print("="*80)
    print("⚽ POSITIVE EV BETTING SCANNER")
    print("="*80)
    print("\nScanning for +EV opportunities...")
    print(f"📊 Sharp books baseline: {', '.join(scanner.sharp_books)}")
    print(f"🎰 Betting bookmakers: {', '.join(scanner.betting_bookmakers)}")
    print(f"🏆 Sports/Leagues: {os.getenv('BETTING_SPORTS', 'soccer leagues')}")
    print(f"✅ Minimum EV threshold: {scanner.min_ev_threshold * 100}%")
    if scanner.min_true_probability > 0:
        print(f"🎲 Minimum true probability: {scanner.min_true_probability * 100:.1f}%")
    if scanner.max_odds > 0:
        print(f"📊 Maximum odds: {scanner.max_odds:.1f}")
    if scanner.max_days_ahead > 0:
        print(f"⏰ Maximum days ahead: {scanner.max_days_ahead:.1f} days")
    print(f"💰 Bankroll: £{scanner.kelly.bankroll:.2f}")
    print(f"📐 Kelly Strategy: {scanner.kelly_fraction * 100:.0f}% Kelly ({scanner.kelly_fraction:.2f} fraction)")
    if scanner.min_kelly_percentage > 0:
        min_stake = scanner.kelly.bankroll * scanner.min_kelly_percentage
        print(f"📏 Minimum Kelly filter: {scanner.min_kelly_percentage * 100:.1f}% (£{min_stake:.2f} min stake)")
    
    # Scan popular sports
    opportunities = scanner.scan_all_sports()
    
    # Print results
    scanner.print_opportunities(opportunities)
    
    print("\n" + "="*80)
    print("SCAN COMPLETE")
    print("="*80)
    print("\n💡 TIP: Higher EV% = better opportunity, but verify the game details!")
    print("💡 TIP: Focus on markets you understand and track your CLV (Closing Line Value)")


if __name__ == "__main__":
    main()
