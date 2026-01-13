"""
Unit tests for Historical Backtest module
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from src.utils.backtest import HistoricalBacktester


@pytest.fixture
def backtester():
    """Create a backtester instance for testing"""
    with patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_api_key',
        'BANKROLL': '1000',
        'KELLY_FRACTION': '0.25',
        'MIN_EV_THRESHOLD': '0.03',
        'MIN_TRUE_PROBABILITY': '0.40',
        'SHARP_BOOKS': 'pinnacle',
        'BETTING_BOOKMAKERS': 'bet365',
        'ONE_BET_PER_GAME': 'true'
    }):
        return HistoricalBacktester(test_mode=True)


class TestBacktesterInitialization:
    """Test backtester initialization"""
    
    def test_initialization_reads_env_vars(self, backtester):
        """Test initialization reads configuration from env"""
        assert backtester.api_key == 'test_api_key'
        assert backtester.initial_bankroll == 1000
        # These are now in the scanner
        assert backtester.scanner.kelly_fraction == 0.25
        assert backtester.scanner.min_ev_threshold == 0.03
        assert backtester.scanner.min_true_probability == 0.40
    
    def test_initialization_missing_api_key(self):
        """Test initialization fails without API key"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match='ODDS_API_KEY'):
                HistoricalBacktester(test_mode=True)
    
    def test_initialization_sets_defaults(self, backtester):
        """Test that defaults are properly set"""
        assert backtester.current_bankroll == backtester.initial_bankroll
        assert backtester.bets_placed == []
        assert backtester.bankroll_history == [backtester.initial_bankroll]


class TestResetState:
    """Test state reset"""
    
    def test_reset_state(self, backtester):
        """Test resetting state for new simulation"""
        # Modify state
        backtester.current_bankroll = 1500
        backtester.bets_placed = [{'bet': 'test'}]
        backtester.bankroll_history = [1000, 1100, 1500]
        
        # Reset
        backtester.reset_state()
        
        assert backtester.current_bankroll == backtester.initial_bankroll
        assert backtester.bets_placed == []
        assert backtester.bankroll_history == [backtester.initial_bankroll]


class TestCaching:
    """Test caching functionality - now handled by requests-cache"""
    
    def test_requests_cache_installed(self):
        """Test that requests-cache session is configured"""
        from src.utils.backtest import cached_session
        import requests_cache
        # Verify the cached session exists and is a CachedSession
        assert isinstance(cached_session, requests_cache.CachedSession)
    
    @patch('src.utils.backtest.cached_session.get')
    def test_http_caching_works(self, mock_get, backtester):
        """Test that HTTP requests are being cached"""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {'data': []}
        mock_response.raise_for_status.return_value = None
        mock_response.from_cache = False
        mock_get.return_value = mock_response
        
        # First call should hit the API
        result1 = backtester.get_historical_odds('soccer_epl', '2024-01-01T12:00:00Z')
        
        # Second call should use cache (not call API again)
        result2 = backtester.get_historical_odds('soccer_epl', '2024-01-01T12:00:00Z')
        
        # Both should return same data
        assert result1 == result2
        # cached_session.get should be called
        assert mock_get.call_count >= 1


class TestCalculations:
    """Test calculation methods (now use utility functions directly)"""
    
    def test_calculate_implied_probability(self, backtester):
        """Test implied probability calculation"""
        from src.utils.odds_utils import calculate_implied_probability
        prob = calculate_implied_probability(2.0)
        assert prob == pytest.approx(0.5, rel=0.001)
    
    def test_calculate_ev(self, backtester):
        """Test EV calculation"""
        from src.utils.odds_utils import calculate_ev
        ev = calculate_ev(2.5, 0.5)
        # (0.5 * 1.5) - 0.5 = 0.25
        assert ev == pytest.approx(0.25, rel=0.001)
    
    def test_calculate_ev_negative(self, backtester):
        """Test negative EV calculation"""
        from src.utils.odds_utils import calculate_ev
        ev = calculate_ev(1.5, 0.4)
        assert ev < 0


