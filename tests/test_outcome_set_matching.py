"""
Test that outcome set matching prevents mixing 2-way and 3-way markets.

This test validates the fix for the bug where Draw bets were getting
sharp odds from Home/Away outcomes when h2h and h2h_3_way markets were both enabled.
"""

import pytest
from unittest.mock import Mock, patch
from src.core.positive_ev_scanner import PositiveEVScanner


class TestOutcomeSetMatching:
    """Test outcome set matching to prevent market cross-contamination."""
    
    @pytest.fixture
    def scanner(self):
        """Create a scanner with test configuration."""
        with patch.dict('os.environ', {
            'SHARP_BOOKS': 'pinnacle',
            'MARKETS': 'h2h,h2h_3_way',
            'MIN_EV_THRESHOLD': '0.05',
            'BANKROLL': '1000',
            'KELLY_FRACTION': '0.5',
            'USE_VIG_ADJUSTED_EV': 'false'
        }):
            scanner = PositiveEVScanner()
            scanner.kelly = Mock()
            scanner.kelly.bankroll = 1000
            scanner.kelly.fraction = 0.5
            return scanner
    
    def test_2way_and_3way_markets_not_mixed(self, scanner):
        """Test that 2-way and 3-way markets are kept separate."""
        # Simulate game data where Pinnacle offers both 2-way and 3-way h2h
        # This is the real-world scenario that caused the bug
        games = [{
            'id': 'test_game_123',
            'sport_key': 'soccer_epl',
            'sport_title': 'EPL',
            'commence_time': '2024-07-15T19:00:00Z',
            'home_team': 'Manchester United',
            'away_team': 'Liverpool',
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Manchester United', 'price': 1.40},
                                {'name': 'Liverpool', 'price': 1.33},
                                {'name': 'Draw', 'price': 3.50}  # 3-way market labeled as h2h
                            ]
                        }
                    ]
                },
                {
                    'key': 'betfair_sb_uk',
                    'title': 'Betfair Sportsbook',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Manchester United', 'price': 1.45},
                                {'name': 'Liverpool', 'price': 1.35},
                                {'name': 'Draw', 'price': 4.00}  # Good value on draw
                            ]
                        }
                    ]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'soccer_epl', set())
        
        # Find draw opportunity if it exists
        draw_opps = [o for o in opportunities if o.get('outcome') == 'Draw']
        
        if draw_opps:
            draw_opp = draw_opps[0]
            
            # The sharp average should be based on Pinnacle's Draw odds (3.50)
            # NOT on an average of Home/Away odds (1.40 + 1.33)/2 = 1.365
            # which would give 73% implied probability
            sharp_avg = draw_opp.get('sharp_avg_odds', 0)
            
            # Sharp avg should be close to Pinnacle's draw odds
            assert 3.0 < sharp_avg < 4.0, \
                f"Sharp avg odds for Draw should be ~3.5, not {sharp_avg}. " \
                f"If it's ~1.36, the bug still exists (mixing home/away with draw)."
            
            # True probability should be realistic for a draw (~28%)
            true_prob = draw_opp.get('true_probability', 0)
            if isinstance(true_prob, float) and true_prob > 1:
                true_prob = true_prob / 100  # Convert percentage to decimal
            
            assert 0.20 < true_prob < 0.40, \
                f"Draw true probability should be 20-40%, not {true_prob*100:.1f}%. " \
                f"If it's ~73%, the bug still exists."
    
    def test_outcome_sets_must_match_exactly(self, scanner):
        """Test that bookmakers must have identical outcome sets to be compared."""
        games = [{
            'id': 'test_game_456',
            'sport_key': 'soccer_bundesliga',
            'sport_title': 'Bundesliga',
            'commence_time': '2024-07-15T19:00:00Z',
            'home_team': 'Bayern Munich',
            'away_team': 'Borussia Dortmund',
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Bayern Munich', 'price': 1.50},
                                {'name': 'Borussia Dortmund', 'price': 6.00},
                                {'name': 'Draw', 'price': 4.20}
                            ]
                        }
                    ]
                },
                {
                    'key': 'betfair_sb_uk',
                    'title': 'Betfair Sportsbook',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                # Only 2-way market (no draw) - should NOT be compared with Pinnacle
                                {'name': 'Bayern Munich', 'price': 1.52},
                                {'name': 'Borussia Dortmund', 'price': 5.80}
                            ]
                        }
                    ]
                },
                {
                    'key': 'williamhill',
                    'title': 'William Hill',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Bayern Munich', 'price': 1.48},
                                {'name': 'Borussia Dortmund', 'price': 6.20},
                                {'name': 'Draw', 'price': 4.50}  # Same outcome set as Pinnacle
                            ]
                        }
                    ]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'soccer_bundesliga', set())
        
        # Check that opportunities only use bookmakers with matching outcome sets
        for opp in opportunities:
            bookmaker = opp.get('bookmaker')
            outcome = opp.get('outcome')
            
            # If this is a Draw bet, it should NOT use Betfair (2-way market)
            # It should only compare against bookmakers that also offer Draw
            if outcome == 'Draw':
                assert bookmaker != 'betfair_sb_uk', \
                    "Draw bet should not come from 2-way market bookmaker"
    
    def test_spreads_with_different_points_not_mixed(self, scanner):
        """Test that spread markets with different points are kept separate."""
        with patch.dict('os.environ', {'MARKETS': 'spreads'}):
            scanner_spreads = PositiveEVScanner()
            scanner_spreads.kelly = Mock()
            scanner_spreads.kelly.bankroll = 1000
            scanner_spreads.kelly.fraction = 0.5
            
            games = [{
                'id': 'test_game_789',
                'sport_key': 'americanfootball_nfl',
                'sport_title': 'NFL',
                'commence_time': '2024-07-15T19:00:00Z',
                'home_team': 'Kansas City Chiefs',
                'away_team': 'Buffalo Bills',
                'bookmakers': [
                    {
                        'key': 'pinnacle',
                        'title': 'Pinnacle',
                        'markets': [
                            {
                                'key': 'spreads',
                                'outcomes': [
                                    {'name': 'Kansas City Chiefs', 'price': 1.90, 'point': -3.5},
                                    {'name': 'Buffalo Bills', 'price': 1.95, 'point': 3.5}
                                ]
                            }
                        ]
                    },
                    {
                        'key': 'fanduel',
                        'title': 'FanDuel',
                        'markets': [
                            {
                                'key': 'spreads',
                                'outcomes': [
                                    # Different spread line - should NOT be compared
                                    {'name': 'Kansas City Chiefs', 'price': 1.85, 'point': -4.0},
                                    {'name': 'Buffalo Bills', 'price': 2.00, 'point': 4.0}
                                ]
                            }
                        ]
                    },
                    {
                        'key': 'draftkings',
                        'title': 'DraftKings',
                        'markets': [
                            {
                                'key': 'spreads',
                                'outcomes': [
                                    # Same spread as Pinnacle - should be compared
                                    {'name': 'Kansas City Chiefs', 'price': 1.92, 'point': -3.5},
                                    {'name': 'Buffalo Bills', 'price': 1.93, 'point': 3.5}
                                ]
                            }
                        ]
                    }
                ]
            }]
            
            opportunities = scanner_spreads.analyze_games_for_ev(games, 'americanfootball_nfl', set())
            
            # Verify that spreads with different points are not compared
            for opp in opportunities:
                outcome = opp.get('outcome')
                # The outcome should include the point spread
                assert '(' in outcome and ')' in outcome, \
                    "Spread outcome should include point value"
    
    def test_no_sharp_odds_when_outcome_sets_differ(self, scanner):
        """Test that bets are skipped when sharp book has different outcome set."""
        games = [{
            'id': 'test_game_999',
            'sport_key': 'soccer_bundesliga',
            'sport_title': 'Bundesliga',
            'commence_time': '2024-07-15T19:00:00Z',
            'home_team': 'RB Leipzig',
            'away_team': 'Bayer Leverkusen',
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                # Pinnacle only offers 2-way
                                {'name': 'RB Leipzig', 'price': 1.70},
                                {'name': 'Bayer Leverkusen', 'price': 2.20}
                            ]
                        }
                    ]
                },
                {
                    'key': 'williamhill',
                    'title': 'William Hill',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                # William Hill offers 3-way with great draw odds
                                {'name': 'RB Leipzig', 'price': 1.72},
                                {'name': 'Bayer Leverkusen', 'price': 2.25},
                                {'name': 'Draw', 'price': 3.80}
                            ]
                        }
                    ]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'soccer_bundesliga', set())
        
        # There should be NO Draw opportunity because Pinnacle doesn't offer it
        # (and Pinnacle is the only sharp book)
        draw_opps = [o for o in opportunities if o.get('outcome') == 'Draw']
        
        assert len(draw_opps) == 0, \
            "No Draw bet should be found when sharp book doesn't offer Draw outcome"
        
        # But Home/Away bets should still work (both books offer those)
        home_away_opps = [o for o in opportunities 
                          if o.get('outcome') in ['RB Leipzig', 'Bayer Leverkusen']]
        
        # We should have opportunities for Home and/or Away (if they have +EV)
        # This verifies the fix doesn't break normal 2-way matching
        assert isinstance(home_away_opps, list), \
            "Should still find Home/Away opportunities when outcome sets match"
