"""
Unit tests for manage_bets.py script
"""

import pytest
import csv
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from scripts.manage_bets import (
    view_summary,
    list_pending_bets,
    update_bet_result,
    export_to_analysis
)


@pytest.fixture
def temp_bet_history():
    """Create a temporary bet history CSV file"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
    temp_path = temp_file.name
    temp_file.close()
    
    # Create a bet history file with sample data
    from src.utils.bet_logger import BetLogger
    logger = BetLogger(log_path=temp_path)
    
    # Add some sample bets
    sample_bets = [
        {
            'game_id': 'game1',
            'sport': 'soccer_epl',
            'game': 'Arsenal @ Chelsea',
            'commence_time': '2024-01-01 15:00',
            'market': 'h2h',
            'outcome': 'Arsenal',
            'bookmaker': 'Bet365',
            'bookmaker_key': 'bet365',
            'odds': 2.5,
            'sharp_avg_odds': 2.3,
            'true_probability': 0.45,
            'bookmaker_probability': 0.40,
            'ev_percentage': 3.5,
            'bookmaker_url': 'https://bet365.com',
            'kelly_stake': {
                'bankroll': 1000,
                'kelly_percentage': 5.0,
                'kelly_fraction': 0.25,
                'recommended_stake': 50.0
            },
            'expected_profit': 5.25
        },
        {
            'game_id': 'game2',
            'sport': 'soccer_epl',
            'game': 'Liverpool @ Man Utd',
            'commence_time': '2024-01-02 15:00',
            'market': 'h2h',
            'outcome': 'Liverpool',
            'bookmaker': 'William Hill',
            'bookmaker_key': 'williamhill',
            'odds': 2.0,
            'sharp_avg_odds': 1.9,
            'true_probability': 0.52,
            'bookmaker_probability': 0.50,
            'ev_percentage': 2.0,
            'bookmaker_url': 'https://williamhill.com',
            'kelly_stake': {
                'bankroll': 1000,
                'kelly_percentage': 4.0,
                'kelly_fraction': 0.25,
                'recommended_stake': 40.0
            },
            'expected_profit': 4.0
        }
    ]
    
    for bet in sample_bets:
        logger.log_bet(bet, bet_placed=True)
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


class TestViewSummary:
    """Test view_summary function"""
    
    def test_view_summary(self, temp_bet_history, capsys):
        """Test that view_summary runs without errors"""
        with patch('scripts.manage_bets.BetRepository') as mock_repo_class:
            mock_repo = Mock()
            mock_repo.log_path = Path(temp_bet_history)
            mock_repo_class.return_value = mock_repo
            
            view_summary()
            
            # Should call print_summary
            mock_repo.print_summary.assert_called_once()


class TestListPendingBets:
    """Test list_pending_bets function"""
    
    def test_list_pending_bets_with_pending(self, temp_bet_history, capsys):
        """Test listing pending bets"""
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_logger.log_path = Path(temp_bet_history)
            mock_logger_class.return_value = mock_logger
            
            list_pending_bets()
            
            captured = capsys.readouterr()
            assert 'PENDING BETS' in captured.out
    
    def test_list_pending_bets_no_file(self, capsys):
        """Test listing pending bets when file doesn't exist"""
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_logger.log_path = mock_path
            mock_logger_class.return_value = mock_logger
            
            list_pending_bets()
            
            captured = capsys.readouterr()
            assert 'No bet history file found' in captured.out


class TestUpdateBetResult:
    """Test update_bet_result function"""
    
    def test_update_bet_result_success(self, capsys):
        """Test successful bet result update"""
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_logger.update_bet_result.return_value = True
            mock_logger_class.return_value = mock_logger
            
            update_bet_result('2024-01-01 12:00:00', 'win', 25.0)
            
            captured = capsys.readouterr()
            assert 'updated successfully' in captured.out
            assert 'Winner' in captured.out
    
    def test_update_bet_result_invalid_result(self, capsys):
        """Test update with invalid result"""
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger
            
            update_bet_result('2024-01-01 12:00:00', 'invalid', 25.0)
            
            captured = capsys.readouterr()
            assert 'Invalid result' in captured.out
    
    def test_update_bet_result_loss(self, capsys):
        """Test updating to loss"""
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_logger.update_bet_result.return_value = True
            mock_logger_class.return_value = mock_logger
            
            update_bet_result('2024-01-01 12:00:00', 'loss', -50.0)
            
            captured = capsys.readouterr()
            assert 'updated successfully' in captured.out
            assert 'Lost' in captured.out


class TestExportToAnalysis:
    """Test export_to_analysis function"""
    
    def test_export_to_analysis_success(self, temp_bet_history, capsys):
        """Test successful export"""
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_logger.log_path = Path(temp_bet_history)
            mock_logger_class.return_value = mock_logger
            
            export_to_analysis()
            
            captured = capsys.readouterr()
            # Should print success message
            assert 'Exported' in captured.out or 'No bet history' in captured.out
    
    def test_export_to_analysis_no_file(self, capsys):
        """Test export when no bet history exists"""
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_logger.log_path = mock_path
            mock_logger_class.return_value = mock_logger
            
            export_to_analysis()
            
            captured = capsys.readouterr()
            assert 'No bet history file found' in captured.out


class TestInteractiveUpdate:
    """Test interactive_update function"""
    
    def test_interactive_update_cancel(self, temp_bet_history, capsys):
        """Test canceling interactive update"""
        from scripts.manage_bets import interactive_update
        from pathlib import Path
        
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_logger.log_path = Path(temp_bet_history)  # Use Path object
            mock_logger_class.return_value = mock_logger
            
            with patch('builtins.input', return_value=''):
                interactive_update()
                
                captured = capsys.readouterr()
                assert 'Cancelled' in captured.out or 'pending' in captured.out.lower()


class TestPrintUsage:
    """Test print_usage function"""
    
    def test_print_usage(self, capsys):
        """Test that print_usage displays help"""
        from scripts.manage_bets import print_usage
        
        print_usage()
        
        captured = capsys.readouterr()
        assert 'Usage' in captured.out
        assert 'summary' in captured.out
        assert 'pending' in captured.out
        assert 'update' in captured.out
        assert 'export' in captured.out


class TestEdgeCases:
    """Test edge cases"""
    
    def test_update_with_none_profit_loss(self, capsys):
        """Test update without profit/loss value"""
        with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
            mock_logger = Mock()
            mock_logger.update_bet_result.return_value = True
            mock_logger_class.return_value = mock_logger
            
            update_bet_result('2024-01-01 12:00:00', 'void', None)
            
            # Should complete without error
            captured = capsys.readouterr()
            assert 'updated successfully' in captured.out
    
    def test_list_pending_bets_empty_file(self, capsys):
        """Test listing pending bets from empty file"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        temp_path = temp_file.name
        
        # Create empty file with just headers
        from src.utils.bet_logger import BetLogger
        logger = BetLogger(log_path=temp_path)
        
        try:
            with patch('scripts.manage_bets.BetLogger') as mock_logger_class:
                mock_logger = Mock()
                mock_logger.log_path = Path(temp_path)
                mock_logger_class.return_value = mock_logger
                
                list_pending_bets()
                
                captured = capsys.readouterr()
                # Should handle gracefully
                assert 'PENDING BETS' in captured.out or 'No bet history' in captured.out
        finally:
            Path(temp_path).unlink(missing_ok=True)
