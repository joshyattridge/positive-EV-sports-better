"""
Historical Backtesting Tool

Simplified backtest using requests-cache for automatic HTTP caching.
Backtests your positive EV betting strategy using real historical odds data.
"""

import os
import requests
import requests_cache
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from dotenv import load_dotenv
import json
from pathlib import Path
from src.core.positive_ev_scanner import PositiveEVScanner
from src.utils.google_search_scraper import GoogleSearchScraper
from src.utils.espn_scores import ESPNScoresFetcher
from src.utils.bet_settler import BetSettler
from src.utils.bet_logger import BetLogger
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

# Create cached session for HTTP requests
cached_session = requests_cache.CachedSession(
    'data/backtest_cache/api_cache',
    backend='sqlite',
    expire_after=None,  # Never expire for historical data
    cache_control=False,  # Ignore Cache-Control headers
    allowable_codes=(200, 404, 422),  # Cache all responses including errors
    ignored_parameters=['apiKey']  # Don't include API key in cache key
)


class HistoricalBacktester:
    """Backtest betting strategy using historical odds data."""
    
    def __init__(self, test_mode: bool = False):
        """Initialize backtester with scanner."""
        self.api_key = os.getenv('ODDS_API_KEY')
        if not self.api_key:
            raise ValueError("ODDS_API_KEY must be set in .env file")
        
        self.base_url = "https://api.the-odds-api.com/v4"
        
        # Initialize scanner
        self.scanner = PositiveEVScanner(api_key=self.api_key)
        
        # Initialize ESPN + SerpAPI for real results
        try:
            self.google_scraper = GoogleSearchScraper()
            self.espn_scraper = ESPNScoresFetcher(serpapi_fallback=self.google_scraper)
            print("✅ ESPN API enabled for real game results")
        except ValueError as e:
            print(f"⚠️  ESPN/SerpAPI not configured: {e}")
            raise
        
        # Store initial bankroll
        self.initial_bankroll = self.scanner.kelly.bankroll
        
        # Initialize bet logger
        self.bet_logger = BetLogger(
            log_path="data/backtest_bet_history.csv", 
            test_mode=test_mode, 
            reset=True
        )
        
        # Track results
        self.bets_placed = []
        self.bankroll_history = [self.initial_bankroll]
        self.bankroll_timestamps = []
        self.current_bankroll = self.initial_bankroll
        self.outcomes_bet_on = set()
        self.game_results_cache = {}
        
    def reset_state(self):
        """Reset backtester state for new run."""
        self.bets_placed = []
        self.bankroll_history = [self.initial_bankroll]
        self.bankroll_timestamps = []
        self.current_bankroll = self.initial_bankroll
        self.outcomes_bet_on = set()
        self.game_results_cache = {}
        self.scanner.kelly.bankroll = self.initial_bankroll
    
    def _parse_timestamp(self, ts: str) -> datetime:
        """Parse timestamp string to timezone-aware datetime."""
        if 'Z' in ts:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        if ' UTC' in ts:
            dt = datetime.strptime(ts.replace(' UTC', ''), '%Y-%m-%d %H:%M')
            return dt.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            return dt.replace(tzinfo=timezone.utc)
    
    def get_historical_odds(self, sport: str, date: str) -> Optional[Dict]:
        """
        Get historical odds for a specific date.
        Uses requests-cache for automatic caching.
        Fetches markets individually to avoid 422 errors.
        """
        url = f"{self.base_url}/historical/sports/{sport}/odds"
        params = {
            'apiKey': self.api_key,
            'bookmakers': ','.join(self.scanner.optimized_bookmakers),
            'markets': self.scanner.markets,
            'oddsFormat': self.scanner.odds_format,
            'date': date
        }
        
        # Fetch markets individually (API often returns 422 for combined markets)
        return self._fetch_markets_individually(url, params)
    
    def _fetch_markets_individually(self, url: str, params: dict) -> Optional[Dict]:
        """Fetch markets individually when combined request fails."""
        market_list = [m.strip() for m in self.scanner.markets.split(',')]
        if len(market_list) <= 1:
            return None
        
        combined_data = {'data': []}
        game_dict = {}
        
        for market in market_list:
            try:
                # Create new params dict for each market to avoid mutation
                market_params = params.copy()
                market_params['markets'] = market
                response = cached_session.get(url, params=market_params, timeout=10)
                response.raise_for_status()
                market_data = response.json()
                
                if market_data and 'data' in market_data:
                    for game in market_data['data']:
                        game_id = game.get('id')
                        if game_id in game_dict:
                            # Merge bookmakers
                            existing_game = game_dict[game_id]
                            for bookmaker in game.get('bookmakers', []):
                                existing_bookmaker = next(
                                    (b for b in existing_game.get('bookmakers', []) 
                                     if b['key'] == bookmaker['key']),
                                    None
                                )
                                if existing_bookmaker:
                                    existing_bookmaker['markets'].extend(bookmaker.get('markets', []))
                                else:
                                    existing_game.setdefault('bookmakers', []).append(bookmaker)
                        else:
                            game_dict[game_id] = game
                            combined_data['data'].append(game)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    print(f"⚠️  Rate limit hit for market '{market}'")
                continue
            except Exception:
                continue
        
        return combined_data if combined_data['data'] else None
    
    def find_positive_ev_bets(self, historical_data: Dict, sport: str, 
                             snapshot_time: Optional[datetime] = None) -> List[Dict]:
        """
        Analyze historical odds snapshot to find +EV bets.
        Uses scanner's analyze_games_for_ev() for consistency with live scanning.
        """
        if not historical_data or 'data' not in historical_data:
            return []
        
        # Keep scanner's Kelly bankroll at initial value
        self.scanner.kelly.bankroll = self.initial_bankroll
        
        opportunities = self.scanner.analyze_games_for_ev(
            games=historical_data['data'],
            sport=sport,
            reference_time=snapshot_time
        )
        
        # Convert scanner's output format
        for opp in opportunities:
            if 'ev_percentage' in opp:
                opp['ev'] = opp['ev_percentage'] / 100
            if 'kelly_stake' in opp:
                opp['kelly_pct'] = opp['kelly_stake']['kelly_percentage'] / 100
                opp['stake'] = opp['kelly_stake']['recommended_stake']
            if 'true_probability' in opp and opp['true_probability'] >= 1:
                opp['true_probability'] = opp['true_probability'] / 100
        
        return opportunities
    
    def _prefetch_game_results(self, bets: List[Dict], current_time: datetime):
        """Pre-fetch all unique game results in parallel."""
        unique_games = {}
        
        for bet in bets:
            game_str = bet.get('game', '')
            if ' @ ' not in game_str:
                continue
            
            # Check if game has completed
            commence_time = bet.get('commence_time', '')
            if commence_time and current_time:
                try:
                    game_time = self._parse_timestamp(commence_time) if isinstance(commence_time, str) else commence_time
                    game_completion_time = game_time + timedelta(hours=4)
                    if current_time < game_completion_time:
                        continue
                except Exception:
                    continue
            
            # Extract game info
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
        
        results_cache = {}
        failed_fetches = []
        cache_lock = threading.Lock()
        
        def fetch_one_game(game_key, game_info):
            """Fetch a single game result."""
            try:
                result = self.espn_scraper.get_game_result(
                    sport=game_info['sport'],
                    team1=game_info['away_team'],
                    team2=game_info['home_team'],
                    game_date=game_info['game_date']
                )
                
                if result:
                    return (game_key, result, None)
                else:
                    return (game_key, None, {
                        'game': f"{game_info['away_team']} @ {game_info['home_team']}",
                        'sport': game_info['sport'],
                        'date': str(game_info['game_date'].date()),
                        'reason': 'No result returned'
                    })
            except Exception as e:
                return (game_key, None, {
                    'game': f"{game_info['away_team']} @ {game_info['home_team']}",
                    'sport': game_info['sport'],
                    'date': str(game_info['game_date'].date()),
                    'reason': f'{type(e).__name__}: {str(e)}'
                })
        
        pbar = tqdm(total=len(unique_games), desc="Fetching results", unit="game", ncols=100)
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_game = {
                executor.submit(fetch_one_game, game_key, game_info): (game_key, game_info)
                for game_key, game_info in unique_games.items()
            }
            
            for future in as_completed(future_to_game):
                game_key, result, failure = future.result()
                
                if result:
                    with cache_lock:
                        results_cache[game_key] = result
                elif failure:
                    with cache_lock:
                        failed_fetches.append(failure)
                
                pbar.update(1)
        
        pbar.close()
        
        # Store in cache
        self.game_results_cache.update(results_cache)
        print(f"   ✅ Cached {len(results_cache)} game results")
        
        if failed_fetches:
            print(f"   ⚠️  Failed to fetch {len(failed_fetches)} games")
            Path('data/settlement_failures.json').write_text(json.dumps(failed_fetches, indent=2))
    
    def determine_bet_result(self, bet: Dict, current_time: Optional[datetime] = None) -> Optional[str]:
        """Determine if a bet won or lost based on actual game results."""
        # Anti-look-ahead protection
        commence_time = bet.get('commence_time', '')
        if commence_time and current_time:
            try:
                game_time = self._parse_timestamp(commence_time) if isinstance(commence_time, str) else commence_time
                game_completion_time = game_time + timedelta(hours=4)
                if current_time < game_completion_time:
                    return None
            except Exception:
                return None
        
        # Try ESPN API
        if self.espn_scraper:
            try:
                game_str = bet.get('game', '')
                if ' @ ' in game_str:
                    away_team, home_team = game_str.split(' @ ')
                    away_team = away_team.strip()
                    home_team = home_team.strip()
                    sport = bet.get('sport', '')
                    
                    if commence_time:
                        game_date = self._parse_timestamp(commence_time)
                        
                        # Check cache first
                        game_key = f"{sport}|{away_team}|{home_team}|{game_date.date()}"
                        result = self.game_results_cache.get(game_key)
                        
                        # Fetch if not cached
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
                            
                            # Use BetSettler to determine result
                            return BetSettler.determine_bet_result_backtest(
                                bet=bet,
                                home_team=home_team,
                                away_team=away_team,
                                home_score=home_score,
                                away_score=away_score,
                                espn_home=espn_home,
                                espn_away=espn_away
                            )
            except Exception:
                pass
        
        return None
    
    def place_bet(self, bet: Dict, result: Optional[str] = None, bet_timestamp: Optional[str] = None):
        """Simulate placing a bet and update bankroll when settled."""
        stake = bet['stake']
        
        # Store timestamp
        bet_placed_timestamp = bet.get('bet_placed_at', bet_timestamp)
        if bet_placed_timestamp:
            csv_timestamp = bet_placed_timestamp if isinstance(bet_placed_timestamp, str) else bet_placed_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        else:
            csv_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        bet['csv_timestamp'] = csv_timestamp
        
        # Update bankroll for settled bets
        if result == 'won':
            profit = stake * (bet['odds'] - 1)
            self.current_bankroll += profit
            actual_profit = profit
            if bet_timestamp:
                self.bankroll_timestamps.append(bet_timestamp)
                self.bankroll_history.append(self.current_bankroll)
        elif result == 'lost':
            self.current_bankroll -= stake
            actual_profit = -stake
            if bet_timestamp:
                self.bankroll_timestamps.append(bet_timestamp)
                self.bankroll_history.append(self.current_bankroll)
        else:
            actual_profit = 0
        
        bet['result'] = result
        bet['actual_profit'] = actual_profit
        bet['bankroll_after'] = self.current_bankroll if result is not None else None
        
        self.bets_placed.append(bet)
        
        # Log to CSV
        if result is None:
            self.bet_logger.log_bet(bet, bet_placed=True, notes="Backtest", timestamp=csv_timestamp)
        else:
            self.bet_logger.log_bet(bet, bet_placed=True, notes="Backtest", timestamp=csv_timestamp)
            bet_result_status = 'win' if result == 'won' else 'loss' if result == 'lost' else 'void'
            self.bet_logger.update_bet_result(
                timestamp=csv_timestamp,
                result=bet_result_status,
                actual_profit_loss=actual_profit,
                notes=f"Settled: {result}"
            )
    
    def backtest(self, sports: List[str], start_date: str, end_date: str, 
                 snapshot_interval_hours: int = 12) -> Dict:
        """Run backtest over a date range."""
        if isinstance(sports, str):
            sports = [sports]
        
        print(f"\n{'='*80}")
        print(f"HISTORICAL BACKTESTING")
        print(f"{'='*80}")
        print(f"Sports: {', '.join(sports)}")
        print(f"Date Range: {start_date} to {end_date}")
        print(f"Snapshot Interval: {snapshot_interval_hours} hours")
        print(f"Initial Bankroll: £{self.initial_bankroll:.2f}")
        print(f"Kelly Fraction: {self.scanner.kelly_fraction}")
        print(f"Min EV: {self.scanner.min_ev_threshold*100:.1f}%")
        print(f"{'='*80}\n")
        
        # Parse dates
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
        current = start
        
        total_opportunities = 0
        
        # Calculate total snapshots
        total_seconds = (end - start).total_seconds()
        interval_seconds = snapshot_interval_hours * 3600
        total_snapshots = int(total_seconds / interval_seconds) + 1
        total_iterations = total_snapshots * len(sports)
        
        pbar = tqdm(total=total_iterations, desc="Backtesting", unit="check", ncols=120)
        
        # Main backtest loop
        while current <= end:
            timestamp = current.strftime('%Y-%m-%dT%H:%M:%SZ')
            all_opportunities = []
            
            for sport in sports:
                historical_data = self.get_historical_odds(sport, timestamp)
                
                if historical_data:
                    opportunities = self.find_positive_ev_bets(historical_data, sport, snapshot_time=current)

                    for opp in opportunities:
                        opp['sport'] = sport
                    
                    all_opportunities.extend(opportunities)
                
                pbar.update(1)
                pbar.set_postfix({'bets': len(self.bets_placed), 'opps': total_opportunities})
            
            if all_opportunities:
                # Filter already bet outcomes
                new_opportunities = []
                for opp in all_opportunities:
                    outcome_key = (opp['game'], opp['market'], opp['outcome'])
                    if outcome_key not in self.outcomes_bet_on:
                        new_opportunities.append(opp)
                        self.outcomes_bet_on.add(outcome_key)
                
                if new_opportunities:
                    total_opportunities += len(new_opportunities)
                    
                    for opp in new_opportunities:
                        opp['bet_placed_at'] = timestamp
                        self.place_bet(opp, result=None, bet_timestamp=timestamp)
                    
                    pbar.set_postfix({
                        'bets': len(self.bets_placed), 
                        'opps': total_opportunities,
                        'bankroll': f'£{self.current_bankroll:.0f}'
                    })
            
            current += timedelta(hours=snapshot_interval_hours)
        
        pbar.close()
        
        # Settle pending bets
        pending_bets = [b for b in self.bets_placed if b.get('result') is None]
        if pending_bets:
            print(f"\n{'='*80}")
            print(f"SETTLING PENDING BETS")
            print(f"{'='*80}")
            print(f"Settling {len(pending_bets)} pending bets...\n")
            
            # Pre-fetch results
            if self.espn_scraper:
                print("⚡ Pre-fetching game results...")
                self._prefetch_game_results(pending_bets, end)
                print()
            
            settled_count = 0
            failed_count = 0
            csv_updates = {}
            
            # Determine results in parallel
            print("⚡ Determining bet results...")
            bet_results = {}
            results_lock = threading.Lock()
            
            def determine_result_batch(bet_index, bet):
                result = self.determine_bet_result(bet, current_time=end)
                return (bet_index, result)
            
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {
                    executor.submit(determine_result_batch, i, bet): i 
                    for i, bet in enumerate(pending_bets)
                }
                
                result_pbar = tqdm(total=len(pending_bets), desc="Determining results", unit="bet", ncols=120)
                for future in as_completed(futures):
                    bet_index, result = future.result()
                    with results_lock:
                        bet_results[bet_index] = result
                    result_pbar.update(1)
                result_pbar.close()
            
            print(f"✅ Determined {len(bet_results)} results. Applying...\n")
            
            # Apply results sequentially
            settle_pbar = tqdm(enumerate(pending_bets), total=len(pending_bets), 
                             desc="Applying results", unit="bet", ncols=120)
            
            for i, bet in settle_pbar:
                result = bet_results.get(i)
                
                if result is not None:
                    bet['result'] = result
                    
                    if result == 'won':
                        profit = bet['stake'] * (bet['odds'] - 1)
                        self.current_bankroll += profit
                        bet['actual_profit'] = profit
                    else:
                        self.current_bankroll -= bet['stake']
                        bet['actual_profit'] = -bet['stake']
                    
                    bet['bankroll_after'] = self.current_bankroll
                    
                    bet_time = bet.get('bet_placed_at') or bet.get('commence_time') or datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
                    self.bankroll_timestamps.append(bet_time)
                    self.bankroll_history.append(self.current_bankroll)
                    
                    csv_timestamp = bet.get('csv_timestamp')
                    if csv_timestamp:
                        bet_result_status = 'win' if result == 'won' else 'loss'
                        csv_updates[csv_timestamp] = (
                            bet_result_status,
                            bet['actual_profit'],
                            "Settled via ESPN"
                        )
                    
                    settled_count += 1
                else:
                    failed_count += 1
                
                settle_pbar.set_postfix({'settled': settled_count, 'failed': failed_count})
            
            settle_pbar.close()
            
            # Batch update CSV
            if csv_updates:
                print(f"\n💾 Writing {len(csv_updates)} bet results to CSV...")
                updated = self.bet_logger.batch_update_bet_results(csv_updates)
                print(f"✅ Updated {updated} bets in CSV file")
            
            print(f"\n✅ Settled {settled_count} bets")
            if failed_count > 0:
                print(f"❌ Failed to settle {failed_count} bets")
            print()
        
        # Print ESPN stats
        if self.espn_scraper:
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
        
        settled_bets = [b for b in self.bets_placed if b.get('result') is not None]
        pending_bets = [b for b in self.bets_placed if b.get('result') is None]
        
        total_bets = len(settled_bets)
        pending_count = len(pending_bets)
        
        if total_bets == 0:
            print("No settled bets found.")
            if pending_count > 0:
                print(f"All {pending_count} bets are pending.")
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
        
        # Stats
        avg_ev = sum(b['ev'] for b in settled_bets) / total_bets
        avg_odds = sum(b['odds'] for b in settled_bets) / total_bets
        avg_prob = sum(b['true_probability'] for b in settled_bets) / total_bets
        
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
        
        print(f"\nBet Characteristics:")
        print(f"  Avg Odds: {avg_odds:.3f}")
        print(f"  Avg True Probability: {avg_prob*100:.1f}%")
        print(f"  Avg EV: {avg_ev*100:.2f}%")
        
        print(f"\nRisk Metrics:")
        print(f"  Max Drawdown: £{max_drawdown:.2f} ({max_drawdown_pct:.2f}%)")
        
        print(f"\n💾 Bets logged to data/backtest_bet_history.csv")
        
        # Per-sport breakdown
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
    
    def save_results(self, results: Dict, filename: str = 'backtest_results.json'):
        """Save backtest results to file."""
        with open(filename, 'w') as f:
            output = {k: v for k, v in results.items() if k != 'bets'}
            if 'bets' in results:
                output['bets_sample'] = results['bets'][:10]
            json.dump(output, f, indent=2)
        
        print(f"💾 Results saved to {filename}")


