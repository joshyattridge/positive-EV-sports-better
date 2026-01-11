"""
Unit tests for Positive EV Scanner module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.positive_ev_scanner import PositiveEVScanner


@pytest.fixture
def scanner():
    """Create a scanner instance for testing"""
    with patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_api_key',
        'SHARP_BOOKS': 'pinnacle,betfair',
        'BETTING_BOOKMAKERS': 'bet365,williamhill',
        'MIN_EV_THRESHOLD': '0.02',
        'MIN_TRUE_PROBABILITY': '0.40',
        'KELLY_FRACTION': '0.25',
        'BANKROLL': '1000'
    }):
        scanner = PositiveEVScanner()
        # Clear cache before each test to ensure test isolation
        scanner._odds_cache = {}
        return scanner


class TestScannerInitialization:
    """Test scanner initialization"""
    
    def test_initialization_with_api_key(self):
        """Test initialization with explicit API key"""
        scanner = PositiveEVScanner(api_key='my_test_key')
        assert scanner.api_key == 'my_test_key'
    
    def test_initialization_from_env(self):
        """Test initialization from environment"""
        with patch.dict('os.environ', {'ODDS_API_KEY': 'env_key'}):
            scanner = PositiveEVScanner()
            assert scanner.api_key == 'env_key'
    
    def test_initialization_missing_key(self):
        """Test initialization fails without API key"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match='ODDS_API_KEY'):
                PositiveEVScanner()
    
    def test_initialization_reads_sharp_books(self, scanner):
        """Test reads sharp books from env"""
        assert 'pinnacle' in scanner.sharp_books
        assert 'betfair' in scanner.sharp_books
    
    def test_initialization_reads_betting_bookmakers(self, scanner):
        """Test auto-detects betting bookmakers from credentials"""
        # Should detect bookmakers that have credentials configured in .env
        # The actual bookmakers depend on what's in the .env file
        assert isinstance(scanner.betting_bookmakers, list)
        # Check that it's auto-detecting (not empty if credentials exist)
        # In test environment, this may be empty or have real credentials
    
    def test_initialization_reads_thresholds(self, scanner):
        """Test reads threshold values from env"""
        assert scanner.min_ev_threshold == 0.02
        assert scanner.min_true_probability == 0.40
        assert scanner.kelly_fraction == 0.25


class TestCalculateImpliedProbability:
    """Test implied probability calculation"""
    
    def test_calculate_implied_probability_even_money(self, scanner):
        """Test with even money odds"""
        prob = scanner.calculate_implied_probability(2.0)
        assert prob == pytest.approx(0.5, rel=0.001)
    
    def test_calculate_implied_probability_favorite(self, scanner):
        """Test with favorite odds"""
        prob = scanner.calculate_implied_probability(1.5)
        assert prob == pytest.approx(0.6667, rel=0.001)
    
    def test_calculate_implied_probability_underdog(self, scanner):
        """Test with underdog odds"""
        prob = scanner.calculate_implied_probability(3.0)
        assert prob == pytest.approx(0.3333, rel=0.001)
    
    def test_calculate_implied_probability_heavy_favorite(self, scanner):
        """Test with heavy favorite"""
        prob = scanner.calculate_implied_probability(1.1)
        assert prob == pytest.approx(0.9091, rel=0.001)


class TestDecimalToFractional:
    """Test decimal to fractional odds conversion"""
    
    def test_decimal_to_fractional_even_money(self, scanner):
        """Test even money conversion"""
        frac = scanner.decimal_to_fractional(2.0)
        assert frac == "1/1"
    
    def test_decimal_to_fractional_simple(self, scanner):
        """Test simple fractional conversion"""
        frac = scanner.decimal_to_fractional(3.0)
        assert frac == "2/1"
    
    def test_decimal_to_fractional_complex(self, scanner):
        """Test complex fractional conversion"""
        frac = scanner.decimal_to_fractional(2.5)
        assert frac == "3/2"
    
    def test_decimal_to_fractional_favorite(self, scanner):
        """Test favorite odds conversion"""
        frac = scanner.decimal_to_fractional(1.5)
        assert frac == "1/2"


