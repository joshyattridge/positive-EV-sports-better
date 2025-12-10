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
from pathlib import Path
from src.core.kelly_criterion import KellyCriterion
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

load_dotenv()


class HistoricalBacktester:
    """
    Backtest betting strategy using historical odds data.
    """
    
    def __init__(self):
        """Initialize backtester with parameters from .env."""
        self.api_key = os.getenv('ODDS_API_KEY')
        if not self.api_key:
            raise ValueError("ODDS_API_KEY must be set in .env file")
        
        self.base_url = "https://api.the-odds-api.com/v4"
        
        # Create cache directory
        self.cache_dir = Path('data/backtest_cache')
        self.cache_dir.mkdir(exist_ok=True)
        
        # Strategy parameters from .env
        self.initial_bankroll = float(os.getenv('BANKROLL', '10'))
        self.kelly_fraction = float(os.getenv('KELLY_FRACTION', '0.25'))
        self.min_ev_threshold = float(os.getenv('MIN_EV_THRESHOLD', '0.03'))
        self.min_true_probability = float(os.getenv('MIN_TRUE_PROBABILITY', '0.40'))
        self.min_kelly_percentage = float(os.getenv('MIN_KELLY_PERCENTAGE', '0.0'))
        
        # Sharp and betting bookmakers
        sharp_books_str = os.getenv('SHARP_BOOKS', 'pinnacle')
        self.sharp_books = [book.strip() for book in sharp_books_str.split(',')]
        
        betting_bookmakers_str = os.getenv('BETTING_BOOKMAKERS', 'bet365,williamhill,paddypower,sport888')
        self.betting_bookmakers = [book.strip() for book in betting_bookmakers_str.split(',')]
        
        # One bet per game filter
        self.one_bet_per_game = os.getenv('ONE_BET_PER_GAME', 'true').lower() == 'true'
        
        self.kelly = KellyCriterion(self.initial_bankroll)
        
        # Track results
        self.bets_placed = []
        self.bankroll_history = [self.initial_bankroll]
        self.bankroll_timestamps = []
        self.current_bankroll = self.initial_bankroll
        self.games_bet_on = set()  # Track which games we've already bet on
        
        # Monte Carlo tracking
        self.all_simulations = []  # Store all simulation runs
        
    def reset_state(self):
        """Reset backtester state for new Monte Carlo run."""
        self.bets_placed = []
        self.bankroll_history = [self.initial_bankroll]
        self.bankroll_timestamps = []
        self.current_bankroll = self.initial_bankroll
        self.games_bet_on = set()
        
    def _get_cache_key(self, sport: str, date: str, markets: str) -> str:
        """Generate a cache key for the API request."""
        key_str = f"{sport}_{date}_{markets}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Load data from cache if it exists."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
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
        except Exception as e:
            print(f"  Warning: Failed to save cache: {e}")
        
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
            print(f"  💾 Loaded from cache")
            return (cached_data, True)
        
        # Fetch from API
        url = f"{self.base_url}/historical/sports/{sport}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': 'uk,eu',
            'markets': markets,
            'oddsFormat': 'decimal',
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
            print(f"  ❌ Error fetching historical odds: {e}")
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
        # Check cache first
        cache_key = self._get_cache_key(sport, f"scores_{date_from}_{date_to}", "scores")
        cached_data = self._load_from_cache(cache_key)
        
        if cached_data:
            print(f"💾 Loaded scores from cache")
            return cached_data
        
        # Fetch historical odds which include scores for completed games
        # We fetch one snapshot well after the period to ensure all games have completed
        end_date = datetime.fromisoformat(date_to)
        snapshot_time = (end_date + timedelta(days=90)).isoformat()  # 90 days after to ensure all games are completed
        
        result = self.get_historical_odds(sport, snapshot_time)
        if not result:
            print(f"  ⚠️  No historical data available for scores")
            return []
        
        historical_data, was_cached = result
        
        if not historical_data or 'data' not in historical_data:
            print(f"  ⚠️  No historical data available for scores")
            return []
        
        # Extract scores from historical data
        scores = []
        total_games = len(historical_data.get('data', []))
        for game in historical_data['data']:
            if game.get('completed', False) and game.get('scores'):
                scores.append(game)
        
        print(f"✅ Loaded {len(scores)} completed games out of {total_games} total games")
        if len(scores) == 0 and total_games > 0:
            print(f"   ⚠️  Warning: Found {total_games} games but none are marked as completed")
        
        # Save to cache
        self._save_to_cache(cache_key, scores)
        
        return scores
    
    def calculate_implied_probability(self, decimal_odds: float) -> float:
        """Calculate implied probability from decimal odds."""
        return 1 / decimal_odds
    
    def calculate_ev(self, bet_odds: float, true_probability: float) -> float:
        """Calculate expected value."""
        return (true_probability * (bet_odds - 1)) - (1 - true_probability)
    
    def find_positive_ev_bets(self, historical_data: Dict) -> List[Dict]:
        """
        Analyze historical odds snapshot to find +EV bets.
        
        Args:
            historical_data: Response from historical odds API
            
        Returns:
            List of positive EV betting opportunities
        """
        if not historical_data or 'data' not in historical_data:
            return []
        
        opportunities = []
        games = historical_data['data']
        
        for game in games:
            game_id = game.get('id', '')
            home_team = game['home_team']
            away_team = game['away_team']
            commence_time = game['commence_time']
            
            bookmakers = game.get('bookmakers', [])
            if not bookmakers:
                continue
            
            # Process each market
            for market_type in ['h2h', 'spreads', 'totals']:
                market_data = {}
                
                for bookmaker in bookmakers:
                    for market in bookmaker.get('markets', []):
                        if market['key'] == market_type:
                            for outcome in market.get('outcomes', []):
                                outcome_key = outcome['name']
                                if 'point' in outcome:
                                    outcome_key += f" ({outcome['point']:+.1f})"
                                
                                if outcome_key not in market_data:
                                    market_data[outcome_key] = []
                                
                                market_data[outcome_key].append({
                                    'bookmaker': bookmaker['key'],
                                    'title': bookmaker['title'],
                                    'odds': outcome['price']
                                })
                
                # Find +EV opportunities
                for outcome_name, odds_list in market_data.items():
                    # Get sharp book average
                    sharp_odds = [o['odds'] for o in odds_list if o['bookmaker'] in self.sharp_books]
                    
                    if not sharp_odds:
                        continue
                    
                    sharp_avg = sum(sharp_odds) / len(sharp_odds)
                    true_probability = self.calculate_implied_probability(sharp_avg)
                    
                    # Check betting bookmakers
                    for odds_data in odds_list:
                        if odds_data['bookmaker'] in self.sharp_books:
                            continue
                        
                        if odds_data['bookmaker'] not in self.betting_bookmakers:
                            continue
                        
                        bet_odds = odds_data['odds']
                        ev = self.calculate_ev(bet_odds, true_probability)
                        
                        # Apply filters
                        if ev >= self.min_ev_threshold and true_probability >= self.min_true_probability:
                            # Calculate Kelly stake
                            b = bet_odds - 1
                            p = true_probability
                            q = 1 - p
                            kelly_pct = (b * p - q) / b
                            kelly_pct = kelly_pct * self.kelly_fraction
                            kelly_pct = max(0, min(kelly_pct, 0.25))
                            
                            # Apply minimum Kelly percentage filter
                            if kelly_pct < self.min_kelly_percentage:
                                continue
                            
                            stake = self.current_bankroll * kelly_pct
                            expected_profit = stake * ev
                            
                            opportunities.append({
                                'game_id': game_id,
                                'game': f"{away_team} @ {home_team}",
                                'commence_time': commence_time,
                                'market': market_type,
                                'outcome': outcome_name,
                                'bookmaker': odds_data['title'],
                                'bookmaker_key': odds_data['bookmaker'],
                                'odds': bet_odds,
                                'sharp_avg_odds': sharp_avg,
                                'true_probability': true_probability,
                                'ev': ev,
                                'kelly_pct': kelly_pct,
                                'stake': stake,
                                'expected_profit': expected_profit
                            })
        
        # Filter to one bet per game if enabled
        if self.one_bet_per_game and opportunities:
            # Group by game_id and keep only the highest EV bet per game
            game_bets = {}
            for opp in opportunities:
                game_id = opp['game_id']
                if game_id not in game_bets or opp['ev'] > game_bets[game_id]['ev']:
                    game_bets[game_id] = opp
            opportunities = list(game_bets.values())
        
        return opportunities
    
    def determine_bet_result(self, bet: Dict, scores_data: Dict) -> Optional[str]:
        """
        Determine if a bet won or lost based on actual game results.
        
        Args:
            bet: Bet details
            scores_data: Pre-indexed scores data by game matchup
            
        Returns:
            'won', 'lost', or None if result unknown
        """
        # Look up game in pre-indexed scores data
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
        Simulate placing a bet and update bankroll.
        
        Args:
            bet: Bet details
            result: 'won', 'lost', or None (pending)
            bet_timestamp: When the bet was placed (for charting)
        """
        stake = bet['stake']
        
        if result == 'won':
            profit = stake * (bet['odds'] - 1)
            self.current_bankroll += profit
            actual_profit = profit
        elif result == 'lost':
            self.current_bankroll -= stake
            actual_profit = -stake
        else:
            # Pending - don't update bankroll yet
            actual_profit = 0
        
        bet['result'] = result
        bet['actual_profit'] = actual_profit
        bet['bankroll_after'] = self.current_bankroll
        
        self.bets_placed.append(bet)
        
        # Only record bankroll changes for settled bets
        if result is not None:
            self.bankroll_history.append(self.current_bankroll)
            
            # Record timestamp for graphing - use bet placement time, not game time
            timestamp_to_use = bet_timestamp or bet.get('commence_time')
            if timestamp_to_use:
                self.bankroll_timestamps.append(timestamp_to_use)
    
    def backtest(self, sports: List[str], start_date: str, end_date: str, 
                 snapshot_interval_hours: int = 12, simulate_on_missing: bool = True) -> Dict:
        """
        Run backtest over a date range for one or more sports.
        
        Args:
            sports: List of sport keys (e.g., ['soccer_epl', 'basketball_nba'])
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            snapshot_interval_hours: Hours between snapshots (default 12)
            simulate_on_missing: If True, simulate results when scores unavailable (default True)
            
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
        print(f"Kelly Fraction: {self.kelly_fraction}")
        print(f"Min EV: {self.min_ev_threshold*100:.1f}%")
        print(f"Min True Probability: {self.min_true_probability*100:.1f}%")
        if self.min_kelly_percentage > 0:
            print(f"Min Kelly Percentage: {self.min_kelly_percentage*100:.1f}%")
        print(f"Sharp Books: {', '.join(self.sharp_books)}")
        print(f"Betting Bookmakers: {', '.join(self.betting_bookmakers)}")
        print(f"{'='*80}\n")
        
        # Parse dates
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        current = start
        
        snapshot_count = 0
        total_opportunities = 0
        
        # Get scores for all sports for the entire period (for result determination)
        print("Fetching historical scores for result verification...")
        # Use a longer buffer to ensure all games have completed
        end_plus_buffer = (end + timedelta(days=60)).isoformat()
        scores_data = {}
        
        for sport in sports:
            print(f"  Loading scores for {sport}...")
            scores_list = self.get_historical_scores(sport, start_date, end_plus_buffer)
            
            if scores_list:
                for game in scores_list:
                    matchup = f"{game.get('away_team', '')} @ {game.get('home_team', '')}"
                    scores_data[matchup] = game
        
        if scores_data:
            print(f"✅ Loaded {len(scores_data)} completed games total (indexed)")
            # Show a few sample matchups for debugging
            if scores_data:
                sample_matchups = list(scores_data.keys())[:3]
                print(f"   Sample matchups: {sample_matchups}")
            print()
        else:
            print("⚠️  Warning: Could not fetch scores. All bets will be pending.\n")
        
        print("Scanning historical odds snapshots...\n")
        
        while current <= end:
            snapshot_count += 1
            timestamp = current.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            print(f"[{snapshot_count}] Snapshot: {timestamp}")
            
            # Collect opportunities from all sports for this timestamp
            all_opportunities = []
            any_api_calls = False
            
            for sport in sports:
                # Get historical odds for this sport
                result = self.get_historical_odds(sport, timestamp)
                historical_data, was_cached = result if result else (None, False)
                
                if not was_cached:
                    any_api_calls = True
                
                if historical_data:
                    # Find +EV opportunities
                    opportunities = self.find_positive_ev_bets(historical_data)
                    
                    # Add sport info to each opportunity
                    for opp in opportunities:
                        opp['sport'] = sport
                    
                    all_opportunities.extend(opportunities)
            
            # Smart rate limiting - only wait if we made actual API calls
            if any_api_calls:
                time.sleep(0.1)  # Reduced from 0.5s for faster execution
            
            if all_opportunities:
                # Filter out games we've already bet on
                new_opportunities = []
                for opp in all_opportunities:
                    if opp['game_id'] not in self.games_bet_on:
                        new_opportunities.append(opp)
                        self.games_bet_on.add(opp['game_id'])
                
                if new_opportunities:
                    filtered_count = len(all_opportunities) - len(new_opportunities)
                    print(f"  Found {len(new_opportunities)} +EV opportunities ({filtered_count} filtered - already bet)")
                    total_opportunities += len(new_opportunities)
                    
                    # Batch process all bets for this snapshot
                    import random
                    won_count = 0
                    lost_count = 0
                    pending_count = 0
                    
                    for opp in new_opportunities:
                        # Determine result if available
                        result = self.determine_bet_result(opp, scores_data)
                        
                        # If no result and simulation is enabled, simulate based on true probability
                        if result is None and simulate_on_missing:
                            result = 'won' if random.random() < opp['true_probability'] else 'lost'
                        
                        if result == 'won':
                            won_count += 1
                        elif result == 'lost':
                            lost_count += 1
                        else:
                            pending_count += 1
                        
                        # Store when this bet was placed (discovered), not game time
                        opp['bet_placed_at'] = timestamp
                        self.place_bet(opp, result, bet_timestamp=timestamp)
                    
                    # Print batch summary
                    if pending_count > 0:
                        print(f"    Placed {len(new_opportunities)} bets: {won_count}W-{lost_count}L-{pending_count}P | Bankroll: £{self.current_bankroll:.2f}")
                    else:
                        print(f"    Placed {len(new_opportunities)} bets: {won_count}W-{lost_count}L | Bankroll: £{self.current_bankroll:.2f}")
                else:
                    print(f"  No +EV opportunities found (all filtered - already bet)")
            else:
                print(f"  No +EV opportunities found")
            
            # Move to next snapshot
            current += timedelta(hours=snapshot_interval_hours)
        
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
    
    def plot_results(self, save_path: str = 'backtest_chart.png', show_monte_carlo: bool = False):
        """
        Create a graph showing bankroll progression over time.
        
        Args:
            save_path: Path to save the chart image
            show_monte_carlo: If True, plot all Monte Carlo simulations
        """
        try:
            print(f"\n📊 Generating bankroll chart...")
            
            if show_monte_carlo and self.all_simulations:
                print(f"   Plotting {len(self.all_simulations)} Monte Carlo simulations...")
                self._plot_monte_carlo(save_path)
                return
            
            print(f"   Timestamps: {len(self.bankroll_timestamps)}")
            print(f"   Bankroll history: {len(self.bankroll_history)}")
            
            if not self.bankroll_timestamps or not self.bankroll_history:
                print("   ⚠️ No data to plot - timestamps or history is empty")
                return
            
            # Convert timestamps to datetime objects
            from datetime import datetime, timedelta
            from collections import OrderedDict
            import numpy as np
            
            dates = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in self.bankroll_timestamps]
            print(f"   Converted {len(dates)} timestamps to dates")
            
            # Sort by timestamp to fix out-of-order bets
            sorted_data = sorted(zip(dates, self.bankroll_history[1:]), key=lambda x: x[0])
            dates = [d for d, _ in sorted_data]
            bankroll_values = [b for _, b in sorted_data]
            
            print(f"   Sorted {len(dates)} data points chronologically")
            
            # Aggregate by date - keep last bankroll value for each day
            daily_data = OrderedDict()
            for date, bankroll in zip(dates, bankroll_values):
                date_key = date.date()
                daily_data[date_key] = bankroll
            
            # Convert to lists
            plot_dates = [datetime.combine(d, datetime.min.time()) for d in daily_data.keys()]
            plot_bankroll = list(daily_data.values())
            
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
            
            # Create figure with larger size
            plt.figure(figsize=(14, 8))
            
            # Plot smoothed bankroll progression
            plt.plot(plot_dates, plot_bankroll, 
                    linewidth=3, color='#2E86AB', label='Bankroll (smoothed)', alpha=0.9)
            
            # Add horizontal line for initial bankroll
            plt.axhline(y=self.initial_bankroll, color='gray', linestyle='--', 
                        linewidth=1, alpha=0.7, label='Initial Bankroll')
            
            # Calculate statistics for annotations
            final_bankroll = self.bankroll_history[-1]
            total_return = ((final_bankroll - self.initial_bankroll) / self.initial_bankroll) * 100
            max_bankroll = max(self.bankroll_history)
            min_bankroll = min(self.bankroll_history)
            
            # Add annotations for key stats
            plt.title(f'Backtest Results: Bankroll Progression\n'
                      f'Return: {total_return:+.2f}% | Final: £{final_bankroll:.2f} | '
                      f'Peak: £{max_bankroll:.2f} | Low: £{min_bankroll:.2f}',
                      fontsize=14, fontweight='bold', pad=20)
            
            # Formatting
            plt.xlabel('Date', fontsize=12, fontweight='bold')
            plt.ylabel('Bankroll (£)', fontsize=12, fontweight='bold')
            plt.grid(True, alpha=0.3, linestyle='--')
            plt.legend(loc='best', fontsize=10)
            
            # Format x-axis dates
            plt.gcf().autofmt_xdate()
            from matplotlib.dates import DateFormatter
            ax = plt.gca()
            ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
            
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
    
    def _plot_monte_carlo(self, save_path: str):
        """Plot all Monte Carlo simulations together."""
        import numpy as np
        
        # Create figure
        plt.figure(figsize=(16, 10))
        
        all_final_bankrolls = []
        
        # Plot each simulation
        for i, sim in enumerate(self.all_simulations):
            dates = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in sim['timestamps']]
            
            # Sort by timestamp
            sorted_data = sorted(zip(dates, sim['history'][1:]), key=lambda x: x[0])
            dates = [d for d, _ in sorted_data]
            bankroll_values = [b for _, b in sorted_data]
            
            # Aggregate by date
            from collections import OrderedDict
            daily_data = OrderedDict()
            for date, bankroll in zip(dates, bankroll_values):
                date_key = date.date()
                daily_data[date_key] = bankroll
            
            plot_dates = [datetime.combine(d, datetime.min.time()) for d in daily_data.keys()]
            plot_bankroll = list(daily_data.values())
            
            # Apply smoothing
            if len(plot_bankroll) > 3:
                window = min(3, len(plot_bankroll) // 5)
                if window > 1:
                    smoothed = np.convolve(plot_bankroll, np.ones(window)/window, mode='valid')
                    offset = window // 2
                    smoothed_dates = plot_dates[offset:offset+len(smoothed)]
                    plot_dates = smoothed_dates
                    plot_bankroll = smoothed.tolist()
            
            # Plot with transparency
            alpha = 0.3 if len(self.all_simulations) > 10 else 0.5
            plt.plot(plot_dates, plot_bankroll, linewidth=1.5, alpha=alpha, color='#2E86AB')
            
            all_final_bankrolls.append(sim['history'][-1])
        
        # Calculate statistics
        avg_final = np.mean(all_final_bankrolls)
        median_final = np.median(all_final_bankrolls)
        percentile_5 = np.percentile(all_final_bankrolls, 5)
        percentile_95 = np.percentile(all_final_bankrolls, 95)
        
        avg_return = ((avg_final - self.initial_bankroll) / self.initial_bankroll) * 100
        
        # Add horizontal lines
        plt.axhline(y=self.initial_bankroll, color='gray', linestyle='--', 
                    linewidth=2, alpha=0.7, label='Initial Bankroll')
        plt.axhline(y=avg_final, color='red', linestyle='-', 
                    linewidth=2, alpha=0.8, label=f'Average Final: £{avg_final:.2f}')
        
        # Title with statistics
        plt.title(f'Monte Carlo Backtest Results ({len(self.all_simulations)} Simulations)\n'
                  f'Avg Return: {avg_return:+.2f}% | Median: £{median_final:.2f} | '
                  f'5th-95th Percentile: £{percentile_5:.2f} - £{percentile_95:.2f}',
                  fontsize=14, fontweight='bold', pad=20)
        
        plt.xlabel('Date', fontsize=12, fontweight='bold')
        plt.ylabel('Bankroll (£)', fontsize=12, fontweight='bold')
        plt.grid(True, alpha=0.3, linestyle='--')
        plt.legend(loc='best', fontsize=10)
        
        # Format x-axis
        plt.gcf().autofmt_xdate()
        from matplotlib.dates import DateFormatter
        ax = plt.gca()
        ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"   ✅ Monte Carlo chart saved to: {save_path}")
        print(f"   📈 Statistics:")
        print(f"      Average Final: £{avg_final:.2f} ({avg_return:+.2f}%)")
        print(f"      Median Final: £{median_final:.2f}")
        print(f"      5th Percentile: £{percentile_5:.2f}")
        print(f"      95th Percentile: £{percentile_95:.2f}")
        
        plt.close()
    
    def monte_carlo_backtest(self, sports: List[str], start_date: str, end_date: str,
                            snapshot_interval_hours: int = 12, n_simulations: int = 100) -> Dict:
        """
        Run multiple Monte Carlo simulations of the backtest.
        
        Args:
            sports: List of sport keys (e.g., ['soccer_epl', 'basketball_nba'])
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            snapshot_interval_hours: Hours between snapshots
            n_simulations: Number of Monte Carlo simulations to run
            
        Returns:
            Aggregated results across all simulations
        """
        # Support single sport string for backward compatibility
        if isinstance(sports, str):
            sports = [sports]
        
        print(f"\n{'='*80}")
        print(f"MONTE CARLO BACKTESTING - {n_simulations} SIMULATIONS")
        print(f"{'='*80}")
        print(f"Sports: {', '.join(sports)}")
        print(f"Date Range: {start_date} to {end_date}")
        print(f"Initial Bankroll: £{self.initial_bankroll:.2f}")
        print(f"Kelly Fraction: {self.kelly_fraction}")
        print(f"Min EV: {self.min_ev_threshold*100:.1f}%")
        print(f"Min True Probability: {self.min_true_probability*100:.1f}%")
        if self.min_kelly_percentage > 0:
            print(f"Min Kelly Percentage: {self.min_kelly_percentage*100:.1f}%")
        print(f"Note: Results simulated based on true probabilities (historical scores not available)")
        print(f"{'='*80}\n")
        
        # Store all simulation results
        all_results = []
        
        # Run first simulation to get opportunities data (fetches from API/cache)
        print(f"[Simulation 1/{n_simulations}] Running base simulation...")
        # Note: Historical scores may not be available, so we simulate results
        first_result = self.backtest(sports, start_date, end_date, snapshot_interval_hours, simulate_on_missing=True)
        
        if not first_result:
            print("❌ Base simulation returned no results. Cannot run Monte Carlo simulation.")
            return {}
        
        all_results.append(first_result)
        
        # Store ONLY the settled bets for reuse (ignore pending bets)
        base_opportunities = [b for b in self.bets_placed if b.get('result') is not None]
        pending_count = len([b for b in self.bets_placed if b.get('result') is None])
        
        if not base_opportunities:
            print("❌ No settled betting opportunities found. Cannot run Monte Carlo simulation.")
            if pending_count > 0:
                print(f"   All {pending_count} bets are still pending (games haven't finished yet).")
                print(f"   Try extending the end date or waiting for more games to complete.")
            return {}
        
        print(f"\n✅ Found {len(base_opportunities)} settled betting opportunities")
        if pending_count > 0:
            print(f"   (Excluding {pending_count} pending bets that haven't settled)")
        print(f"Running {n_simulations - 1} additional Monte Carlo simulations...\n")
        
        # Run remaining simulations
        import random
        for sim_num in range(2, n_simulations + 1):
            self.reset_state()
            
            # Re-simulate outcomes for each opportunity
            for opp in base_opportunities:
                # Simulate result based on true probability
                result = 'won' if random.random() < opp['true_probability'] else 'lost'
                # Use the bet placement time, not the game commence time
                self.place_bet(opp.copy(), result, bet_timestamp=opp.get('bet_placed_at', opp.get('commence_time')))
            
            # Store this simulation
            self.all_simulations.append({
                'history': self.bankroll_history.copy(),
                'timestamps': self.bankroll_timestamps.copy(),
                'final_bankroll': self.current_bankroll
            })
            
            all_results.append({
                'final_bankroll': self.current_bankroll,
                'total_return_pct': ((self.current_bankroll - self.initial_bankroll) / self.initial_bankroll) * 100
            })
            
            if sim_num % 10 == 0 or sim_num == n_simulations:
                print(f"  Completed {sim_num}/{n_simulations} simulations...")
        
        # Also add first simulation to all_simulations (use bet placement timestamps)
        self.all_simulations.insert(0, {
            'history': first_result['bankroll_history'],
            'timestamps': [bet.get('bet_placed_at', bet.get('commence_time', '')) for bet in base_opportunities if bet.get('result') is not None],
            'final_bankroll': first_result['final_bankroll']
        })
        
        # Calculate aggregate statistics
        import numpy as np
        final_bankrolls = [r['final_bankroll'] for r in all_results]
        returns = [r['total_return_pct'] for r in all_results]
        
        aggregate = {
            'n_simulations': n_simulations,
            'initial_bankroll': self.initial_bankroll,
            'avg_final_bankroll': np.mean(final_bankrolls),
            'median_final_bankroll': np.median(final_bankrolls),
            'std_final_bankroll': np.std(final_bankrolls),
            'min_final_bankroll': np.min(final_bankrolls),
            'max_final_bankroll': np.max(final_bankrolls),
            'percentile_5': np.percentile(final_bankrolls, 5),
            'percentile_95': np.percentile(final_bankrolls, 95),
            'avg_return_pct': np.mean(returns),
            'median_return_pct': np.median(returns),
            'std_return_pct': np.std(returns),
            'min_return_pct': np.min(returns),
            'max_return_pct': np.max(returns),
            'probability_profit': sum(1 for r in returns if r > 0) / len(returns) * 100,
            'total_bets': len(base_opportunities),
            'first_simulation': first_result
        }
        
        # Print summary
        print(f"\n{'='*80}")
        print(f"MONTE CARLO RESULTS SUMMARY")
        print(f"{'='*80}\n")
        print(f"Simulations: {n_simulations}")
        print(f"Total Bets per Simulation: {aggregate['total_bets']}")
        print(f"\nFinal Bankroll Statistics:")
        print(f"  Average: £{aggregate['avg_final_bankroll']:.2f}")
        print(f"  Median: £{aggregate['median_final_bankroll']:.2f}")
        print(f"  Std Dev: £{aggregate['std_final_bankroll']:.2f}")
        print(f"  Min: £{aggregate['min_final_bankroll']:.2f}")
        print(f"  Max: £{aggregate['max_final_bankroll']:.2f}")
        print(f"  5th Percentile: £{aggregate['percentile_5']:.2f}")
        print(f"  95th Percentile: £{aggregate['percentile_95']:.2f}")
        print(f"\nReturn Statistics:")
        print(f"  Average: {aggregate['avg_return_pct']:+.2f}%")
        print(f"  Median: {aggregate['median_return_pct']:+.2f}%")
        print(f"  Std Dev: {aggregate['std_return_pct']:.2f}%")
        print(f"  Min: {aggregate['min_return_pct']:+.2f}%")
        print(f"  Max: {aggregate['max_return_pct']:+.2f}%")
        print(f"\nProbability of Profit: {aggregate['probability_profit']:.1f}%")
        print(f"\n{'='*80}\n")
        
        return aggregate
    
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
        '--monte-carlo', '-mc',
        type=int,
        default=0,
        help='Run Monte Carlo simulation with N iterations (default: 0 = single run)'
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
    snapshots = int((days * 24) / args.interval)
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
    backtester = HistoricalBacktester()
    
    if args.monte_carlo > 0:
        # Run Monte Carlo simulation
        results = backtester.monte_carlo_backtest(
            sports=sports,
            start_date=start_date,
            end_date=end_date,
            snapshot_interval_hours=args.interval,
            n_simulations=args.monte_carlo
        )
        
        if results:
            # Save results
            backtester.save_results(results, args.output)
            
            # Generate Monte Carlo chart
            print("\n🎨 Preparing to generate Monte Carlo visualization...")
            chart_path = args.output.replace('.json', '_monte_carlo_chart.png')
            print(f"   Chart will be saved to: {chart_path}")
            backtester.plot_results(chart_path, show_monte_carlo=True)
    else:
        # Run single backtest
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
