"""
Comprehensive tests to validate the accuracy of EV calculations in the Positive EV Scanner.

This test suite validates:
1. Core mathematical formulas (implied probability, EV calculation)
2. Sharp odds averaging (probability-based, not odds-based)
3. 2-way vs 3-way market handling
4. Edge cases and boundary conditions
5. Real-world scenarios with actual odds
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta, timezone
from src.core.positive_ev_scanner import PositiveEVScanner
from src.utils.odds_utils import calculate_implied_probability, calculate_ev


class TestImpliedProbabilityCalculations:
    """Verify implied probability calculations are mathematically correct."""
    
    def test_even_money_odds(self):
        """2.0 odds should equal exactly 50% probability"""
        prob = calculate_implied_probability(2.0)
        assert prob == 0.5
    
    def test_favorite_odds(self):
        """1.5 odds should equal exactly 66.67% probability"""
        prob = calculate_implied_probability(1.5)
        assert prob == pytest.approx(2/3, abs=0.00001)
    
    def test_underdog_odds(self):
        """3.0 odds should equal exactly 33.33% probability"""
        prob = calculate_implied_probability(3.0)
        assert prob == pytest.approx(1/3, abs=0.00001)
    
    def test_heavy_favorite(self):
        """1.2 odds should equal exactly 83.33% probability"""
        prob = calculate_implied_probability(1.2)
        assert prob == pytest.approx(5/6, abs=0.00001)
    
    def test_heavy_underdog(self):
        """10.0 odds should equal exactly 10% probability"""
        prob = calculate_implied_probability(10.0)
        assert prob == 0.1
    
    def test_extreme_favorite(self):
        """1.01 odds should equal 99.01% probability"""
        prob = calculate_implied_probability(1.01)
        assert prob == pytest.approx(0.990099, abs=0.00001)
    
    def test_extreme_underdog(self):
        """100.0 odds should equal 1% probability"""
        prob = calculate_implied_probability(100.0)
        assert prob == 0.01
    
    def test_probability_formula(self):
        """Verify the formula: probability = 1 / decimal_odds"""
        test_odds = [1.5, 2.0, 2.5, 3.0, 5.0, 10.0]
        for odds in test_odds:
            prob = calculate_implied_probability(odds)
            expected = 1.0 / odds
            assert prob == pytest.approx(expected, abs=0.00001)


class TestEVCalculationFormula:
    """Verify EV calculation formula is mathematically correct."""
    
    def test_ev_formula_basic(self):
        """Verify EV formula: EV = (true_prob × (odds - 1)) - (1 - true_prob)"""
        odds = 2.5
        true_prob = 0.5
        
        ev = calculate_ev(odds, true_prob)
        
        # Manual calculation: (0.5 × 1.5) - 0.5 = 0.75 - 0.5 = 0.25
        expected = (true_prob * (odds - 1)) - (1 - true_prob)
        assert ev == pytest.approx(expected, abs=0.00001)
        assert ev == pytest.approx(0.25, abs=0.00001)
    
    def test_positive_ev_scenario(self):
        """True odds 2.0, bookmaker offers 2.5 = +25% EV"""
        odds = 2.5
        true_prob = 0.5  # True odds of 2.0
        
        ev = calculate_ev(odds, true_prob)
        
        assert ev == pytest.approx(0.25, abs=0.00001)  # 25% EV
    
    def test_negative_ev_scenario(self):
        """True odds 2.5, bookmaker offers 2.0 = -16.67% EV"""
        odds = 2.0
        true_prob = 0.4  # True odds of 2.5
        
        ev = calculate_ev(odds, true_prob)
        
        # (0.4 × 1.0) - 0.6 = 0.4 - 0.6 = -0.2
        assert ev == pytest.approx(-0.2, abs=0.00001)
    
    def test_zero_ev_fair_odds(self):
        """When bookmaker odds match true odds, EV should be 0"""
        odds = 3.0
        true_prob = 1/3  # 33.33% = 3.0 odds
        
        ev = calculate_ev(odds, true_prob)
        
        assert ev == pytest.approx(0.0, abs=0.00001)
    
    def test_high_ev_underdog(self):
        """True odds 5.0, bookmaker offers 10.0 = +80% EV"""
        odds = 10.0
        true_prob = 0.2  # True odds of 5.0
        
        ev = calculate_ev(odds, true_prob)
        
        # (0.2 × 9.0) - 0.8 = 1.8 - 0.8 = 1.0
        assert ev == pytest.approx(1.0, abs=0.00001)  # 100% EV
    
    def test_small_edge_detection(self):
        """Small edges should be detected accurately (2% EV)"""
        odds = 2.04
        true_prob = 0.5
        
        ev = calculate_ev(odds, true_prob)
        
        # (0.5 × 1.04) - 0.5 = 0.52 - 0.5 = 0.02
        assert ev == pytest.approx(0.02, abs=0.0001)


class TestSharpOddsAveragingAccuracy:
    """Verify sharp odds are averaged correctly (probability-based, NOT odds-based)."""
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle,betfair',
        'BETTING_BOOKMAKERS': 'bet365'
    })
    def test_averaging_probabilities_not_odds(self):
        """CRITICAL: Must average probabilities, not odds!"""
        scanner = PositiveEVScanner()
        
        # Two sharp books with different odds
        outcomes = [
            {
                'key': 'pinnacle',
                'markets': [{
                    'outcomes': [
                        {'name': 'Team A', 'price': 2.0}  # 50% probability
                    ]
                }]
            },
            {
                'key': 'betfair',
                'markets': [{
                    'outcomes': [
                        {'name': 'Team A', 'price': 2.5}  # 40% probability
                    ]
                }]
            }
        ]
        
        avg_odds = scanner.get_sharp_average(outcomes, 'Team A')
        
        # WRONG: Average odds = (2.0 + 2.5) / 2 = 2.25
        # RIGHT: Average probabilities = (0.5 + 0.4) / 2 = 0.45, convert to odds = 1/0.45 = 2.222
        
        expected_prob = (0.5 + 0.4) / 2
        expected_odds = 1 / expected_prob
        
        assert avg_odds == pytest.approx(expected_odds, abs=0.001)
        assert avg_odds == pytest.approx(2.222, abs=0.001)
        assert avg_odds != 2.25  # Ensure we're NOT averaging odds directly
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle,betfair,smarkets',
        'BETTING_BOOKMAKERS': 'bet365'
    })
    def test_three_sharp_books_averaging(self):
        """Test with three sharp books"""
        scanner = PositiveEVScanner()
        
        outcomes = [
            {
                'key': 'pinnacle',
                'markets': [{
                    'outcomes': [
                        {'name': 'Over 2.5', 'price': 2.0}  # 50%
                    ]
                }]
            },
            {
                'key': 'betfair',
                'markets': [{
                    'outcomes': [
                        {'name': 'Over 2.5', 'price': 2.2}  # 45.45%
                    ]
                }]
            },
            {
                'key': 'smarkets',
                'markets': [{
                    'outcomes': [
                        {'name': 'Over 2.5', 'price': 1.9}  # 52.63%
                    ]
                }]
            }
        ]
        
        avg_odds = scanner.get_sharp_average(outcomes, 'Over 2.5')
        
        # Calculate expected: average probabilities first
        prob1 = 1/2.0    # 0.5
        prob2 = 1/2.2    # 0.4545
        prob3 = 1/1.9    # 0.5263
        avg_prob = (prob1 + prob2 + prob3) / 3  # 0.4936
        expected_odds = 1 / avg_prob  # 2.026
        
        assert avg_odds == pytest.approx(expected_odds, abs=0.001)
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365'
    })
    def test_single_sharp_book(self):
        """With single sharp book, should return exact odds"""
        scanner = PositiveEVScanner()
        
        outcomes = [
            {
                'key': 'pinnacle',
                'markets': [{
                    'outcomes': [
                        {'name': 'Draw', 'price': 3.5}
                    ]
                }]
            }
        ]
        
        avg_odds = scanner.get_sharp_average(outcomes, 'Draw')
        
        assert avg_odds == 3.5
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle,betfair',
        'BETTING_BOOKMAKERS': 'bet365'
    })
    def test_no_sharp_books_available(self):
        """Should return None when no sharp books have odds"""
        scanner = PositiveEVScanner()
        
        outcomes = [
            {
                'key': 'bet365',
                'markets': [{
                    'outcomes': [
                        {'name': 'Team A', 'price': 2.0}
                    ]
                }]
            }
        ]
        
        avg_odds = scanner.get_sharp_average(outcomes, 'Team A')
        
        assert avg_odds is None


class TestTwoWayVsThreeWayMarketHandling:
    """Verify 2-way and 3-way markets are handled separately."""
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.01',
        'BANKROLL': '1000'
    })
    def test_filters_mixed_outcome_counts(self):
        """Should only compare bookmakers with same number of outcomes"""
        scanner = PositiveEVScanner()
        
        # Game with mixed 2-way and 3-way markets
        games = [{
            'id': 'game1',
            'home_team': 'Arsenal',
            'away_team': 'Chelsea',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Arsenal', 'price': 2.0},  # 2-way market
                            {'name': 'Chelsea', 'price': 2.0}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Arsenal', 'price': 2.1},  # 3-way market
                            {'name': 'Draw', 'price': 3.5},
                            {'name': 'Chelsea', 'price': 2.1}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'soccer_epl', set())
        
        # Should not find opportunities because outcome counts don't match
        # (Pinnacle has 2-way, Bet365 has 3-way)
        assert len(opportunities) == 0
    
    @patch('src.core.positive_ev_scanner.BookmakerCredentials.get_available_bookmakers', return_value=['bet365'])
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'MIN_EV_THRESHOLD': '0.01',
        'BANKROLL': '1000',
        'MARKETS': 'h2h'
    })
    def test_compares_matching_outcome_counts(self, mock_bookmakers):
        """Should compare bookmakers with same outcome count"""
        scanner = PositiveEVScanner()
        scanner.markets = 'h2h'  # Ensure scanner uses h2h market
        
        # Both bookmakers have 2-way markets
        games = [{
            'id': 'game2',
            'home_team': 'Arsenal',
            'away_team': 'Chelsea',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Arsenal', 'price': 2.0},
                            {'name': 'Chelsea', 'price': 2.0}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Arsenal', 'price': 2.5},  # Better odds = +EV
                            {'name': 'Chelsea', 'price': 1.7}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'soccer_epl', set())
        
        # Should find the Arsenal +EV opportunity
        assert len(opportunities) > 0
        arsenal_opps = [o for o in opportunities if o['outcome'] == 'Arsenal']
        assert len(arsenal_opps) == 1
        assert arsenal_opps[0]['odds'] == 2.5


class TestRealWorldEVScenarios:
    """Test with realistic odds scenarios from actual bookmakers."""
    
    @patch('src.core.positive_ev_scanner.BookmakerCredentials.get_available_bookmakers', return_value=['bet365'])
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle,betfair',
        'MIN_EV_THRESHOLD': '0.02',
        'BANKROLL': '1000',
        'MARKETS': 'h2h'
    })
    def test_small_edge_detection(self, mock_bookmakers):
        """Detect small but profitable 2% edge"""
        scanner = PositiveEVScanner()
        scanner.markets = 'h2h'
        
        # Pinnacle: 1.95, Betfair: 2.05 (avg prob = 50%)
        # Bet365: 2.10 (47.6% implied) = +5% EV
        games = [{
            'id': 'game3',
            'home_team': 'Team A',
            'away_team': 'Team B',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team A', 'price': 1.95},
                            {'name': 'Team B', 'price': 2.05}
                        ]
                    }]
                },
                {
                    'key': 'betfair',
                    'title': 'Betfair',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team A', 'price': 2.05},
                            {'name': 'Team B', 'price': 1.95}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team A', 'price': 2.10},
                            {'name': 'Team B', 'price': 1.85}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should detect the 2.10 odds as +EV
        assert len(opportunities) == 1
        opp = opportunities[0]
        
        # Verify calculations
        sharp_prob = (1/1.95 + 1/2.05) / 2  # ~0.50
        expected_ev = (sharp_prob * (2.10 - 1)) - (1 - sharp_prob)
        
        assert opp['odds'] == 2.10
        assert opp['ev_percentage'] == pytest.approx(expected_ev * 100, rel=0.01)
        assert opp['ev_percentage'] > 2.0  # Above minimum threshold
    
    @patch('src.core.positive_ev_scanner.BookmakerCredentials.get_available_bookmakers', return_value=['bet365'])
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'MIN_EV_THRESHOLD': '0.05',
        'BANKROLL': '1000',
        'MARKETS': 'h2h'
    })
    def test_large_edge_favorite(self, mock_bookmakers):
        """Detect large edge on a favorite"""
        scanner = PositiveEVScanner()
        scanner.markets = 'h2h'
        
        # Pinnacle: 1.50 (66.67% true probability)
        # Bet365: 1.70 (58.82% implied) = +13.33% EV
        games = [{
            'id': 'game4',
            'home_team': 'Strong Team',
            'away_team': 'Weak Team',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Strong Team', 'price': 1.50},
                            {'name': 'Weak Team', 'price': 4.00}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Strong Team', 'price': 1.70},
                            {'name': 'Weak Team', 'price': 3.50}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        assert len(opportunities) == 1
        opp = opportunities[0]
        
        # True prob = 1/1.50 = 0.6667
        # EV = (0.6667 × 0.70) - 0.3333 = 0.4667 - 0.3333 = 0.1334
        assert opp['ev_percentage'] == pytest.approx(13.34, rel=0.01)
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.05',
        'BANKROLL': '1000'
    })
    def test_no_edge_scenario(self):
        """Should not flag bets with no edge"""
        scanner = PositiveEVScanner()
        
        # Pinnacle: 2.00
        # Bet365: 1.95 (worse odds = negative EV)
        games = [{
            'id': 'game5',
            'home_team': 'Team X',
            'away_team': 'Team Y',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team X', 'price': 2.00}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team X', 'price': 1.95}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should not find any opportunities (negative EV)
        assert len(opportunities) == 0


class TestSpreadAndTotalsMarkets:
    """Verify EV calculations work correctly for spreads and totals."""
    
    @patch('src.core.positive_ev_scanner.BookmakerCredentials.get_available_bookmakers', return_value=['bet365'])
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'MIN_EV_THRESHOLD': '0.02',
        'MARKETS': 'spreads',
        'BANKROLL': '1000'
    })
    def test_spread_market_with_points(self, mock_bookmakers):
        """Verify spreads with point lines are tracked separately"""
        scanner = PositiveEVScanner()
        scanner.markets = 'spreads'
        
        games = [{
            'id': 'game6',
            'home_team': 'Team A',
            'away_team': 'Team B',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'spreads',
                        'outcomes': [
                            {'name': 'Team A', 'price': 1.95, 'point': -3.5},
                            {'name': 'Team B', 'price': 1.95, 'point': 3.5}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'spreads',
                        'outcomes': [
                            {'name': 'Team A', 'price': 2.10, 'point': -3.5},  # +EV
                            {'name': 'Team B', 'price': 1.85, 'point': 3.5}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should find Team A -3.5 at better odds
        assert len(opportunities) == 1
        assert opportunities[0]['outcome'] == 'Team A (-3.5)'
        assert opportunities[0]['odds'] == 2.10
    
    @patch('src.core.positive_ev_scanner.BookmakerCredentials.get_available_bookmakers', return_value=['bet365'])
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'MIN_EV_THRESHOLD': '0.02',
        'MARKETS': 'totals',
        'BANKROLL': '1000'
    })
    def test_totals_market_over_under(self, mock_bookmakers):
        """Verify totals (over/under) markets calculate correctly"""
        scanner = PositiveEVScanner()
        scanner.markets = 'totals'
        
        games = [{
            'id': 'game7',
            'home_team': 'Team C',
            'away_team': 'Team D',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'totals',
                        'outcomes': [
                            {'name': 'Over', 'price': 1.90, 'point': 2.5},
                            {'name': 'Under', 'price': 2.00, 'point': 2.5}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'totals',
                        'outcomes': [
                            {'name': 'Over', 'price': 2.05, 'point': 2.5},  # +EV
                            {'name': 'Under', 'price': 1.85, 'point': 2.5}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should find Over 2.5 at better odds
        over_opps = [o for o in opportunities if 'Over' in o['outcome']]
        assert len(over_opps) == 1
        assert over_opps[0]['odds'] == 2.05


class TestFilteringLogic:
    """Verify filtering logic works correctly."""
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.05',
        'MIN_TRUE_PROBABILITY': '0.40',
        'BANKROLL': '1000'
    })
    def test_min_true_probability_filter(self):
        """Should filter out low probability bets even with high EV"""
        scanner = PositiveEVScanner()
        
        # High odds underdog with +EV but low probability
        games = [{
            'id': 'game8',
            'home_team': 'Underdog',
            'away_team': 'Favorite',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Underdog', 'price': 8.0}  # 12.5% probability
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Underdog', 'price': 10.0}  # Higher odds = +EV
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should be filtered out (probability < 40%)
        assert len(opportunities) == 0
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.02',
        'MAX_ODDS': '3.0',
        'BANKROLL': '1000'
    })
    def test_max_odds_filter(self):
        """Should filter out bets above maximum odds"""
        scanner = PositiveEVScanner()
        
        games = [{
            'id': 'game9',
            'home_team': 'Team E',
            'away_team': 'Team F',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team E', 'price': 3.0}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team E', 'price': 3.5}  # Above max odds
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should be filtered out (odds > 3.0)
        assert len(opportunities) == 0
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.02',
        'MIN_KELLY_PERCENTAGE': '0.02',
        'BANKROLL': '1000'
    })
    def test_min_kelly_filter(self):
        """Should filter out bets below minimum Kelly percentage"""
        scanner = PositiveEVScanner()
        
        # Small edge that doesn't meet Kelly threshold
        games = [{
            'id': 'game10',
            'home_team': 'Team G',
            'away_team': 'Team H',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team G', 'price': 2.00}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team G', 'price': 2.02}  # Tiny edge
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should be filtered out (Kelly % too low)
        assert len(opportunities) == 0


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.02',
        'BANKROLL': '1000'
    })
    def test_live_game_filtered_out(self):
        """Games that have already started should be filtered"""
        scanner = PositiveEVScanner()
        
        # Game that started 1 hour ago
        games = [{
            'id': 'game11',
            'home_team': 'Team I',
            'away_team': 'Team J',
            'commence_time': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team I', 'price': 2.00}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team I', 'price': 2.50}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should be filtered (game already started)
        assert len(opportunities) == 0
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.02',
        'SKIP_ALREADY_BET_GAMES': 'true',
        'BANKROLL': '1000'
    })
    def test_already_bet_game_filtered(self):
        """Games with existing bets should be filtered if enabled"""
        scanner = PositiveEVScanner()
        
        game_id = 'game12'
        already_bet_games = {game_id}
        
        games = [{
            'id': game_id,
            'home_team': 'Team K',
            'away_team': 'Team L',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team K', 'price': 2.00}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team K', 'price': 2.50}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', already_bet_games)
        
        # Should be filtered (already have a bet on this game)
        assert len(opportunities) == 0
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.02',
        'BANKROLL': '1000'
    })
    def test_empty_games_list(self):
        """Should handle empty games list gracefully"""
        scanner = PositiveEVScanner()
        
        opportunities = scanner.analyze_games_for_ev([], 'test_sport', set())
        
        assert opportunities == []
    
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'MIN_EV_THRESHOLD': '0.02',
        'BANKROLL': '1000'
    })
    def test_game_without_bookmakers(self):
        """Should handle games without bookmaker data"""
        scanner = PositiveEVScanner()
        
        games = [{
            'id': 'game13',
            'home_team': 'Team M',
            'away_team': 'Team N',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': []
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        assert len(opportunities) == 0


class TestExpectedProfitCalculation:
    """Verify expected profit calculations are accurate."""
    
    @patch('src.core.positive_ev_scanner.BookmakerCredentials.get_available_bookmakers', return_value=['bet365'])
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'MIN_EV_THRESHOLD': '0.02',
        'BANKROLL': '1000',
        'KELLY_FRACTION': '1.0',
        'MARKETS': 'h2h'
    })
    def test_expected_profit_calculation(self, mock_bookmakers):
        """Verify expected profit = stake × EV"""
        scanner = PositiveEVScanner()
        scanner.markets = 'h2h'
        
        games = [{
            'id': 'game14',
            'home_team': 'Team O',
            'away_team': 'Team P',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team O', 'price': 2.00},  # 50% true probability
                            {'name': 'Team P', 'price': 2.00}
                        ]
                    }]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{
                        'key': 'h2h',
                        'outcomes': [
                            {'name': 'Team O', 'price': 2.20},  # 10% EV
                            {'name': 'Team P', 'price': 1.85}
                        ]
                    }]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        assert len(opportunities) == 1
        opp = opportunities[0]
        
        # Verify: expected_profit = stake × (true_prob × (odds - 1) - (1 - true_prob))
        stake = opp['kelly_stake']['recommended_stake']
        true_prob = opp['true_probability'] / 100
        odds = opp['odds']
        ev = (true_prob * (odds - 1)) - (1 - true_prob)
        expected_profit_manual = stake * ev
        
        assert opp['expected_profit'] == pytest.approx(expected_profit_manual, abs=0.01)


class TestMultipleMarketsInSameGame:
    """Verify multiple markets in same game are handled correctly."""
    
    @patch('src.core.positive_ev_scanner.BookmakerCredentials.get_available_bookmakers', return_value=['bet365'])
    @patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_key',
        'SHARP_BOOKS': 'pinnacle',
        'MIN_EV_THRESHOLD': '0.02',
        'MARKETS': 'h2h,totals',
        'BANKROLL': '1000'
    })
    def test_multiple_markets_same_game(self, mock_bookmakers):
        """Should find +EV opportunities in multiple markets for same game"""
        scanner = PositiveEVScanner()
        scanner.markets = 'h2h,totals'
        
        games = [{
            'id': 'game15',
            'home_team': 'Team Q',
            'away_team': 'Team R',
            'commence_time': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            'bookmakers': [
                {
                    'key': 'pinnacle',
                    'title': 'Pinnacle',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Team Q', 'price': 2.00},
                                {'name': 'Team R', 'price': 2.00}
                            ]
                        },
                        {
                            'key': 'totals',
                            'outcomes': [
                                {'name': 'Over', 'price': 1.95, 'point': 2.5},
                                {'name': 'Under', 'price': 2.05, 'point': 2.5}
                            ]
                        }
                    ]
                },
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Team Q', 'price': 2.20},  # +EV in h2h
                                {'name': 'Team R', 'price': 1.85}
                            ]
                        },
                        {
                            'key': 'totals',
                            'outcomes': [
                                {'name': 'Over', 'price': 2.10, 'point': 2.5},  # +EV in totals
                                {'name': 'Under', 'price': 1.90, 'point': 2.5}
                            ]
                        }
                    ]
                }
            ]
        }]
        
        opportunities = scanner.analyze_games_for_ev(games, 'test_sport', set())
        
        # Should find both opportunities
        assert len(opportunities) == 2
        markets = [o['market'] for o in opportunities]
        assert 'h2h' in markets
        assert 'totals' in markets