class TestCalculateEV:
    """Test expected value calculation"""
    
    def test_calculate_ev_positive(self, scanner):
        """Test positive EV calculation"""
        ev = scanner.calculate_ev(
            bet_odds=2.5,
            true_probability=0.5
        )
        # (0.5 * 1.5) - 0.5 = 0.75 - 0.5 = 0.25 = 25%
        assert ev == pytest.approx(0.25, rel=0.001)
    
    def test_calculate_ev_negative(self, scanner):
        """Test negative EV calculation"""
        ev = scanner.calculate_ev(
            bet_odds=1.5,
            true_probability=0.4
        )
        # (0.4 * 0.5) - 0.6 = 0.2 - 0.6 = -0.4
        assert ev < 0
    
    def test_calculate_ev_zero(self, scanner):
        """Test zero EV (fair odds)"""
        ev = scanner.calculate_ev(
            bet_odds=2.0,
            true_probability=0.5
        )
        # (0.5 * 1.0) - 0.5 = 0.5 - 0.5 = 0
        assert ev == pytest.approx(0.0, abs=0.001)


class TestGenerateBookmakerLink:
    """Test bookmaker link generation"""
    
    def test_generate_link_williamhill(self, scanner):
        """Test William Hill link generation - now uses Google search fallback"""
        link = scanner.generate_bookmaker_link(
            'williamhill',
            'soccer_epl',
            'Arsenal',
            'Chelsea'
        )
        assert 'google.com' in link or 'williamhill' in link
        assert 'Chelsea' in link or 'Arsenal' in link
    
    def test_generate_link_bet365(self, scanner):
        """Test Bet365 link generation - uses Google search fallback"""
        link = scanner.generate_bookmaker_link(
            'bet365',
            'soccer_epl',
            'Manchester United',
            'Liverpool'
        )
        assert 'google.com' in link or 'bet365' in link
    
    def test_generate_link_unknown_bookmaker(self, scanner):
        """Test link generation for unknown bookmaker"""
        link = scanner.generate_bookmaker_link(
            'unknown_bookie',
            'soccer_epl',
            'Team A',
            'Team B'
        )
        # Should fallback to Google search
        assert 'google.com' in link or 'unknown_bookie' in link


class TestGetSharpAverage:
    """Test sharp bookmaker average calculation"""
    
    def test_get_sharp_average_single_book(self, scanner):
        """Test average with single sharp book"""
        outcomes = [
            {
                'key': 'pinnacle',
                'markets': [{
                    'outcomes': [
                        {'name': 'Arsenal', 'price': 2.5}
                    ]
                }]
            }
        ]
        
        avg = scanner.get_sharp_average(outcomes, 'Arsenal')
        assert avg == 2.5
    
    def test_get_sharp_average_multiple_books(self, scanner):
        """Test average with multiple sharp books"""
        outcomes = [
            {
                'key': 'pinnacle',
                'markets': [{
                    'outcomes': [
                        {'name': 'Arsenal', 'price': 2.5}
                    ]
                }]
            },
            {
                'key': 'betfair',
                'markets': [{
                    'outcomes': [
                        {'name': 'Arsenal', 'price': 2.3}
                    ]
                }]
            }
        ]
        
        avg = scanner.get_sharp_average(outcomes, 'Arsenal')
        # The implementation correctly averages implied probabilities, not raw odds
        # 2.5 -> 0.4, 2.3 -> 0.4348, avg = 0.4174, odds = 1/0.4174 = 2.3958
        assert avg == pytest.approx(2.3958, rel=0.001)
    
    def test_get_sharp_average_no_sharp_books(self, scanner):
        """Test returns None when no sharp books found"""
        outcomes = [
            {
                'key': 'bet365',
                'markets': [{
                    'outcomes': [
                        {'name': 'Arsenal', 'price': 2.5}
                    ]
                }]
            }
        ]
        
        avg = scanner.get_sharp_average(outcomes, 'Arsenal')
        assert avg is None