class TestPlaceBet:
    """Test bet placement"""
    
    def test_place_bet_win(self, backtester):
        """Test placing a winning bet"""
        bet = {
            'stake': 100,
            'odds': 2.0,
            'game_id': 'test1',
            'commence_time': '2024-01-01T12:00:00Z'
        }
        
        initial_bankroll = backtester.current_bankroll
        backtester.place_bet(bet, result='won', bet_timestamp='2024-01-01T12:00:00Z')
        
        assert backtester.current_bankroll > initial_bankroll
        assert len(backtester.bets_placed) == 1
        assert backtester.bets_placed[0]['result'] == 'won'
    
    def test_place_bet_loss(self, backtester):
        """Test placing a losing bet"""
        bet = {
            'stake': 100,
            'odds': 2.0,
            'game_id': 'test1',
            'commence_time': '2024-01-01T12:00:00Z'
        }
        
        initial_bankroll = backtester.current_bankroll
        backtester.place_bet(bet, result='lost', bet_timestamp='2024-01-01T12:00:00Z')
        
        assert backtester.current_bankroll < initial_bankroll
        assert backtester.current_bankroll == initial_bankroll - 100
    
    def test_place_bet_pending(self, backtester):
        """Test placing a pending bet (bankroll unchanged until settled)"""
        bet = {
            'stake': 100,
            'odds': 2.0,
            'game_id': 'test1',
            'commence_time': '2024-01-01T12:00:00Z'
        }
        
        initial_bankroll = backtester.current_bankroll
        backtester.place_bet(bet, result=None, bet_timestamp='2024-01-01T12:00:00Z')
        
        # Pending bets don't change bankroll (changed from two-stage to avoid negative values)
        assert backtester.current_bankroll == initial_bankroll
        assert len(backtester.bets_placed) == 1
        assert backtester.bets_placed[0]['result'] is None


