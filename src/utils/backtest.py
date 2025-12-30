"""
Historical Backtesting Tool

Backtests your positive EV betting strategy using real historical odds data
from The Odds API. This validates your simulator parameters and shows actual
performance with your exact strategy.
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv
import json
import time
import hashlib
import csv
from pathlib import Path
from src.core.positive_ev_scanner import PositiveEVScanner
from src.utils.odds_utils import calculate_implied_probability, calculate_ev
from src.utils.google_search_scraper import GoogleSearchScraper
from src.utils.espn_scores import ESPNScoresFetcher
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()


class HistoricalBacktester:
    """
    Backtest betting strategy using historical odds data.
    """
    
    def __init__(self, use_google_search: bool = False):
        """Initialize backtester with scanner.
        
        Args:
            use_google_search: If True, use SerpAPI to fetch real game results from Google Sports
        """
        self.api_key = os.getenv('ODDS_API_KEY')
        if not self.api_key:
            raise ValueError("ODDS_API_KEY must be set in .env file")
        
        self.base_url = "https://api.the-odds-api.com/v4"
        
        # Create cache directory
        self.cache_dir = Path('data/backtest_cache')
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize scanner (reads all parameters from .env)
        self.scanner = PositiveEVScanner(api_key=self.api_key)
        
        # Initialize ESPN + SerpAPI for real results if enabled
        self.use_google_search = use_google_search
        self.google_scraper = None
        self.espn_scraper = None
        if use_google_search:
            try:
                # Initialize SerpAPI for fallback
                self.google_scraper = GoogleSearchScraper()
                # Initialize ESPN with SerpAPI fallback
                self.espn_scraper = ESPNScoresFetcher(serpapi_fallback=self.google_scraper)
                print(f"✅ ESPN API enabled for real game results (with SerpAPI fallback)")
            except ValueError as e:
                print(f"⚠️  ESPN/SerpAPI not configured: {e}")
                print(f"   Falling back to simulated results")
                self.use_google_search = False
        
        # Store initial bankroll for resets
        self.initial_bankroll = self.scanner.kelly.bankroll
        
        # Track results
        self.bets_placed = []
        self.bankroll_history = [self.initial_bankroll]
        self.bankroll_timestamps = []
        self.current_bankroll = self.initial_bankroll
        self.games_bet_on = set()  # Track which games we've already bet on
        
        # Monte Carlo tracking
        self.all_simulations = []  # Store all simulation runs
        
        # In-memory cache for fast lookups
        self.memory_cache = {}  # Will be populated by preload_cache()
        
    def reset_state(self):
        """Reset backtester state for new Monte Carlo run."""
        self.bets_placed = []
        self.bankroll_history = [self.initial_bankroll]
        self.bankroll_timestamps = []
        self.current_bankroll = self.initial_bankroll
        self.games_bet_on = set()
        # Reset scanner's Kelly bankroll
        self.scanner.kelly.bankroll = self.initial_bankroll
    
    def _parse_timestamp(self, ts: str):
        """Parse timestamp string in various formats, always returning timezone-aware datetime."""
        from datetime import datetime, timezone
        
        # Try ISO format with Z
        if 'Z' in ts:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        
        # Try format with UTC suffix
        if ' UTC' in ts:
            dt = datetime.strptime(ts.replace(' UTC', ''), '%Y-%m-%d %H:%M')
            return dt.replace(tzinfo=timezone.utc)
        
        # Try plain ISO format
        try:
            dt = datetime.fromisoformat(ts)
            # Make timezone-aware if naive
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            # Last resort: try parsing as datetime string
            dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            return dt.replace(tzinfo=timezone.utc)
        
    def _get_cache_key(self, sport: str, date: str, markets: str) -> str:
        """Generate a cache key for the API request."""
        key_str = f"{sport}_{date}_{markets}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Load data from cache if it exists (checks memory first, then disk).
        
        Returns:
            - Dict: Data exists
            - None: Cache miss (not in cache)
            
        Note: Data cached as None (404) is treated as cache miss but won't trigger API retry.
        """
        # Check in-memory cache first
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]
        
        # Fall back to disk if not in memory
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    # Only cache in memory if data exists (skip 404s)
                    if data is not None:
                        self.memory_cache[cache_key] = data
                    return data
            except Exception as e:
                print(f"  Warning: Failed to load cache: {e}")
                return None
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict):
        """Save data to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            # Also store in memory cache
            self.memory_cache[cache_key] = data
        except Exception as e:
            print(f"  Warning: Failed to save cache: {e}")
    
    def preload_cache(self, sports: Optional[List[str]] = None, timestamps: Optional[List[str]] = None):
        """Pre-load cache files into memory for fast access.
        
        Args:
            sports: List of sport keys to preload (if None, loads all)
            timestamps: List of timestamps to preload (if None, loads all)
        """
        # If no filters provided, load everything
        if sports is None or timestamps is None:
            cache_files = list(self.cache_dir.glob('*.json'))
            if not cache_files:
                return
            
            print(f"\n🔄 Pre-loading all {len(cache_files)} cache files into memory...")
            start_time = time.time()
            
            loaded = 0
            for cache_file in cache_files:
                try:
                    cache_key = cache_file.stem
                    with open(cache_file, 'r') as f:
                        self.memory_cache[cache_key] = json.load(f)
                    loaded += 1
                except Exception as e:
                    print(f"  Warning: Failed to load {cache_file.name}: {e}")
            
            elapsed = time.time() - start_time
            print(f"✅ Pre-loaded {loaded} cache files in {elapsed:.2f}s")
            print(f"   Memory cache size: ~{len(str(self.memory_cache)) / 1024 / 1024:.1f} MB\n")
            return
        
        # Generate list of needed cache keys with their metadata
        needed_data = []
        to_fetch = []  # Items that need API calls
        
        print(f"\n🔄 Pre-loading {len(sports) * len(timestamps)} cache files for date range...\n")
        start_time = time.time()
        
        loaded_from_cache = 0
        failed = 0
        
        # First pass: load from cache synchronously (fast)
        print("Phase 1: Loading from disk cache...")
        for sport in sports:
            for timestamp in timestamps:
                cache_key = self._get_cache_key(sport, timestamp, 'h2h')
                cache_file = self.cache_dir / f"{cache_key}.json"
                
                if cache_file.exists():
                    try:
                        with open(cache_file, 'r') as f:
                            data = json.load(f)
                            # Skip None entries (404s - data doesn't exist)
                            if data is not None:
                                self.memory_cache[cache_key] = data
                                loaded_from_cache += 1
                            # else: skip 404s, don't add to to_fetch
                    except Exception as e:
                        failed += 1
                else:
                    # Mark for API fetching
                    to_fetch.append((cache_key, sport, timestamp))
        
        print(f"   Loaded {loaded_from_cache} files from cache")
        
        if not to_fetch:
            elapsed = time.time() - start_time
            print(f"\n✅ Pre-loaded {loaded_from_cache} files in {elapsed:.2f}s (all from cache)")
            print(f"   Memory cache size: ~{len(str(self.memory_cache)) / 1024 / 1024:.1f} MB\n")
            return
        
        # Second pass: fetch missing data from API in parallel
        print(f"\nPhase 2: Fetching {len(to_fetch)} missing files from API...")
        fetched_from_api = 0
        
        # Rate limiter: track API call timing and errors
        rate_limiter = {'last_call': time.time(), 'lock': threading.Lock()}
        min_interval = 0.02  # 50 requests per second max
        error_summary = {}  # Track error types
        error_lock = threading.Lock()
        
        def fetch_one(cache_key, sport, timestamp):
            """Fetch a single historical odds snapshot with rate limiting."""
            nonlocal fetched_from_api, failed
            
            # Rate limit: ensure minimum time between API calls
            with rate_limiter['lock']:
                elapsed = time.time() - rate_limiter['last_call']
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                rate_limiter['last_call'] = time.time()
            
            try:
                url = f"{self.base_url}/historical/sports/{sport}/odds"
                params = {
                    'apiKey': self.api_key,
                    'bookmakers': ','.join(self.scanner.optimized_bookmakers),
                    'markets': self.scanner.markets,
                    'oddsFormat': self.scanner.odds_format,
                    'date': timestamp
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Save to cache and memory (thread-safe)
                self._save_to_cache(cache_key, data)
                return True
                
            except requests.exceptions.HTTPError as e:
                # Track error types
                status_code = e.response.status_code if e.response is not None else 'unknown'
                error_type = f"HTTPError_{status_code}"

                # if rate limit exceeded print
                if status_code == 429:
                    print("  ⚠️  Rate limit exceeded. Consider slowing down requests.")
                
                # Handle 422 by trying individual markets (like live scanner)
                if status_code == 422:
                    market_list = [m.strip() for m in self.scanner.markets.split(',')]
                    if len(market_list) > 1:
                        # Try each market individually
                        combined_data = {'data': []}
                        game_dict = {}  # Track games by ID to merge data
                        success_count = 0
                        
                        for market in market_list:
                            try:
                                params['markets'] = market
                                market_response = requests.get(url, params=params, timeout=10)
                                market_response.raise_for_status()
                                market_data = market_response.json()
                                
                                if market_data and 'data' in market_data:
                                    # Merge game data
                                    for game in market_data['data']:
                                        game_id = game.get('id')
                                        if game_id in game_dict:
                                            # Merge bookmakers for existing game
                                            existing_game = game_dict[game_id]
                                            for bookmaker in game.get('bookmakers', []):
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
                                            game_dict[game_id] = game
                                            combined_data['data'].append(game)
                                    
                                    success_count += 1
                                    
                            except requests.exceptions.HTTPError as market_error:
                                # Individual market failed, continue to next
                                continue
                        
                        # If we got any successful markets, save combined data
                        if success_count > 0:
                            self._save_to_cache(cache_key, combined_data)
                            return True
                
                # Track all HTTP errors
                with error_lock:
                    error_summary[error_type] = error_summary.get(error_type, 0) + 1
                
                # Cache 404 as empty (data doesn't exist)
                # Cache 422 as None to avoid retrying every time
                if status_code == 404 or status_code == 422:
                    self._save_to_cache(cache_key, None)
                
                return False
                
            except Exception as e:
                # Track other error types (network, timeout, etc.)
                error_type = type(e).__name__
                
                with error_lock:
                    error_summary[error_type] = error_summary.get(error_type, 0) + 1
                
                # Don't cache - allow retry on next run
                return False
        
        # Use ThreadPoolExecutor for parallel fetching (max 5 concurrent)
        max_workers = 15
        pbar = tqdm(total=len(to_fetch), desc="Fetching from API", unit="file", ncols=120,
                   bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all fetch tasks
            future_to_data = {executor.submit(fetch_one, *item): item for item in to_fetch}
            
            # Process as they complete
            for future in as_completed(future_to_data):
                success = future.result()
                if success:
                    fetched_from_api += 1
                else:
                    failed += 1
                
                pbar.update(1)
                pbar.set_postfix({'fetched': fetched_from_api, 'failed': failed})
        
        pbar.close()
        
        elapsed = time.time() - start_time
        total_loaded = loaded_from_cache + fetched_from_api
        print(f"\n✅ Pre-loaded {total_loaded} files in {elapsed:.2f}s")
        print(f"   From cache: {loaded_from_cache}, From API: {fetched_from_api}")
        if failed > 0:
            print(f"   ⚠️  Failed/unavailable: {failed}")
            if error_summary:
                print(f"   📊 Error breakdown:")
                for error_type, count in sorted(error_summary.items(), key=lambda x: x[1], reverse=True):
                    print(f"      • {error_type}: {count}")
        if fetched_from_api > 0:
            print(f"   💰 API credits used: ~{fetched_from_api * 10}")
        print(f"   Memory cache size: ~{len(str(self.memory_cache)) / 1024 / 1024:.1f} MB\n")
    
    def bulk_get_historical_odds(self, sports: List[str], timestamps: List[str], markets: str = 'h2h') -> Dict:
        """Bulk fetch all historical odds data for multiple sports and timestamps.
        
        Args:
            sports: List of sport keys
            timestamps: List of ISO timestamps
            markets: Markets to query
            
        Returns:
            Dictionary mapping (sport, timestamp) -> (data, was_cached)
        """
        total_lookups = len(sports) * len(timestamps)
        print(f"\n📦 Bulk fetching {total_lookups} historical odds snapshots...")
        start_time = time.time()
        
        results = {}
        cache_hits = 0
        cache_misses = 0
        
        for sport in sports:
            for timestamp in timestamps:
                cache_key = self._get_cache_key(sport, timestamp, markets)
                
                # Direct memory cache lookup (skip function call overhead)
                if cache_key in self.memory_cache:
                    results[(sport, timestamp)] = (self.memory_cache[cache_key], True)
                    cache_hits += 1
                else:
                    # Would need API call - skip for now
                    results[(sport, timestamp)] = (None, False)
                    cache_misses += 1
        
        elapsed = time.time() - start_time
        hit_rate = (cache_hits / total_lookups * 100) if total_lookups > 0 else 0
        print(f"✅ Bulk fetch complete in {elapsed:.3f}s")
        print(f"   Cache hits: {cache_hits}/{total_lookups} ({hit_rate:.1f}%)")
        if cache_misses > 0:
            print(f"   ⚠️  Cache misses: {cache_misses} (these will be skipped)")
        print()
        
        return results
        
    def get_historical_odds(self, sport: str, date: str, markets: str = 'h2h') -> Optional[tuple]:
        """
        Get historical odds for a specific date (with caching).
        
        Args:
            sport: Sport key (e.g., 'soccer_epl')
            date: ISO timestamp (e.g., '2024-01-01T12:00:00Z')
            markets: Markets to query
            
        Returns:
            Tuple of (data, was_cached) or (None, False) if error
        """
        # Check cache first
        cache_key = self._get_cache_key(sport, date, markets)
        cached_data = self._load_from_cache(cache_key)
        
        if cached_data:
            return (cached_data, True)
        
        # Fetch from API
        url = f"{self.base_url}/historical/sports/{sport}/odds"
        params = {
            'apiKey': self.api_key,
            'bookmakers': ','.join(self.scanner.optimized_bookmakers),
            'markets': markets,
            'oddsFormat': self.scanner.odds_format,
            'date': date
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Check remaining quota (show less frequently to reduce output)
            remaining = response.headers.get('x-requests-remaining')
            if remaining and int(float(remaining)) % 10 == 0:
                print(f"  📊 API Requests Remaining: {remaining}")
            
            data = response.json()
            
            # Save to cache
            self._save_to_cache(cache_key, data)
            
            return (data, False)
        except requests.exceptions.RequestException as e:
            # Silently skip errors - likely outright/championship markets with wrong market type
            return (None, False)
    
    def get_historical_scores(self, sport: str, date_from: str, date_to: str) -> Optional[List[Dict]]:
        """
        Get historical scores/results for games in date range (with caching).
        
        NOTE: The Odds API doesn't provide historical scores through the scores endpoint.
        Historical scores are included in the historical odds data itself.
        This method fetches the historical odds data to extract the scores.
        
        Args:
            sport: Sport key
            date_from: Start date (ISO format)
            date_to: End date (ISO format)
            
        Returns:
            List of completed games with scores
        """
        # Skip score fetching for outright/championship winner markets (futures)
        if '_winner' in sport or '_championship' in sport:
            print(f"  ⏭️  Skipping (outright market, no game scores)")
            return []
        
        # Check cache first
        cache_key = self._get_cache_key(sport, f"scores_{date_from}_{date_to}", "scores")
        cached_data = self._load_from_cache(cache_key)
        
        if cached_data:
            print(f"💾 Loaded scores from cache")
            return cached_data
        
        # Fetch historical odds which include scores for completed games
        # We fetch one snapshot well after the period to ensure all games have completed
        # But cap it to at least 7 days ago (games need time to complete and be marked as such)
        from datetime import timezone
        end_date = datetime.fromisoformat(date_to)
        today = datetime.now(timezone.utc)
        # Use at least 7 days ago, and normalize to noon UTC for consistency
        seven_days_ago = (today - timedelta(days=7)).replace(hour=12, minute=0, second=0, microsecond=0)
        snapshot_time_date = min(end_date + timedelta(days=90), seven_days_ago)
        snapshot_time = snapshot_time_date.replace(hour=12, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        result = self.get_historical_odds(sport, snapshot_time)
        if not result:
            print(f"  ⚠️  No historical data available for scores")
            return []
        
        historical_data, was_cached = result
        
        if not historical_data or 'data' not in historical_data:
            print(f"  ⚠️  No historical data available for scores")
            return []
        
        # Extract scores from historical data
        # NOTE: Historical odds snapshots don't include game results
        # The API only provides results in real-time via the scores endpoint (max 3 days back)
        # For older historical backtests, results must be simulated
        scores = []
        total_games = len(historical_data.get('data', []))
        for game in historical_data['data']:
            if game.get('completed', False) and game.get('scores'):
                scores.append(game)
        
        if len(scores) == 0 and total_games > 0:
            print(f"  ℹ️  Found {total_games} games (results will be simulated)")
        elif len(scores) > 0:
            print(f"✅ Loaded {len(scores)} completed games out of {total_games} total games")
        
        # Save to cache
        self._save_to_cache(cache_key, scores)
        
        return scores
    
    def find_positive_ev_bets(self, historical_data: Dict, sport: str, snapshot_time: Optional[datetime] = None) -> List[Dict]:
        """
        Analyze historical odds snapshot to find +EV bets.
        
        This method uses the scanner's analyze_games_for_ev() to ensure the backtest
        uses exactly the same logic as live scanning.
        
        Args:
            historical_data: Response from historical odds API
            sport: Sport key for context
            snapshot_time: Time of the snapshot (for backtesting) - if None, uses current time
            
        Returns:
            List of positive EV betting opportunities
        """
        if not historical_data or 'data' not in historical_data:
            return []
        
        # Keep scanner's Kelly bankroll at initial value for consistent bet sizing
        self.scanner.kelly.bankroll = self.initial_bankroll
        
        games = historical_data['data']
        
        # Use the scanner's core analysis method with backtest-specific parameters
        opportunities = self.scanner.analyze_games_for_ev(
            games=games,
            sport=sport,
            already_bet_game_ids=self.games_bet_on,  # Track games bet in this backtest
            reference_time=snapshot_time  # Use snapshot time instead of current time
        )
        
        # Convert scanner's output format to backtest format
        # Scanner returns ev_percentage (0-100), backtest expects ev (0-1)
        # Scanner returns kelly_stake dict, backtest expects flat fields
        for opp in opportunities:
            if 'ev_percentage' in opp:
                opp['ev'] = opp['ev_percentage'] / 100
            if 'kelly_stake' in opp:
                opp['kelly_pct'] = opp['kelly_stake']['kelly_percentage'] / 100
                opp['stake'] = opp['kelly_stake']['recommended_stake']
            if 'true_probability' in opp and opp['true_probability'] >= 1:
                # Scanner returns percentage (0-100), backtest expects decimal (0-1)
                opp['true_probability'] = opp['true_probability'] / 100
        
        return opportunities
    
    def _prefetch_game_results(self, bets: List[Dict], current_time: datetime):
        """
        Pre-fetch all unique game results in parallel to speed up settlement.
        Stores results in memory cache for instant lookup during settlement.
        
        Args:
            bets: List of bets to fetch results for
            current_time: Current time in backtest for look-ahead protection
        """
        # Extract unique games that need results
        unique_games = {}
        for bet in bets:
            game_str = bet.get('game', '')
            if ' @ ' not in game_str:
                continue
            
            # Check if game has completed (same logic as determine_bet_result)
            commence_time = bet.get('commence_time', '')
            if commence_time and current_time:
                try:
                    if isinstance(commence_time, str):
                        game_time = self._parse_timestamp(commence_time)
                    else:
                        game_time = commence_time
                    
                    from datetime import timedelta
                    game_completion_time = game_time + timedelta(hours=4)
                    
                    # Skip games not yet completed
                    if current_time < game_completion_time:
                        continue
                except Exception:
                    continue
            
            # Create unique key for this game
            away_team, home_team = game_str.split(' @ ')
            away_team = away_team.strip()
            home_team = home_team.strip()
            sport = bet.get('sport', '')
            game_date = self._parse_timestamp(bet.get('commence_time', ''))
            
            game_key = f"{sport}|{away_team}|{home_team}|{game_date.date()}"
            if game_key not in unique_games:
                unique_games[game_key] = {
                    'sport': sport,
                    'away_team': away_team,
                    'home_team': home_team,
                    'game_date': game_date
                }
        
        if not unique_games:
            return
        
        print(f"   Fetching results for {len(unique_games)} unique games...")
        
        # Fetch results sequentially to avoid rate limiting
        results_cache = {}
        
        # Progress bar for fetching
        from tqdm import tqdm
        for game_key, game_info in tqdm(unique_games.items(), desc="Fetching results", unit="game", ncols=100):
            try:
                result = self.espn_scraper.get_game_result(
                    sport=game_info['sport'],
                    team1=game_info['away_team'],
                    team2=game_info['home_team'],
                    game_date=game_info['game_date']
                )
                
                if result:
                    results_cache[game_key] = result
                    
            except Exception as e:
                # Silently fail for individual games
                pass
        
        # Store in memory cache
        self.memory_cache.update(results_cache)
        print(f"   ✅ Cached {len(results_cache)} game results in memory\n")
    
    def determine_bet_result(self, bet: Dict, scores_data: Dict, current_time: Optional[datetime] = None) -> Optional[str]:
        """
        Determine if a bet won or lost based on actual game results.
        
        This method first tries to use Google Search API (if enabled) to fetch
        real game results. If that fails or is disabled, falls back to pre-indexed
        scores data.
        
        CRITICAL: Only fetches results for games that have ALREADY completed at current_time
        to prevent look-ahead bias in backtesting.
        
        Args:
            bet: Bet details (must include 'game', 'sport', 'outcome', 'market', 'commence_time')
            scores_data: Pre-indexed scores data by game matchup (fallback)
            current_time: Current time in backtest (None = use actual current time for live trading)
            
        Returns:
            'won', 'lost', or None if result unknown
        """
        # ANTI-LOOK-AHEAD PROTECTION:
        # Only check game results if the game has already completed
        commence_time = bet.get('commence_time', '')
        if commence_time and current_time:
            # Parse commence time
            try:
                if isinstance(commence_time, str):
                    game_time = self._parse_timestamp(commence_time)
                else:
                    game_time = commence_time
                
                # Add buffer for game completion (e.g., 4 hours for most sports)
                # This ensures the game has actually finished before we look up results
                from datetime import timedelta
                game_completion_time = game_time + timedelta(hours=4)
                
                # If current backtest time is before game completion, result is not yet known
                if current_time < game_completion_time:
                    return None
            except Exception:
                # If we can't parse the time, be conservative and return None
                return None
        
        # Try ESPN API first (with SerpAPI fallback) if enabled
        if self.use_google_search and self.espn_scraper:
            try:
                # Parse team names from the game string (e.g., "Buffalo Bills @ New England Patriots")
                game_str = bet.get('game', '')
                if ' @ ' in game_str:
                    away_team, home_team = game_str.split(' @ ')
                    away_team = away_team.strip()
                    home_team = home_team.strip()
                    
                    # Get game date from commence_time
                    commence_time_str = bet.get('commence_time', '')
                    sport = bet.get('sport', '')
                    
                    # Parse game date
                    if commence_time_str:
                        game_date = self._parse_timestamp(commence_time_str)
                        
                        # Check memory cache first (from prefetch)
                        game_key = f"{sport}|{away_team}|{home_team}|{game_date.date()}"
                        result = self.memory_cache.get(game_key)
                        
                        # If not in cache, fetch it (fallback for edge cases)
                        if not result:
                            result = self.espn_scraper.get_game_result(
                                sport=sport,
                                team1=away_team,
                                team2=home_team,
                                game_date=game_date
                            )
                        
                        if result and 'home_score' in result and 'away_score' in result:
                            home_score = result['home_score']
                            away_score = result['away_score']
                            espn_home = result.get('home_team', home_team)
                            espn_away = result.get('away_team', away_team)
                            source = result.get('source', 'unknown')
                            
                            print(f"   ✓ Settled via {source.upper()}: {espn_away} {away_score} @ {espn_home} {home_score}")
                            
                            # Determine winner based on market type
                            if bet['market'] == 'h2h':
                                outcome = bet['outcome']
                                
                                # Match outcome to actual teams (case-insensitive partial match)
                                outcome_lower = outcome.lower()
                                home_lower = home_team.lower()
                                away_lower = away_team.lower()
                                espn_home_lower = espn_home.lower()
                                espn_away_lower = espn_away.lower()
                                
                                # Determine if bet was on home or away team
                                bet_on_home = (outcome_lower in home_lower or home_lower in outcome_lower or 
                                              outcome_lower in espn_home_lower or espn_home_lower in outcome_lower)
                                bet_on_away = (outcome_lower in away_lower or away_lower in outcome_lower or
                                              outcome_lower in espn_away_lower or espn_away_lower in outcome_lower)
                                
                                # Check if bet won
                                if bet_on_home and home_score > away_score:
                                    return 'won'
                                elif bet_on_away and away_score > home_score:
                                    return 'won'
                                elif 'draw' in outcome_lower and home_score == away_score:
                                    return 'won'
                                else:
                                    return 'lost'
                
            except Exception as e:
                # If ESPN/SerpAPI fails, fall back to scores_data
                pass
        
        # Fallback: Look up game in pre-indexed scores data
        bet_game = f"{bet.get('game', '')}"
        game = scores_data.get(bet_game)
        
        if game:
            # Check if game is completed
            if not game.get('completed', False):
                return None
            
            scores = game.get('scores')
            if not scores or len(scores) < 2:
                return None
            
            # Parse scores
            home_score = None
            away_score = None
            
            for score in scores:
                if score['name'] == game['home_team']:
                    home_score = int(score['score'])
                elif score['name'] == game['away_team']:
                    away_score = int(score['score'])
            
            if home_score is None or away_score is None:
                return None
            
            # Determine winner based on market type
            if bet['market'] == 'h2h':
                outcome = bet['outcome']
                
                if outcome == game['home_team'] and home_score > away_score:
                    return 'won'
                elif outcome == game['away_team'] and away_score > home_score:
                    return 'won'
                elif 'Draw' in outcome and home_score == away_score:
                    return 'won'
                else:
                    return 'lost'
            
            # For spreads and totals, would need more complex logic
            # For now, return None for these markets
            return None
        
        return None
    
    def place_bet(self, bet: Dict, result: Optional[str] = None, bet_timestamp: Optional[str] = None):
        """
        Simulate placing a bet and update bankroll only when bet settles.
        
        Args:
            bet: Bet details
            result: 'won', 'lost', or None (pending)
            bet_timestamp: When the bet was placed (for charting)
        """
        stake = bet['stake']
        commence_time = bet.get('commence_time')
        
        # Only update bankroll for settled bets
        if result == 'won':
            profit = stake * (bet['odds'] - 1)
            self.current_bankroll += profit  # Just add the profit (net gain)
            actual_profit = profit
            
            # Record bankroll at settlement time
            if bet_timestamp:
                self.bankroll_timestamps.append(bet_timestamp)
                self.bankroll_history.append(self.current_bankroll)
                
        elif result == 'lost':
            self.current_bankroll -= stake  # Deduct the stake (net loss)
            actual_profit = -stake
            
            # Record bankroll at settlement time
            if bet_timestamp:
                self.bankroll_timestamps.append(bet_timestamp)
                self.bankroll_history.append(self.current_bankroll)
        else:
            # Pending - don't update bankroll yet
            actual_profit = 0
        
        bet['result'] = result
        bet['actual_profit'] = actual_profit
        bet['bankroll_after'] = self.current_bankroll if result is not None else None
        
        self.bets_placed.append(bet)
    
    def backtest(self, sports: List[str], start_date: str, end_date: str, 
                 snapshot_interval_hours: int = 12) -> Dict:
        """
        Run backtest over a date range for one or more sports.
        
        Args:
            sports: List of sport keys (e.g., ['soccer_epl', 'basketball_nba'])
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            snapshot_interval_hours: Hours between snapshots (default 12)
            
        Returns:
            Backtest results
        """
        # Support single sport string for backward compatibility
        if isinstance(sports, str):
            sports = [sports]
        
        print(f"\n{'='*80}")
        print(f"HISTORICAL BACKTESTING")
        print(f"{'='*80}")
        print(f"Sports: {', '.join(sports)}")
        print(f"Date Range: {start_date} to {end_date}")
        print(f"Initial Bankroll: £{self.initial_bankroll:.2f}")
        print(f"Kelly Fraction: {self.scanner.kelly_fraction}")
        print(f"Min EV: {self.scanner.min_ev_threshold*100:.1f}%")
        print(f"Min True Probability: {self.scanner.min_true_probability*100:.1f}%")
        if self.scanner.min_kelly_percentage > 0:
            print(f"Min Kelly Percentage: {self.scanner.min_kelly_percentage*100:.1f}%")
        if self.scanner.max_odds > 0:
            print(f"Max Odds: {self.scanner.max_odds:.1f}")
        print(f"Sharp Books: {', '.join(self.scanner.sharp_books)}")
        print(f"Betting Bookmakers: {', '.join(self.scanner.betting_bookmakers)}")
        print(f"One Bet Per Game: {self.scanner.one_bet_per_game}")
        print(f"{'='*80}\n")
        
        # Parse dates and make them timezone-aware (UTC) for comparison with API data
        from datetime import timezone
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
        current = start
        
        snapshot_count = 0
        total_opportunities = 0
        
        # Determine result source
        if self.use_google_search and self.google_scraper:
            print("\n📋 Using Google Search API for real game results\n")
        else:
            print("\n📋 Using simulated results based on true win probabilities\n")
        scores_data = {}
        
        # Calculate total snapshots for progress bar
        total_seconds = (end - start).total_seconds()
        interval_seconds = snapshot_interval_hours * 3600
        total_snapshots = int(total_seconds / interval_seconds) + 1
        
        # Pre-generate all timestamps
        all_timestamps = []
        temp_current = start
        while temp_current <= end:
            all_timestamps.append(temp_current.strftime('%Y-%m-%dT%H:%M:%SZ'))
            temp_current += timedelta(hours=snapshot_interval_hours)
        
        # Pre-load only the cache files needed for this date range
        self.preload_cache(sports=sports, timestamps=all_timestamps)
        
        # Bulk fetch all historical odds data upfront (eliminates 750 function calls)
        odds_data_cache = self.bulk_get_historical_odds(sports, all_timestamps)
        
        # Create progress bar with finer granularity (update per sport processed)
        total_iterations = total_snapshots * len(sports)
        pbar = tqdm(total=total_iterations, desc="Backtesting", unit="check", ncols=120, 
                   bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
        
        while current <= end:
            snapshot_count += 1
            timestamp = current.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Collect opportunities from all sports for this timestamp
            all_opportunities = []
            
            for sport in sports:
                # Direct lookup from bulk-fetched cache (no function call overhead)
                cache_result = odds_data_cache.get((sport, timestamp))
                historical_data, was_cached = cache_result if cache_result else (None, False)
                
                if historical_data:
                    # Find +EV opportunities using scanner, passing snapshot time for proper filtering
                    opportunities = self.find_positive_ev_bets(historical_data, sport, snapshot_time=current)
                    
                    # Add sport info to each opportunity
                    for opp in opportunities:
                        opp['sport'] = sport
                    
                    all_opportunities.extend(opportunities)
                
                # Update progress bar after each sport
                pbar.update(1)
                pbar.set_postfix({'bets': len(self.bets_placed), 'opps': total_opportunities})
            
            if all_opportunities:
                # Filter out games we've already bet on
                new_opportunities = []
                for opp in all_opportunities:
                    if opp['game_id'] not in self.games_bet_on:
                        new_opportunities.append(opp)
                        self.games_bet_on.add(opp['game_id'])
                
                if new_opportunities:
                    total_opportunities += len(new_opportunities)
                    pbar.set_postfix({'bets': len(self.bets_placed), 'opps': total_opportunities})
                    
                    # Batch process all bets for this snapshot
                    import random
                    won_count = 0
                    lost_count = 0
                    pending_count = 0
                    
                    for opp in new_opportunities:
                        # Don't settle during backtest - settle all at the end
                        result = None
                        pending_count += 1
                        
                        # Store when this bet was placed (discovered), not game time
                        opp['bet_placed_at'] = timestamp
                        self.place_bet(opp, result, bet_timestamp=timestamp)
                    
                    # Update postfix with latest stats
                    pbar.set_postfix({'bets': len(self.bets_placed), 'opps': total_opportunities, 
                                    'bankroll': f'£{self.current_bankroll:.0f}'})
            
            # Move to next snapshot
            current += timedelta(hours=snapshot_interval_hours)
        
        # Close progress bar
        pbar.close()
        
        # Settle all pending bets at the end of backtest using Google results
        pending_bets = [b for b in self.bets_placed if b.get('result') is None]
        if pending_bets:
            print(f"\n{'='*80}")
            print(f"SETTLING PENDING BETS WITH GOOGLE RESULTS")
            print(f"{'='*80}")
            print(f"Fetching real results for {len(pending_bets)} pending bets...\n")
            
            # Pre-fetch all unique game results in parallel to speed up settlement
            if self.use_google_search and self.espn_scraper:
                print("⚡ Pre-fetching game results in parallel...")
                self._prefetch_game_results(pending_bets, end)
                print(f"✅ Pre-fetch complete. Now settling bets...\n")
            
            settled_count = 0
            failed_count = 0
            
            # Create progress bar for settling bets
            settle_pbar = tqdm(pending_bets, desc="Settling bets", unit="bet", ncols=120,
                             bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
            
            for bet in settle_pbar:
                # Use end time as current_time to check if game has completed
                result = self.determine_bet_result(bet, scores_data, current_time=end)
                
                if result is not None:
                    # Update bet result and bankroll
                    bet['result'] = result
                    
                    if result == 'won':
                        profit = bet['stake'] * (bet['odds'] - 1)
                        self.current_bankroll += profit
                        bet['actual_profit'] = profit
                    else:  # lost
                        self.current_bankroll -= bet['stake']
                        bet['actual_profit'] = -bet['stake']
                    
                    bet['bankroll_after'] = self.current_bankroll
                    
                    # Add to bankroll history
                    bet_time = bet.get('bet_placed_at', bet.get('commence_time'))
                    if bet_time:
                        self.bankroll_timestamps.append(bet_time)
                        self.bankroll_history.append(self.current_bankroll)
                    
                    settled_count += 1
                else:
                    failed_count += 1
                
                # Update progress bar with current stats
                settle_pbar.set_postfix({'settled': settled_count, 'failed': failed_count})
            
            settle_pbar.close()
            
            print(f"\n✅ Settled {settled_count} bets with real Google results")
            if failed_count > 0:
                print(f"❌ Failed to get results for {failed_count} bets (will be excluded from analysis)")
            print()
        
        # Print ESPN/SerpAPI statistics if used
        if self.use_google_search and self.espn_scraper:
            self.espn_scraper.print_stats()
        
        print(f"\n{'='*80}")
        print(f"BACKTEST COMPLETE")
        print(f"{'='*80}\n")
        
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate comprehensive backtest report."""
        if not self.bets_placed:
            print("No bets were placed during backtest.")
            return {}
        
        # Filter out pending/unsettled bets
        settled_bets = [b for b in self.bets_placed if b.get('result') is not None]
        pending_bets = [b for b in self.bets_placed if b.get('result') is None]
        
        total_bets = len(settled_bets)
        pending_count = len(pending_bets)
        
        # Check if we have any settled bets
        if total_bets == 0:
            print("No settled bets found during backtest.")
            if pending_count > 0:
                print(f"All {pending_count} bets are still pending (games haven't finished yet).")
            return {}
        
        won_bets = sum(1 for b in settled_bets if b.get('result') == 'won')
        lost_bets = sum(1 for b in settled_bets if b.get('result') == 'lost')
        
        total_staked = sum(b['stake'] for b in settled_bets)
        total_profit = sum(b.get('actual_profit', 0) for b in settled_bets)
        
        final_bankroll = self.current_bankroll
        total_return = (final_bankroll - self.initial_bankroll) / self.initial_bankroll * 100
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        
        # Calculate max drawdown
        peak = self.initial_bankroll
        max_drawdown = 0
        max_drawdown_pct = 0
        
        for br in self.bankroll_history:
            if br > peak:
                peak = br
            drawdown = peak - br
            drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0
            if drawdown_pct > max_drawdown_pct:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct
        
        # Calculate actual EV stats from settled bets only
        actual_evs = [b['ev'] for b in settled_bets]
        avg_ev = sum(actual_evs) / len(actual_evs) if actual_evs else 0
        
        actual_odds = [b['odds'] for b in settled_bets]
        avg_odds = sum(actual_odds) / len(actual_odds) if actual_odds else 0
        
        actual_probs = [b['true_probability'] for b in settled_bets]
        avg_prob = sum(actual_probs) / len(actual_probs) if actual_probs else 0
        
        # Print report
        print(f"BACKTEST RESULTS")
        print(f"{'='*80}\n")
        
        print(f"Settled Bets: {total_bets}")
        print(f"  Won: {won_bets} ({won_bets/total_bets*100:.1f}%)")
        print(f"  Lost: {lost_bets} ({lost_bets/total_bets*100:.1f}%)")
        if pending_count > 0:
            print(f"  Pending (ignored): {pending_count}")
        
        print(f"\nBankroll Performance:")
        print(f"  Starting: £{self.initial_bankroll:.2f}")
        print(f"  Final: £{final_bankroll:.2f}")
        print(f"  Total Return: {total_return:+.2f}%")
        print(f"  Total Profit: £{total_profit:+.2f}")
        
        print(f"\nBetting Statistics:")
        print(f"  Total Staked: £{total_staked:.2f}")
        print(f"  ROI: {roi:.2f}%")
        print(f"  Avg Stake: £{total_staked/total_bets:.2f}")
        
        print(f"\nActual Bet Characteristics:")
        print(f"  Avg Odds: {avg_odds:.3f}")
        print(f"  Avg True Probability: {avg_prob*100:.1f}%")
        print(f"  Avg EV: {avg_ev*100:.2f}%")
        
        print(f"\nRisk Metrics:")
        print(f"  Max Drawdown: £{max_drawdown:.2f} ({max_drawdown_pct:.2f}%)")
        
        # Export bets to CSV
        self.export_bets_to_csv()
        
        # Show per-sport breakdown if multiple sports
        sports_in_bets = set(b.get('sport') for b in settled_bets if b.get('sport'))
        if len(sports_in_bets) > 1:
            print(f"\nPer-Sport Breakdown:")
            for sport in sorted(sports_in_bets):
                sport_bets = [b for b in settled_bets if b.get('sport') == sport]
                sport_count = len(sport_bets)
                sport_won = sum(1 for b in sport_bets if b.get('result') == 'won')
                sport_profit = sum(b.get('actual_profit', 0) for b in sport_bets)
                print(f"  {sport}: {sport_count} bets, {sport_won}W-{sport_count-sport_won}L, £{sport_profit:+.2f}")
        
        print(f"\n{'='*80}\n")
        
        return {
            'total_bets': total_bets,
            'pending_bets': pending_count,
            'won_bets': won_bets,
            'lost_bets': lost_bets,
            'win_rate': won_bets / total_bets if total_bets > 0 else 0,
            'initial_bankroll': self.initial_bankroll,
            'final_bankroll': final_bankroll,
            'total_return_pct': total_return,
            'total_profit': total_profit,
            'total_staked': total_staked,
            'roi': roi,
            'avg_odds': avg_odds,
            'avg_true_prob': avg_prob,
            'avg_ev': avg_ev,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'bankroll_history': self.bankroll_history,
            'bets': settled_bets,
            'pending_bets_list': pending_bets
        }
    
    def plot_results(self, save_path: str = 'backtest_chart.png'):
        """
        Create a graph showing bankroll progression over time.
        
        Args:
            save_path: Path to save the chart image
        """
        try:
            print(f"\n📊 Generating bankroll chart...")
            
            print(f"   Timestamps: {len(self.bankroll_timestamps)}")
            print(f"   Bankroll history: {len(self.bankroll_history)}")
            
            if not self.bankroll_timestamps or not self.bankroll_history:
                print("   ⚠️ No data to plot - timestamps or history is empty")
                return
            
            # Convert timestamps to datetime objects
            from datetime import datetime, timedelta
            from collections import OrderedDict
            import numpy as np
            
            # Prepend initial timestamp (use first bet time or arbitrary start if no bets)
            if self.bankroll_timestamps:
                first_timestamp = self._parse_timestamp(self.bankroll_timestamps[0])
                # Use a time slightly before the first bet to show initial bankroll
                initial_timestamp = first_timestamp - timedelta(minutes=1)
            else:
                # No bets placed, use current time
                initial_timestamp = datetime.now()
            
            # Create full timestamp list including initial bankroll point
            all_timestamps = [initial_timestamp] + [self._parse_timestamp(ts) for ts in self.bankroll_timestamps]
            dates = all_timestamps
            print(f"   Converted {len(dates)} timestamps to dates (including initial bankroll)")
            
            # Sort by timestamp to fix out-of-order bets
            sorted_data = sorted(zip(dates, self.bankroll_history), key=lambda x: x[0])
            dates = [d for d, _ in sorted_data]
            bankroll_values = [b for _, b in sorted_data]
            
            print(f"   Sorted {len(dates)} data points chronologically")
            
            # Aggregate by hour - keep last bankroll value for each hour
            hourly_data = OrderedDict()
            for date, bankroll in zip(dates, bankroll_values):
                # Round down to the hour
                hour_key = date.replace(minute=0, second=0, microsecond=0)
                hourly_data[hour_key] = bankroll
            
            # Convert to lists
            plot_dates = list(hourly_data.keys())
            plot_bankroll = list(hourly_data.values())
            
            print(f"   Aggregated to {len(plot_dates)} daily data points")
            
            # Apply smoothing with a simple moving average if we have enough data points
            if len(plot_bankroll) > 3:
                window = min(3, len(plot_bankroll) // 5)  # Adaptive window size
                if window > 1:
                    smoothed = np.convolve(plot_bankroll, np.ones(window)/window, mode='valid')
                    # Adjust dates to match smoothed data
                    offset = window // 2
                    smoothed_dates = plot_dates[offset:offset+len(smoothed)]
                    plot_dates = smoothed_dates
                    plot_bankroll = smoothed.tolist()
                    print(f"   Applied smoothing with window size {window}")
            
            # Calculate daily bet volume
            bet_volume_by_day = OrderedDict()
            for bet in self.bets_placed:
                if 'bet_placed_at' in bet and bet['bet_placed_at']:
                    bet_date = self._parse_timestamp(bet['bet_placed_at'])
                    # Group by day
                    day_key = bet_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    bet_volume_by_day[day_key] = bet_volume_by_day.get(day_key, 0) + 1
            
            volume_dates = list(bet_volume_by_day.keys())
            volume_counts = list(bet_volume_by_day.values())
            print(f"   Calculated bet volume for {len(volume_dates)} days")
            
            # Create figure with subplots - bankroll on top, volume on bottom
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), 
                                           gridspec_kw={'height_ratios': [3, 1]})
            
            # Plot smoothed bankroll progression on top subplot
            ax1.plot(plot_dates, plot_bankroll, 
                    linewidth=3, color='#2E86AB', label='Bankroll (smoothed)', alpha=0.9)
            
            # Add horizontal line for initial bankroll
            ax1.axhline(y=self.initial_bankroll, color='gray', linestyle='--', 
                        linewidth=1, alpha=0.7, label='Initial Bankroll')
            
            # Calculate statistics for annotations
            final_bankroll = self.bankroll_history[-1]
            total_return = ((final_bankroll - self.initial_bankroll) / self.initial_bankroll) * 100
            max_bankroll = max(self.bankroll_history)
            min_bankroll = min(self.bankroll_history)
            
            # Calculate max drawdown percentage
            peak = self.initial_bankroll
            max_drawdown_pct = 0
            for br in self.bankroll_history:
                if br > peak:
                    peak = br
                drawdown_pct = (peak - br) / peak * 100 if peak > 0 else 0
                if drawdown_pct > max_drawdown_pct:
                    max_drawdown_pct = drawdown_pct
            
            # Calculate bet statistics (only settled bets)
            settled_bets = [b for b in self.bets_placed if b.get('result') is not None]
            total_bets = len(settled_bets)
            won_bets = sum(1 for b in settled_bets if b.get('result') == 'won')
            win_rate = (won_bets / total_bets * 100) if total_bets > 0 else 0
            
            total_staked = sum(b['stake'] for b in settled_bets) if settled_bets else 0
            total_profit = sum(b.get('actual_profit', 0) for b in settled_bets) if settled_bets else 0
            roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
            
            # Add annotations for key stats (multi-line title for readability)
            ax1.set_title(f'Backtest Results: Bankroll Progression\n'
                      f'Bets: {total_bets} | Win Rate: {win_rate:.1f}% | ROI: {roi:.2f}% | '
                      f'Return: {total_return:+.2f}%\n'
                      f'Max Drawdown: {max_drawdown_pct:.2f}% | Final: £{final_bankroll:.2f} | '
                      f'Peak: £{max_bankroll:.2f}',
                      fontsize=13, fontweight='bold', pad=20)
            
            # Formatting for top subplot
            ax1.set_ylabel('Bankroll (£)', fontsize=12, fontweight='bold')
            ax1.grid(True, alpha=0.3, linestyle='--')
            ax1.legend(loc='best', fontsize=10)
            
            # Plot bet volume bar chart on bottom subplot
            ax2.bar(volume_dates, volume_counts, width=0.8, 
                   color='#A23B72', alpha=0.7, edgecolor='#6B1E45', linewidth=0.5)
            ax2.set_ylabel('Bets Placed', fontsize=12, fontweight='bold')
            ax2.set_xlabel('Date', fontsize=12, fontweight='bold')
            ax2.grid(True, alpha=0.3, linestyle='--', axis='y')
            
            # Format x-axis dates for both subplots
            fig.autofmt_xdate()
            from matplotlib.dates import DateFormatter
            ax1.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
            ax2.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
            
            # Tight layout to prevent label cutoff
            plt.tight_layout()
            
            # Save the figure
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"   ✅ Chart saved to: {save_path}")
            
            # Close to free memory
            plt.close()
        except Exception as e:
            print(f"   ❌ Error generating chart: {e}")
            import traceback
            traceback.print_exc()
    
    def export_bets_to_csv(self, filename: str = 'data/backtest_bet_history.csv'):
        """
        Export all placed bets to a CSV file.
        
        Args:
            filename: Path to save the CSV file
        """
        if not self.bets_placed:
            print("⚠️  No bets to export")
            return
        
        # Ensure directory exists
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        # Define CSV headers (similar to BetLogger)
        headers = [
            'timestamp',
            'date_placed',
            'game_id',
            'sport',
            'game',
            'commence_time',
            'market',
            'outcome',
            'bookmaker',
            'bookmaker_key',
            'bet_odds',
            'sharp_avg_odds',
            'true_probability_pct',
            'ev_percentage',
            'bankroll',
            'kelly_percentage',
            'recommended_stake',
            'expected_profit',
            'bet_result',
            'actual_profit_loss',
            'bankroll_after'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                for bet in self.bets_placed:
                    row = {
                        'timestamp': bet.get('bet_placed_at', ''),
                        'date_placed': bet.get('bet_placed_at', '')[:10] if bet.get('bet_placed_at') else '',
                        'game_id': bet.get('game_id', ''),
                        'sport': bet.get('sport', ''),
                        'game': bet.get('game', ''),
                        'commence_time': bet.get('commence_time', ''),
                        'market': bet.get('market', ''),
                        'outcome': bet.get('outcome', ''),
                        'bookmaker': bet.get('bookmaker', ''),
                        'bookmaker_key': bet.get('bookmaker_key', ''),
                        'bet_odds': bet.get('odds', 0),
                        'sharp_avg_odds': bet.get('sharp_avg_odds', 0),
                        'true_probability_pct': bet.get('true_probability', 0) * 100,
                        'ev_percentage': bet.get('ev', 0) * 100,
                        'bankroll': self.initial_bankroll,  # Always initial bankroll for sizing
                        'kelly_percentage': bet.get('kelly_pct', 0) * 100,
                        'recommended_stake': bet.get('stake', 0),
                        'expected_profit': bet.get('expected_profit', 0),
                        'bet_result': bet.get('result', 'pending'),
                        'actual_profit_loss': bet.get('actual_profit', 0),
                        'bankroll_after': bet.get('bankroll_after', 0)
                    }
                    writer.writerow(row)
            
            print(f"💾 Exported {len(self.bets_placed)} bets to {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting bets to CSV: {e}")
    
    def save_results(self, results: Dict, filename: str = 'backtest_results.json'):
        """Save backtest results to file."""
        with open(filename, 'w') as f:
            # Convert to JSON-serializable format
            output = {k: v for k, v in results.items() if k != 'bets'}
            # Only add bets_sample if 'bets' key exists (single backtest, not Monte Carlo)
            if 'bets' in results:
                output['bets_sample'] = results['bets'][:10]  # Save first 10 bets as sample
            json.dump(output, f, indent=2)
        
        print(f"💾 Results saved to {filename}")


def main():
    """Main function to run backtester."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Backtest betting strategy using historical odds data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backtest EPL for January 2024, 12-hour snapshots
  python backtest.py --sport soccer_epl --start 2024-01-01 --end 2024-01-31
  
  # Backtest La Liga for Q1 2024, 24-hour snapshots
  python backtest.py --sport soccer_spain_la_liga --start 2024-01-01 --end 2024-03-31 --interval 24
  
  # Short test: 1 week of EPL
  python backtest.py --sport soccer_epl --start 2024-01-01 --end 2024-01-07 --interval 24

Note: Historical data costs 10 API credits per request. 
A 30-day backtest with 12-hour intervals = ~60 requests = 600 credits.
        """
    )
    
    parser.add_argument(
        '--sport', '-s',
        type=str,
        default=None,
        help='Sport key (default: from BETTING_SPORTS in .env, or soccer_epl). Use comma-separated values for multiple sports.'
    )
    
    parser.add_argument(
        '--start',
        type=str,
        required=True,
        help='Start date (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        required=True,
        help='End date (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=12,
        help='Hours between snapshots (default: 12)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='backtest_results.json',
        help='Output filename (default: backtest_results.json)'
    )
    
    parser.add_argument(
        '--google-search',
        action='store_true',
        help='Use SerpAPI to fetch real game results from Google Sports (requires SERPAPI_KEY in .env, 100 free/month)'
    )
    
    args = parser.parse_args()
    
    # Determine sports to backtest
    if args.sport:
        # Use command-line argument (can be comma-separated)
        sports = [s.strip() for s in args.sport.split(',')]
    else:
        # Use BETTING_SPORTS from .env
        betting_sports_str = os.getenv('BETTING_SPORTS', 'soccer_epl')
        sports = [s.strip() for s in betting_sports_str.split(',')]
    
    print(f"🏆 Sports to backtest: {', '.join(sports)}\n")
    
    # Validate dates
    try:
        start_date = datetime.fromisoformat(args.start).date().isoformat()
        end_date = datetime.fromisoformat(args.end).date().isoformat()
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD")
        return
    
    # Calculate estimated cost
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    days = (end - start).days
    total_hours = days * 24
    snapshots = int(total_hours / args.interval) + 1
    cost_per_sport = snapshots * 10
    total_cost = cost_per_sport * len(sports)
    
    print(f"\n⚠️  ESTIMATED COST:")
    print(f"   Days: {days}")
    print(f"   Sports: {len(sports)}")
    print(f"   Snapshots per sport: {snapshots}")
    print(f"   Total snapshots: {snapshots * len(sports)}")
    print(f"   API Credits: {total_cost}")
    print(f"   (Each snapshot costs 10 credits)\n")
    
    response = input("Continue with backtest? (y/n): ").lower().strip()
    if response != 'y':
        print("Backtest cancelled.")
        return
    
    # Run backtest with all sports together
    backtester = HistoricalBacktester(use_google_search=args.google_search)
    
    # Run backtest with all sports together
    backtester = HistoricalBacktester(use_google_search=args.google_search)
    
    # Run single backtest with Google results
    results = backtester.backtest(
        sports=sports,
        start_date=start_date,
        end_date=end_date,
        snapshot_interval_hours=args.interval
    )
    
    if results:
        backtester.save_results(results, args.output)
        
        # Generate chart
        print("\n🎨 Preparing to generate visualization...")
        chart_path = args.output.replace('.json', '_chart.png')
        print(f"   Chart will be saved to: {chart_path}")
        backtester.plot_results(chart_path)
        
        print("\n💡 TIP: Compare these results with your simulator:")
        print(f"   Actual Avg EV: {results['avg_ev']*100:.2f}% vs Simulator: 2.91%")
        print(f"   Actual Avg Odds: {results['avg_odds']:.2f} vs Simulator: 1.235")
        print(f"   Actual Win Rate: {results['win_rate']*100:.1f}% vs Expected: 83%")
        print(f"   Actual Avg True Prob: {results['avg_true_prob']*100:.1f}% vs Simulator: 83%")


if __name__ == '__main__':
    main()