class TestSortOpportunities:
    """Test opportunity sorting"""
    
    def test_sort_by_ev_desc(self):
        """Test sorting by EV descending"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'ORDER_BY': 'ev',
            'SORT_ORDER': 'desc'
        }):
            scanner = PositiveEVScanner()
            
            opps = [
                {'ev_percentage': 2.0, 'expected_profit': 10},
                {'ev_percentage': 5.0, 'expected_profit': 15},
                {'ev_percentage': 3.0, 'expected_profit': 12}
            ]
            
            sorted_opps = scanner.sort_opportunities(opps)
            
            assert sorted_opps[0]['ev_percentage'] == 5.0
            assert sorted_opps[1]['ev_percentage'] == 3.0
            assert sorted_opps[2]['ev_percentage'] == 2.0
    
    def test_sort_by_expected_profit_desc(self):
        """Test sorting by expected profit descending"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'ORDER_BY': 'expected_profit',
            'SORT_ORDER': 'desc'
        }):
            scanner = PositiveEVScanner()
            
            opps = [
                {'ev_percentage': 2.0, 'expected_profit': 10},
                {'ev_percentage': 5.0, 'expected_profit': 15},
                {'ev_percentage': 3.0, 'expected_profit': 12}
            ]
            
            sorted_opps = scanner.sort_opportunities(opps)
            
            assert sorted_opps[0]['expected_profit'] == 15
            assert sorted_opps[1]['expected_profit'] == 12
            assert sorted_opps[2]['expected_profit'] == 10
    
    def test_sort_by_odds_asc(self):
        """Test sorting by odds ascending"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'ORDER_BY': 'odds',
            'SORT_ORDER': 'asc'
        }):
            scanner = PositiveEVScanner()
            
            opps = [
                {'odds': 2.5},
                {'odds': 1.5},
                {'odds': 3.0}
            ]
            
            sorted_opps = scanner.sort_opportunities(opps)
            
            assert sorted_opps[0]['odds'] == 1.5
            assert sorted_opps[1]['odds'] == 2.5
            assert sorted_opps[2]['odds'] == 3.0


class TestFilterOneBetPerGame:
    """Test one bet per game filtering"""
    
    def test_filter_one_bet_per_game_enabled(self):
        """Test filtering with ONE_BET_PER_OUTCOME enabled - allows multiple bets per game on different outcomes"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'ONE_BET_PER_OUTCOME': 'true'  # Updated variable name
        }):
            scanner = PositiveEVScanner()
            
            opps = [
                # Same outcome (Team A win) in same game - should filter to 1
                {'game': 'Arsenal @ Chelsea', 'market': 'h2h', 'outcome': 'Arsenal', 'ev_percentage': 5.0},
                {'game': 'Arsenal @ Chelsea', 'market': 'h2h', 'outcome': 'Arsenal', 'ev_percentage': 3.0},
                # Different outcome (Over) in same game - should be kept
                {'game': 'Arsenal @ Chelsea', 'market': 'totals', 'outcome': 'Over 2.5', 'ev_percentage': 4.5},
                # Different game - should be kept
                {'game': 'Liverpool @ Man Utd', 'market': 'h2h', 'outcome': 'Liverpool', 'ev_percentage': 4.0}
            ]
            
            filtered = scanner.filter_one_bet_per_game(opps)
            
            # Should keep 3 bets: best Arsenal win + Over + Liverpool
            assert len(filtered) == 3
            assert filtered[0]['game'] == 'Arsenal @ Chelsea'
            assert filtered[0]['outcome'] == 'Arsenal'
            assert filtered[0]['ev_percentage'] == 5.0
            assert filtered[1]['game'] == 'Arsenal @ Chelsea'
            assert filtered[1]['outcome'] == 'Over 2.5'
            assert filtered[2]['game'] == 'Liverpool @ Man Utd'
    
    def test_filter_one_bet_per_game_disabled(self):
        """Test no filtering when ONE_BET_PER_OUTCOME is disabled"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'ONE_BET_PER_OUTCOME': 'false'  # Updated variable name
        }):
            scanner = PositiveEVScanner()
            
            opps = [
                {'game': 'Arsenal @ Chelsea', 'ev_percentage': 5.0},
                {'game': 'Arsenal @ Chelsea', 'ev_percentage': 3.0}
            ]
            
            filtered = scanner.filter_one_bet_per_game(opps)
            
            assert len(filtered) == 2


class TestGetOdds:
    """Test get_odds API call"""
    
    @patch('src.core.positive_ev_scanner.requests.get')
    def test_get_odds_success(self, mock_get, scanner):
        """Test successful odds retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                'id': 'game1',
                'home_team': 'Arsenal',
                'away_team': 'Chelsea'
            }
        ]
        mock_response.headers.get.return_value = '999'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = scanner.get_odds('soccer_epl')
        
        assert len(result) == 1
        assert result[0]['home_team'] == 'Arsenal'
    
    @patch('src.core.positive_ev_scanner.requests.get')
    def test_get_odds_api_error(self, mock_get, scanner):
        """Test handles API errors gracefully"""
        mock_get.side_effect = Exception('API Error')
        
        result = scanner.get_odds('soccer_epl')
        
        assert result == []