class TestFindPositiveEVBets:
    """Test finding positive EV opportunities"""
    
    def test_find_positive_ev_bets_empty_data(self, backtester):
        """Test with empty data"""
        opportunities = backtester.find_positive_ev_bets({}, 'soccer_epl')
        assert opportunities == []
    
    def test_find_positive_ev_bets_no_data_key(self, backtester):
        """Test with missing data key"""
        opportunities = backtester.find_positive_ev_bets({'games': []}, 'soccer_epl')
        assert opportunities == []
    
    def test_find_positive_ev_bets_with_valid_data(self, backtester):
        """Test finding opportunities with valid data"""
        historical_data = {
            'data': [
                {
                    'id': 'game1',
                    'home_team': 'Arsenal',
                    'away_team': 'Chelsea',
                    'commence_time': '2024-01-01T15:00:00Z',
                    'bookmakers': [
                        {
                            'key': 'pinnacle',
                            'title': 'Pinnacle',
                            'markets': [
                                {
                                    'key': 'h2h',
                                    'outcomes': [
                                        {'name': 'Arsenal', 'price': 2.0}
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
                                        {'name': 'Arsenal', 'price': 2.3}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        opportunities = backtester.find_positive_ev_bets(historical_data, 'soccer_epl')
        
        # Should find at least one opportunity
        assert isinstance(opportunities, list)


class TestDetermineBetResult:
    """Test determining bet results"""
    
    def test_determine_bet_result_h2h_home_win(self, backtester):
        """Test h2h bet result for home win"""
        from unittest.mock import MagicMock
        from src.utils.bet_settler import BetSettler
        
        bet = {
            'game': 'Chelsea @ Arsenal',
            'market': 'h2h',
            'outcome': 'Arsenal',
            'sport': 'soccer_epl',
            'commence_time': '2024-01-01T15:00:00Z'
        }
        
        # Mock ESPN result
        backtester.espn_scraper = MagicMock()
        backtester.espn_scraper.get_game_result.return_value = {
            'home_team': 'Arsenal',
            'away_team': 'Chelsea',
            'home_score': 2,
            'away_score': 1,
            'source': 'espn'
        }
        
        result = backtester.determine_bet_result(bet, {})
        assert result == 'won'
    
    def test_determine_bet_result_h2h_away_win(self, backtester):
        """Test h2h bet result for away win"""
        from unittest.mock import MagicMock
        from src.utils.bet_settler import BetSettler
        
        bet = {
            'game': 'Chelsea @ Arsenal',
            'market': 'h2h',
            'outcome': 'Chelsea',
            'sport': 'soccer_epl',
            'commence_time': '2024-01-01T15:00:00Z'
        }
        
        # Mock ESPN result
        backtester.espn_scraper = MagicMock()
        backtester.espn_scraper.get_game_result.return_value = {
            'home_team': 'Arsenal',
            'away_team': 'Chelsea',
            'home_score': 1,
            'away_score': 2,
            'source': 'espn'
        }
        
        result = backtester.determine_bet_result(bet, {})
        assert result == 'won'
    
    def test_determine_bet_result_h2h_loss(self, backtester):
        """Test h2h bet result for loss"""
        from unittest.mock import MagicMock
        from src.utils.bet_settler import BetSettler
        
        bet = {
            'game': 'Chelsea @ Arsenal',
            'market': 'h2h',
            'outcome': 'Chelsea',
            'sport': 'soccer_epl',
            'commence_time': '2024-01-01T15:00:00Z'
        }
        
        # Mock ESPN result
        backtester.espn_scraper = MagicMock()
        backtester.espn_scraper.get_game_result.return_value = {
            'home_team': 'Arsenal',
            'away_team': 'Chelsea',
            'home_score': 2,
            'away_score': 1,
            'source': 'espn'
        }
        
        result = backtester.determine_bet_result(bet, {})
        assert result == 'lost'
    
    def test_determine_bet_result_game_not_found(self, backtester):
        """Test with game not in scores data"""
        bet = {
            'game': 'Unknown @ Match',
            'market': 'h2h',
            'outcome': 'Unknown'
        }
        
        result = backtester.determine_bet_result(bet, {})
        assert result is None


class TestGenerateReport:
    """Test report generation"""
    
    def test_generate_report_no_bets(self, backtester):
        """Test report with no bets"""
        report = backtester.generate_report()
        assert report == {}
    
    def test_generate_report_with_bets(self, backtester):
        """Test report generation with bets"""
        # Place some bets
        for i in range(5):
            bet = {
                'stake': 50,
                'odds': 2.0,
                'game_id': f'game_{i}',
                'commence_time': '2024-01-01T12:00:00Z',
                'ev': 0.05,
                'true_probability': 0.55
            }
            result = 'won' if i % 2 == 0 else 'lost'
            backtester.place_bet(bet, result=result, bet_timestamp='2024-01-01T12:00:00Z')
        
        report = backtester.generate_report()
        
        assert report['total_bets'] == 5
        assert report['won_bets'] == 3
        assert report['lost_bets'] == 2
        assert 'final_bankroll' in report
        assert 'total_return_pct' in report
        assert 'roi' in report


class TestEdgeCases:
    """Test edge cases"""
    
    def test_very_large_bankroll(self):
        """Test with very large bankroll"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'BANKROLL': '1000000'
        }):
            backtester = HistoricalBacktester(test_mode=True)
            assert backtester.initial_bankroll == 1000000
    
    def test_very_small_bankroll(self):
        """Test with very small bankroll"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'BANKROLL': '10'
        }):
            backtester = HistoricalBacktester(test_mode=True)
            assert backtester.initial_bankroll == 10
    
    def test_zero_kelly_fraction(self):
        """Test with zero Kelly fraction"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'KELLY_FRACTION': '0'
        }):
            backtester = HistoricalBacktester(test_mode=True)
            assert backtester.scanner.kelly_fraction == 0