def main():
    """Main function to run backtester."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Backtest betting strategy using historical odds data'
    )
    
    parser.add_argument('--sport', '-s', type=str, default=None,
                       help='Sport key (comma-separated for multiple sports)')
    parser.add_argument('--start', type=str, required=True,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True,
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--interval', type=int, default=12,
                       help='Hours between snapshots (default: 12, min: 6)')
    parser.add_argument('--output', '-o', type=str, default='backtest_results.json',
                       help='Output filename')
    
    args = parser.parse_args()
    
    # Determine sports
    if args.sport:
        sports = [s.strip() for s in args.sport.split(',')]
    else:
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
    
    # Calculate cost estimate
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    days = (end - start).days
    total_hours = days * 24
    snapshots = int(total_hours / args.interval) + 1
    total_cost = snapshots * len(sports) * 10
    
    print(f"\n⚠️  ESTIMATED COST:")
    print(f"   Days: {days}")
    print(f"   Sports: {len(sports)}")
    print(f"   Snapshots per sport: {snapshots}")
    print(f"   API Credits: {total_cost}\n")
    
    response = input("Continue with backtest? (y/n): ").lower().strip()
    if response != 'y':
        print("Backtest cancelled.")
        return
    
    # Run backtest
    backtester = HistoricalBacktester()
    results = backtester.backtest(
        sports=sports,
        start_date=start_date,
        end_date=end_date,
        snapshot_interval_hours=args.interval
    )
    
    if results:
        backtester.save_results(results, args.output)


if __name__ == '__main__':
    main()