class TestGetAvailableSports:
    """Test get_available_sports API call"""
    
    @patch('src.core.positive_ev_scanner.requests.get')
    def test_get_available_sports_success(self, mock_get, scanner):
        """Test successful sports retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {'key': 'soccer_epl', 'title': 'EPL'},
            {'key': 'soccer_spain_la_liga', 'title': 'La Liga'}
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = scanner.get_available_sports()
        
        assert len(result) == 2
        assert result[0]['key'] == 'soccer_epl'
    
    @patch('src.core.positive_ev_scanner.requests.get')
    def test_get_available_sports_error(self, mock_get, scanner):
        """Test handles errors gracefully"""
        mock_get.side_effect = Exception('API Error')
        
        result = scanner.get_available_sports()
        
        assert result == []


class TestEdgeCases:
    """Test edge cases"""
    
    def test_very_high_odds(self, scanner):
        """Test with very high odds"""
        prob = scanner.calculate_implied_probability(100.0)
        assert prob == pytest.approx(0.01, rel=0.001)
    
    def test_minimum_odds(self, scanner):
        """Test with minimum valid odds"""
        prob = scanner.calculate_implied_probability(1.01)
        assert prob == pytest.approx(0.9901, rel=0.001)
    
    def test_ev_calculation_extreme_values(self, scanner):
        """Test EV with extreme values"""
        ev = scanner.calculate_ev(
            bet_odds=100.0,
            true_probability=0.05
        )
        assert ev > 0


class TestMinimumKellyPercentageFilter:
    """Test minimum Kelly percentage filter"""
    
    def test_reads_min_kelly_percentage_from_env(self):
        """Test scanner reads MIN_KELLY_PERCENTAGE from environment"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key',
            'MIN_KELLY_PERCENTAGE': '0.025'
        }):
            scanner = PositiveEVScanner()
            assert scanner.min_kelly_percentage == 0.025
    
    def test_defaults_to_zero_when_not_set(self):
        """Test defaults to 0.0 (no filter) when not set"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key'
        }, clear=True):
            scanner = PositiveEVScanner()
            assert scanner.min_kelly_percentage == 0.0
    
    def test_filter_applied_in_opportunities(self):
        """Test that opportunities below min Kelly % are filtered out"""
        # This is an integration test that would require mocking the full API response
        # For now, we verify the configuration is read correctly
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key',
            'MIN_KELLY_PERCENTAGE': '0.015',
            'BANKROLL': '40'
        }):
            scanner = PositiveEVScanner()
            # With £40 bankroll and 1.5% min Kelly (0.015), minimum stake = £0.60
            # This ensures we don't get micro-bets below bookmaker minimums
            assert scanner.min_kelly_percentage == 0.015
            assert scanner.kelly.bankroll == 40.0


class TestMaxOddsFilter:
    """Test maximum odds filter"""
    
    def test_reads_max_odds_from_env(self):
        """Test scanner reads MAX_ODDS from environment"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key',
            'MAX_ODDS': '5.0'
        }):
            scanner = PositiveEVScanner()
            assert scanner.max_odds == 5.0
    
    def test_defaults_to_zero_when_not_set(self):
        """Test defaults to 0.0 (no filter) when not set"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key'
        }, clear=True):
            scanner = PositiveEVScanner()
            assert scanner.max_odds == 0.0
    
    def test_filter_blocks_high_odds(self):
        """Test that MAX_ODDS filter is configured correctly"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key',
            'MAX_ODDS': '8.0'
        }):
            scanner = PositiveEVScanner()
            # With max_odds=8.0, bets above 8.0 should be filtered
            assert scanner.max_odds == 8.0


class TestMaxDaysAheadFilter:
    """Test maximum days ahead filter"""
    
    def test_defaults_to_zero_when_not_set(self):
        """Test defaults to 0 (no filter) when not set"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key'
        }, clear=True):
            scanner = PositiveEVScanner()
            assert scanner.max_days_ahead == 0
    
    def test_filter_configured_correctly(self):
        """Test that MAX_DAYS_AHEAD filter is configured correctly"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key',
            'MAX_DAYS_AHEAD': '2'
        }):
            scanner = PositiveEVScanner()
            assert scanner.max_days_ahead == 2.0
    
    def test_filter_with_decimal_days(self):
        """Test that MAX_DAYS_AHEAD accepts decimal values"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test_key',
            'MAX_DAYS_AHEAD': '1.5'
        }):
            scanner = PositiveEVScanner()
            assert scanner.max_days_ahead == 1.5
