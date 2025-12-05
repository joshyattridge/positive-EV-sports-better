"""
Positive EV Sports Betting Opportunity Scanner

Uses The Odds API to find positive expected value betting opportunities
by comparing odds across multiple sportsbooks against sharp bookmakers.
"""

import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class PositiveEVScanner:
    """
    Scanner to identify positive expected value betting opportunities
    by comparing odds across sportsbooks.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the scanner with The Odds API key.
        
        Args:
            api_key: Your The Odds API key (optional, will read from .env if not provided)
        """
        # Read from environment variables if not provided
        self.api_key = api_key or os.getenv('ODDS_API_KEY')
        if not self.api_key:
            raise ValueError("ODDS_API_KEY must be provided or set in .env file")
        
        self.base_url = "https://api.the-odds-api.com/v4"
        
        # Sharp bookmakers - read from env or use defaults
        sharp_books_str = os.getenv('SHARP_BOOKS', 'pinnacle,betfair_ex_uk,betfair_ex_eu,betfair_ex_au,matchbook,smarkets')
        self.sharp_books = [book.strip() for book in sharp_books_str.split(',')]
        
        # Betting bookmakers - read from env or use defaults
        betting_bookmakers_str = os.getenv('BETTING_BOOKMAKERS', 'bet365,williamhill,ladbrokes_uk,coral,paddypower,skybet,betway,betvictor,unibet_uk,betfred,888sport')
        self.betting_bookmakers = [book.strip() for book in betting_bookmakers_str.split(',')]
        
        # Minimum EV threshold - read from env or use default
        self.min_ev_threshold = float(os.getenv('MIN_EV_THRESHOLD', '0.02'))
        
        # API regions - read from env or use default
        self.api_regions = os.getenv('API_REGIONS', 'us,uk,eu,au')
        
        # Markets - read from env or use default
        self.markets = os.getenv('MARKETS', 'h2h,spreads,totals')
        
        # Odds format - read from env or use default
        self.odds_format = os.getenv('ODDS_FORMAT', 'decimal')
        
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
    
    def get_odds(self, sport: str, markets: str = 'h2h') -> List[Dict]:
        """
        Get odds for a specific sport.
        
        Args:
            sport: Sport key (e.g., 'americanfootball_nfl')
            markets: Comma-separated markets (h2h, spreads, totals)
            
        Returns:
            List of games with odds from multiple bookmakers
        """
        url = f"{self.base_url}/sports/{sport}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': self.api_regions,
            'markets': markets,
            'oddsFormat': self.odds_format,
            'dateFormat': 'iso',
            'includeLinks': 'true'  # Get bookmaker links to events
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # Print remaining requests
            remaining = response.headers.get('x-requests-remaining')
            if remaining:
                print(f"API Requests Remaining: {remaining}")
            
            return response.json()
        except Exception as e:
            print(f"Error fetching odds for {sport}: {e}")
            return []
    
    def calculate_implied_probability(self, decimal_odds: float) -> float:
        """
        Calculate implied probability from decimal odds.
        
        Args:
            decimal_odds: Odds in decimal format
            
        Returns:
            Implied probability (0 to 1)
        """
        return 1 / decimal_odds
    
    def calculate_ev(self, bet_odds: float, true_probability: float) -> float:
        """
        Calculate expected value of a bet.
        
        Args:
            bet_odds: The odds being offered (decimal)
            true_probability: Estimated true probability of outcome
            
        Returns:
            Expected value as percentage (0.05 = 5% EV)
        """
        return (true_probability * (bet_odds - 1)) - (1 - true_probability)
    
    def generate_bookmaker_link(self, bookmaker_key: str, sport: str, home_team: str, away_team: str) -> str:
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
        import urllib.parse
        
        # Clean up team names for search
        search_query = f"{away_team} {home_team}".replace(" @ ", " ")
        encoded_query = urllib.parse.quote(search_query)
        
        # Bookmaker search URLs (these will search within the bookmaker's site)
        search_urls = {
            'williamhill': f'https://sports.williamhill.com/betting/en-gb/football?q={encoded_query}',
            'ladbrokes_uk': f'https://sports.ladbrokes.com/en-gb/betting/football?q={encoded_query}',
            'coral': f'https://sports.coral.co.uk/en-gb/betting/football?q={encoded_query}',
            'paddypower': f'https://www.paddypower.com/football?q={encoded_query}',
            'skybet': f'https://m.skybet.com/football?search={encoded_query}',
            'betway': f'https://betway.com/en-gb/sports/evt/{encoded_query}',
            'betvictor': f'https://www.betvictor.com/en-gb/sports/football?q={encoded_query}',
            'unibet_uk': f'https://www.unibet.co.uk/betting/sports/filter/all/all/all?search={encoded_query}',
            'betfred': f'https://www.betfred.com/sport/football?q={encoded_query}',
            '888sport': f'https://www.888sport.com/football?q={encoded_query}'
        }
        
        # If bookmaker has a search URL, use it, otherwise create a Google search
        if bookmaker_key in search_urls:
            return search_urls[bookmaker_key]
        else:
            # Fallback: Google search for the game on that bookmaker's site
            site_domains = {
                'williamhill': 'sports.williamhill.com',
                'ladbrokes_uk': 'sports.ladbrokes.com',
                'coral': 'sports.coral.co.uk',
                'paddypower': 'paddypower.com',
                'skybet': 'skybet.com',
                'betway': 'betway.com',
                'betvictor': 'betvictor.com',
                'unibet_uk': 'unibet.co.uk',
                'betfred': 'betfred.com',
                '888sport': '888sport.com'
            }
            domain = site_domains.get(bookmaker_key, bookmaker_key)
            return f'https://www.google.com/search?q={encoded_query}+site:{domain}'
    
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
    
    def find_positive_ev_opportunities(self, sport: str, markets: str = 'h2h') -> List[Dict]:
        """
        Find positive EV opportunities for a sport.
        
        Args:
            sport: Sport key
            markets: Markets to analyze
            
        Returns:
            List of positive EV opportunities
        """
        print(f"\n{'='*80}")
        print(f"Scanning {sport.upper()} for +EV opportunities...")
        print(f"{'='*80}\n")
        
        games = self.get_odds(sport, markets)
        opportunities = []
        
        if not games:
            print("No games found or API error.")
            return opportunities
        
        for game in games:
            # Skip live games
            commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
            if commence_time <= datetime.now(commence_time.tzinfo):
                continue
            
            home_team = game['home_team']
            away_team = game['away_team']
            commence_time_str = commence_time.strftime('%Y-%m-%d %H:%M %Z')
            
            bookmakers = game.get('bookmakers', [])
            
            if not bookmakers:
                continue
            
            # Process each market (h2h, spreads, totals)
            for market_type in ['h2h', 'spreads', 'totals']:
                # Get all outcomes for this market across all bookmakers
                market_data = {}
                
                for bookmaker in bookmakers:
                    for market in bookmaker.get('markets', []):
                        if market['key'] == market_type:
                            # Get the market link if available
                            market_link = market.get('link')
                            
                            for outcome in market.get('outcomes', []):
                                outcome_key = outcome['name']
                                if 'point' in outcome:
                                    outcome_key += f" ({outcome['point']:+.1f})"
                                
                                if outcome_key not in market_data:
                                    market_data[outcome_key] = []
                                
                                market_data[outcome_key].append({
                                    'bookmaker': bookmaker['key'],
                                    'title': bookmaker['title'],
                                    'odds': outcome['price'],
                                    'link': market_link  # Include link from API
                                })
                
                # Analyze each outcome
                for outcome_name, odds_list in market_data.items():
                    # Get sharp book average as baseline
                    sharp_odds = [o['odds'] for o in odds_list if o['bookmaker'] in self.sharp_books]
                    
                    if not sharp_odds:
                        continue
                    
                    sharp_avg = sum(sharp_odds) / len(sharp_odds)
                    true_probability = self.calculate_implied_probability(sharp_avg)
                    
                    # Check each bookmaker's odds
                    for odds_data in odds_list:
                        if odds_data['bookmaker'] in self.sharp_books:
                            continue  # Skip the sharp books themselves
                        
                        # Only show opportunities for betting bookmakers
                        if odds_data['bookmaker'] not in self.betting_bookmakers:
                            continue
                        
                        bet_odds = odds_data['odds']
                        ev = self.calculate_ev(bet_odds, true_probability)
                        
                        if ev >= self.min_ev_threshold:
                            # Get bookmaker link from API if available, otherwise generate one
                            bookmaker_url = odds_data.get('link') or self.generate_bookmaker_link(
                                odds_data['bookmaker'],
                                sport,
                                home_team,
                                away_team
                            )
                            
                            opportunities.append({
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
                                'bookmaker_url': bookmaker_url
                            })
        
        return opportunities
    
    def scan_all_sports(self, sport_keys: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """
        Scan multiple sports for +EV opportunities.
        
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
        
        for sport in sport_keys:
            opportunities = self.find_positive_ev_opportunities(sport, markets=self.markets)
            if opportunities:
                all_opportunities[sport] = opportunities
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
        
        return all_opportunities
    
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
        
        for sport, opps in opportunities.items():
            print(f"\n{'─'*80}")
            print(f"📊 {sport.upper().replace('_', ' ')}: {len(opps)} opportunities")
            print(f"{'─'*80}\n")
            
            # Sort by EV percentage (highest first)
            opps.sort(key=lambda x: x['ev_percentage'], reverse=True)
            
            for i, opp in enumerate(opps, 1):
                print(f"{i}. 🎯 {opp['game']}")
                print(f"   📅 {opp['commence_time']}")
                print(f"   🎲 Market: {opp['market'].upper()}")
                print(f"   🏆 Bet: {opp['outcome']}")
                print(f"   💰 Bookmaker: {opp['bookmaker']}")
                print(f"   📈 Odds: {opp['odds']:.2f} (Sharp Avg: {opp['sharp_avg_odds']:.2f})")
                print(f"   ✅ Expected Value: +{opp['ev_percentage']:.2f}%")
                print(f"   🎲 True Probability: {opp['true_probability']:.1f}%")
                print(f"   🔗 Link: {opp['bookmaker_url']}")
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
    print(f"� Betting bookmakers: {', '.join(scanner.betting_bookmakers)}")
    print(f"🏆 Sports/Leagues: {os.getenv('BETTING_SPORTS', 'soccer leagues')}")
    print(f"✅ Minimum EV threshold: {scanner.min_ev_threshold * 100}%")
    
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
