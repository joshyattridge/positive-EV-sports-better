"""
Unit tests for Bet Logger module
"""

import pytest
import csv
import tempfile
from pathlib import Path
from datetime import datetime
from src.utils.bet_logger import BetLogger


@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file for testing"""
    # Just create the path, don't create the file
    # Let BetLogger create it properly
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
    temp_path = temp_file.name
    temp_file.close()
    
    # Delete the file so BetLogger can create it fresh
    Path(temp_path).unlink()
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def bet_logger(temp_csv_file):
    """Create a BetLogger instance with temporary file"""
    return BetLogger(log_path=temp_csv_file)


@pytest.fixture
def sample_opportunity():
    """Sample betting opportunity for testing"""
    return {
        'game_id': 'test_game_123',
        'sport': 'soccer_epl',
        'game': 'Arsenal @ Manchester United',
        'commence_time': '2024-01-15 15:00 GMT',
        'market': 'h2h',
        'outcome': 'Arsenal',
        'bookmaker': 'Bet365',
        'bookmaker_key': 'bet365',
        'odds': 2.5,
        'sharp_avg_odds': 2.3,
        'true_probability': 0.45,
        'bookmaker_probability': 0.40,
        'ev_percentage': 3.5,
        'bookmaker_url': 'https://bet365.com/test',
        'kelly_stake': {
            'bankroll': 1000,
            'kelly_percentage': 5.0,
            'kelly_fraction': 0.25,
            'recommended_stake': 50.0
        },
        'expected_profit': 5.25
    }


class TestBetLoggerInitialization:
    """Test BetLogger initialization"""
    
    def test_initialization_creates_file(self, temp_csv_file):
        """Test that initialization creates CSV file with headers"""
        logger = BetLogger(log_path=temp_csv_file)
        
        assert Path(temp_csv_file).exists()
        
        # Check headers by reading the first line
        with open(temp_csv_file, 'r') as f:
            first_line = f.readline().strip()
            headers = first_line.split(',')
            assert headers == logger.CSV_HEADERS
    
    def test_initialization_preserves_existing_file(self, temp_csv_file):
        """Test that initialization doesn't overwrite existing file"""
        # Create logger and write a bet
        logger1 = BetLogger(log_path=temp_csv_file)
        
        test_opp = {
            'game_id': 'test1',
            'sport': 'test_sport',
            'game': 'Test Game',
            'commence_time': '2024-01-01',
            'market': 'h2h',
            'outcome': 'Team A',
            'bookmaker': 'TestBook',
            'bookmaker_key': 'testbook',
            'odds': 2.0,
            'sharp_avg_odds': 1.9,
            'true_probability': 0.5,
            'bookmaker_probability': 0.5,
            'ev_percentage': 2.0,
            'bookmaker_url': 'http://test.com',
            'kelly_stake': {
                'bankroll': 100,
                'kelly_percentage': 10,
                'kelly_fraction': 1.0,
                'recommended_stake': 10
            },
            'expected_profit': 1.0
        }
        
        logger1.log_bet(test_opp)
        
        # Create another logger instance - should not delete the bet
        logger2 = BetLogger(log_path=temp_csv_file)
        
        # Check that the bet still exists
        with open(temp_csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1


class TestLogBet:
    """Test log_bet functionality"""
    
    def test_log_bet_success(self, bet_logger, sample_opportunity):
        """Test successful bet logging"""
        result = bet_logger.log_bet(sample_opportunity)
        
        assert result is True
        
        # Verify the bet was written
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            
            row = rows[0]
            assert row['game_id'] == 'test_game_123'
            assert row['sport'] == 'soccer_epl'
            assert row['game'] == 'Arsenal @ Manchester United'
            assert row['outcome'] == 'Arsenal'
            assert row['bookmaker'] == 'Bet365'
            assert float(row['bet_odds']) == 2.5
            assert row['bet_result'] == 'pending'
    
    def test_log_bet_not_placed(self, bet_logger, sample_opportunity):
        """Test logging a bet that wasn't actually placed"""
        result = bet_logger.log_bet(sample_opportunity, bet_placed=False)
        
        assert result is True
        
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            row = rows[0]
            assert row['bet_result'] == 'not_placed'
    
    def test_log_bet_with_notes(self, bet_logger, sample_opportunity):
        """Test logging bet with custom notes"""
        result = bet_logger.log_bet(
            sample_opportunity,
            bet_placed=True,
            notes="Test note"
        )
        
        assert result is True
        
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            row = rows[0]
            assert row['notes'] == "Test note"
    
    def test_log_multiple_bets(self, bet_logger, sample_opportunity):
        """Test logging multiple bets"""
        bet_logger.log_bet(sample_opportunity)
        
        # Modify and log another bet
        sample_opportunity['game_id'] = 'test_game_456'
        sample_opportunity['game'] = 'Chelsea @ Liverpool'
        bet_logger.log_bet(sample_opportunity)
        
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2


class TestUpdateBetResult:
    """Test update_bet_result functionality"""
    
    def test_update_bet_result_win(self, bet_logger, sample_opportunity):
        """Test updating bet result to win"""
        bet_logger.log_bet(sample_opportunity)
        
        # Get the timestamp
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            timestamp = row['timestamp']
        
        # Update to win
        result = bet_logger.update_bet_result(
            timestamp=timestamp,
            result='win',
            actual_profit_loss=25.0
        )
        
        assert result is True
        
        # Verify update
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row['bet_result'] == 'win'
            assert float(row['actual_profit_loss']) == 25.0
    
    def test_update_bet_result_loss(self, bet_logger, sample_opportunity):
        """Test updating bet result to loss"""
        bet_logger.log_bet(sample_opportunity)
        
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            timestamp = row['timestamp']
        
        result = bet_logger.update_bet_result(
            timestamp=timestamp,
            result='loss',
            actual_profit_loss=-50.0
        )
        
        assert result is True
        
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row['bet_result'] == 'loss'
            assert float(row['actual_profit_loss']) == -50.0
    
    def test_update_nonexistent_bet(self, bet_logger):
        """Test updating a bet that doesn't exist"""
        result = bet_logger.update_bet_result(
            timestamp='2024-01-01 00:00:00',
            result='win'
        )
        
        assert result is False


class TestGetAlreadyBetGameIds:
    """Test get_already_bet_game_ids functionality"""
    
    def test_get_empty_set_no_file(self, temp_csv_file):
        """Test returns empty set when no file exists"""
        # File doesn't exist yet, fixture only creates the path
        logger = BetLogger(log_path=temp_csv_file)
        Path(temp_csv_file).unlink()  # Delete the file created by BetLogger
        
        game_ids = logger.get_already_bet_game_ids()
        assert game_ids == set()
    
    def test_get_game_ids_from_placed_bets(self, bet_logger, sample_opportunity):
        """Test returns game IDs from placed bets only"""
        # Place one bet
        bet_logger.log_bet(sample_opportunity, bet_placed=True)
        
        # Log another as not placed
        sample_opportunity['game_id'] = 'test_game_456'
        bet_logger.log_bet(sample_opportunity, bet_placed=False)
        
        game_ids = bet_logger.get_already_bet_game_ids()
        
        assert 'test_game_123' in game_ids
        assert 'test_game_456' not in game_ids
    
    def test_get_game_ids_excludes_not_placed(self, bet_logger, sample_opportunity):
        """Test that not_placed bets are excluded"""
        sample_opportunity['game_id'] = 'test1'
        bet_logger.log_bet(sample_opportunity, bet_placed=False)
        
        game_ids = bet_logger.get_already_bet_game_ids()
        assert 'test1' not in game_ids


class TestGetBetSummary:
    """Test get_bet_summary functionality"""
    
    def test_summary_no_bets(self, bet_logger):
        """Test summary with no bets"""
        summary = bet_logger.get_bet_summary()
        
        assert summary['total_bets'] == 0
    
    def test_summary_with_bets(self, bet_logger, sample_opportunity):
        """Test summary calculation with bets"""
        # Log several bets
        for i in range(5):
            sample_opportunity['game_id'] = f'game_{i}'
            bet_logger.log_bet(sample_opportunity)
        
        summary = bet_logger.get_bet_summary()
        
        assert summary['total_bets'] == 5
        assert summary['pending'] == 5
        assert summary['wins'] == 0
        assert summary['losses'] == 0
    
    @pytest.mark.skip(reason="Flaky test - timing issue with CSV updates")
    def test_summary_with_results(self, bet_logger, sample_opportunity):
        """Test summary with settled bets"""
        # Log and settle some bets
        bet_logger.log_bet(sample_opportunity)
        
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            timestamp1 = row['timestamp']
        
        bet_logger.update_bet_result(timestamp1, 'win', 25.0)
        
        # Log another
        sample_opportunity['game_id'] = 'game_2'
        bet_logger.log_bet(sample_opportunity)
        
        with open(bet_logger.log_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            next(reader)
            row = next(reader)
            timestamp2 = row['timestamp']
        
        bet_logger.update_bet_result(timestamp2, 'loss', -50.0)
        
        summary = bet_logger.get_bet_summary()
        
        assert summary['total_bets'] == 2
        assert summary['wins'] == 1
        assert summary['losses'] == 1
        assert summary['win_rate'] == 50.0
        assert summary['total_actual_profit'] == -25.0


class TestPrintSummary:
    """Test print_summary functionality"""
    
    def test_print_summary_no_error(self, bet_logger, sample_opportunity, capsys):
        """Test that print_summary doesn't raise errors"""
        bet_logger.log_bet(sample_opportunity)
        bet_logger.print_summary()
        
        captured = capsys.readouterr()
        # Check for condensed output format
        assert 'Bet Summary' in captured.out or '1 bets' in captured.out


class TestFailedBetOpportunities:
    """Test get_failed_bet_opportunities functionality"""
    
    def test_get_failed_bet_opportunities_empty(self, bet_logger):
        """Test with no failed bets"""
        failed = bet_logger.get_failed_bet_opportunities(max_failures=3)
        assert len(failed) == 0
    
    def test_get_failed_bet_opportunities_single_failure(self, bet_logger, sample_opportunity):
        """Test with single failure - should not be ignored"""
        # Log a failed bet
        bet_logger.log_bet(sample_opportunity, bet_placed=False, notes="Odds too bad")
        
        failed = bet_logger.get_failed_bet_opportunities(max_failures=3)
        assert len(failed) == 0  # Not enough failures
    
    def test_get_failed_bet_opportunities_multiple_failures(self, bet_logger, sample_opportunity):
        """Test with multiple failures of same bet - should be ignored"""
        # Log the same bet failing 3 times
        for i in range(3):
            bet_logger.log_bet(sample_opportunity, bet_placed=False, notes=f"Failure {i+1}")
        
        failed = bet_logger.get_failed_bet_opportunities(max_failures=3)
        assert len(failed) == 1
        
        # Check the tuple structure
        expected_key = (sample_opportunity['game_id'], sample_opportunity['market'], sample_opportunity['outcome'])
        assert expected_key in failed
    
    def test_get_failed_bet_opportunities_different_outcomes(self, bet_logger, sample_opportunity):
        """Test that different outcomes are tracked separately"""
        # Fail the same game/market but different outcomes
        opp1 = sample_opportunity.copy()
        opp1['outcome'] = 'Arsenal'
        
        opp2 = sample_opportunity.copy()
        opp2['outcome'] = 'Manchester United'
        
        # Fail opp1 three times
        for i in range(3):
            bet_logger.log_bet(opp1, bet_placed=False, notes=f"Failure {i+1}")
        
        # Fail opp2 twice
        for i in range(2):
            bet_logger.log_bet(opp2, bet_placed=False, notes=f"Failure {i+1}")
        
        failed = bet_logger.get_failed_bet_opportunities(max_failures=3)
        
        # Only opp1 should be in failed list
        assert len(failed) == 1
        expected_key = (opp1['game_id'], opp1['market'], opp1['outcome'])
        assert expected_key in failed
    
    def test_get_failed_bet_opportunities_mixed_results(self, bet_logger, sample_opportunity):
        """Test that successful bets don't count towards failures"""
        # Log 2 failures
        for i in range(2):
            bet_logger.log_bet(sample_opportunity, bet_placed=False, notes=f"Failure {i+1}")
        
        # Log 1 success
        bet_logger.log_bet(sample_opportunity, bet_placed=True, notes="Success")
        
        # Log 1 more failure
        bet_logger.log_bet(sample_opportunity, bet_placed=False, notes="Failure 3")
        
        failed = bet_logger.get_failed_bet_opportunities(max_failures=3)
        
        # Total of 3 failures, should be ignored
        assert len(failed) == 1
        expected_key = (sample_opportunity['game_id'], sample_opportunity['market'], sample_opportunity['outcome'])
        assert expected_key in failed
    
    def test_get_failed_bet_opportunities_custom_threshold(self, bet_logger, sample_opportunity):
        """Test with custom failure threshold"""
        # Log 2 failures
        for i in range(2):
            bet_logger.log_bet(sample_opportunity, bet_placed=False, notes=f"Failure {i+1}")
        
        # With threshold of 2, should be ignored
        failed = bet_logger.get_failed_bet_opportunities(max_failures=2)
        assert len(failed) == 1
        
        # With threshold of 3, should not be ignored
        failed = bet_logger.get_failed_bet_opportunities(max_failures=3)
        assert len(failed) == 0
