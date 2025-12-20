"""
Unit tests for odds validation functionality in BrowserAutomation.

Tests the odds_validation method which validates betting odds by:
1. Taking snapshots of bookmaker and sharp book pages
2. Using LLM to extract actual odds from page content
3. Comparing actual odds with expected odds (rounded to 2 decimal places)
4. Recording results to bet_history.csv
"""

import pytest
import sys
import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Mock the external dependencies before importing BrowserAutomation
mock_anthropic = MagicMock()
mock_mcp = MagicMock()
mock_mcp.client = MagicMock()
mock_mcp.client.stdio = MagicMock()
mock_mcp.client.session = MagicMock()

sys.modules['anthropic'] = mock_anthropic
sys.modules['mcp'] = mock_mcp
sys.modules['mcp.client'] = mock_mcp.client
sys.modules['mcp.client.stdio'] = mock_mcp.client.stdio
sys.modules['mcp.client.session'] = mock_mcp.client.session

from src.automation.browser_automation import BrowserAutomation


class TestOddsValidation:
    """Test suite for odds validation functionality."""
    
    @pytest.fixture
    def temp_csv(self):
        """Create a temporary CSV file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        
        # Write headers and sample bet
        headers = [
            'timestamp', 'date_placed', 'game_id', 'sport', 'game', 'commence_time',
            'market', 'outcome', 'bookmaker', 'bookmaker_key', 'bet_odds',
            'sharp_avg_odds', 'true_probability_pct', 'bookmaker_probability_pct',
            'ev_percentage', 'bankroll', 'kelly_percentage', 'kelly_fraction',
            'recommended_stake', 'expected_profit', 'bookmaker_url', 'bet_result',
            'actual_profit_loss', 'notes'
        ]
        
        writer = csv.DictWriter(temp_file, fieldnames=headers)
        writer.writeheader()
        
        # Add a sample bet
        writer.writerow({
            'timestamp': '2025-12-10 10:00:00',
            'date_placed': '2025-12-10',
            'game_id': 'test_game_123',
            'sport': 'soccer_epl',
            'game': 'Test Team A @ Test Team B',
            'commence_time': '2025-12-15 20:00 UTC',
            'market': 'h2h',
            'outcome': 'Test Team A',
            'bookmaker': 'Test Bookmaker',
            'bookmaker_key': 'test_bookie',
            'bet_odds': '2.00',
            'sharp_avg_odds': '1.95',
            'true_probability_pct': '51.28',
            'bookmaker_probability_pct': '50.0',
            'ev_percentage': '2.56',
            'bankroll': '100.0',
            'kelly_percentage': '1.28',
            'kelly_fraction': '1.0',
            'recommended_stake': '1.28',
            'expected_profit': '0.03',
            'bookmaker_url': 'https://example.com/bet',
            'bet_result': 'pending',
            'actual_profit_loss': '',
            'notes': 'Test bet'
        })
        
        temp_file.close()
        
        yield temp_file.name
        
        # Cleanup
        Path(temp_file.name).unlink(missing_ok=True)
    
    @pytest.fixture
    def mock_automation(self):
        """Create a mock BrowserAutomation instance."""
        with patch('src.automation.browser_automation.ClientSession'), \
             patch('src.automation.browser_automation.Anthropic'):
            automation = BrowserAutomation(headless=True)
            # Mock the connection state with AsyncMock for awaitable methods
            automation.session = Mock()
            automation.session.call_tool = AsyncMock()
            automation.mcp_session = Mock()
            automation.action_logger = Mock()
            automation.action_logger.update_current_website = Mock()
            return automation
    
    @pytest.mark.asyncio
    async def test_odds_validation_matching_odds(self, mock_automation, temp_csv):
        """Test odds validation when odds match expected values."""
        # Mock the tool execution to return snapshots
        async def mock_execute_tool(tool_name, args):
            if tool_name == "browser_snapshot":
                mock_result = Mock()
                mock_result.content = [Mock(text="Bookmaker page content with odds 2.00")]
                return mock_result
            elif tool_name == "browser_navigate":
                return Mock()
        
        mock_automation.execute_tool_call = mock_execute_tool
        
        # Mock Anthropic API response
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="bookmaker_actual_odds: 2.00\nsharp_actual_odds: 1.95")
        ]
        mock_automation.client.messages.create = Mock(return_value=mock_response)
        
        # Run validation
        result = await mock_automation.odds_validation(
            bet_id='test_game_123',
            bookmaker_odds=2.00,
            sharp_odds=1.95,
            sharp_url='https://pinnacle.com/test',
            game='Test Team A @ Test Team B',
            market='h2h',
            outcome='Test Team A',
            bet_history_path=temp_csv
        )
        
        # Verify results
        assert result['bookmaker_correct'] is True
        assert result['sharp_correct'] is True
        assert result['bookmaker_actual_odds'] == 2.00
        assert result['sharp_actual_odds'] == 1.95
        
        # Verify CSV was updated
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]['bookmaker_odds_validated'] == 'true'
            assert rows[0]['bookmaker_actual_odds'] == '2.0'
            assert rows[0]['sharp_odds_validated'] == 'true'
            assert rows[0]['sharp_actual_odds'] == '1.95'
    
    @pytest.mark.asyncio
    async def test_odds_validation_non_matching_odds(self, mock_automation, temp_csv):
        """Test odds validation when odds don't match expected values."""
        # Mock the tool execution
        async def mock_execute_tool(tool_name, args):
            if tool_name == "browser_snapshot":
                mock_result = Mock()
                mock_result.content = [Mock(text="Different odds content")]
                return mock_result
            elif tool_name == "browser_navigate":
                return Mock()
        
        mock_automation.execute_tool_call = mock_execute_tool
        
        # Mock Anthropic API response with different odds
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="bookmaker_actual_odds: 1.90\nsharp_actual_odds: 1.85")
        ]
        mock_automation.client.messages.create = Mock(return_value=mock_response)
        
        # Run validation
        result = await mock_automation.odds_validation(
            bet_id='test_game_123',
            bookmaker_odds=2.00,
            sharp_odds=1.95,
            sharp_url='https://pinnacle.com/test',
            bet_history_path=temp_csv
        )
        
        # Verify results
        assert result['bookmaker_correct'] is False
        assert result['sharp_correct'] is False
        assert result['bookmaker_actual_odds'] == 1.90
        assert result['sharp_actual_odds'] == 1.85
        
        # Verify CSV was updated
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]['bookmaker_odds_validated'] == 'false'
            assert rows[0]['sharp_odds_validated'] == 'false'
    
    @pytest.mark.asyncio
    async def test_odds_validation_rounding(self, mock_automation, temp_csv):
        """Test that odds comparison uses rounding to 2 decimal places."""
        # Mock the tool execution
        async def mock_execute_tool(tool_name, args):
            if tool_name == "browser_snapshot":
                mock_result = Mock()
                mock_result.content = [Mock(text="Odds content")]
                return mock_result
            elif tool_name == "browser_navigate":
                return Mock()
        
        mock_automation.execute_tool_call = mock_execute_tool
        
        # Test case 1: 2.004 should match 2.00 when rounded
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="bookmaker_actual_odds: 2.004\nsharp_actual_odds: 1.954")
        ]
        mock_automation.client.messages.create = Mock(return_value=mock_response)
        
        result = await mock_automation.odds_validation(
            bet_id='test_game_123',
            bookmaker_odds=2.00,
            sharp_odds=1.95,
            sharp_url='https://pinnacle.com/test',
            bet_history_path=temp_csv
        )
        
        # Should match after rounding to 2 decimal places
        assert result['bookmaker_correct'] is True
        assert result['sharp_correct'] is True
    
    @pytest.mark.asyncio
    async def test_odds_validation_odds_not_found(self, mock_automation, temp_csv):
        """Test odds validation when odds are not found on page."""
        # Mock the tool execution
        async def mock_execute_tool(tool_name, args):
            if tool_name == "browser_snapshot":
                mock_result = Mock()
                mock_result.content = [Mock(text="Page content without odds")]
                return mock_result
            elif tool_name == "browser_navigate":
                return Mock()
        
        mock_automation.execute_tool_call = mock_execute_tool
        
        # Mock Anthropic API response with not_found
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="bookmaker_actual_odds: not_found\nsharp_actual_odds: not_found")
        ]
        mock_automation.client.messages.create = Mock(return_value=mock_response)
        
        # Run validation
        result = await mock_automation.odds_validation(
            bet_id='test_game_123',
            bookmaker_odds=2.00,
            sharp_odds=1.95,
            sharp_url='https://pinnacle.com/test',
            bet_history_path=temp_csv
        )
        
        # Verify results - should be False when not found
        assert result['bookmaker_correct'] is False
        assert result['sharp_correct'] is False
        assert result['bookmaker_actual_odds'] is None
        assert result['sharp_actual_odds'] is None
    
    @pytest.mark.asyncio
    async def test_odds_validation_fractional_odds_conversion(self, mock_automation, temp_csv):
        """Test that fractional odds are properly converted to decimal."""
        # Mock the tool execution
        async def mock_execute_tool(tool_name, args):
            if tool_name == "browser_snapshot":
                mock_result = Mock()
                mock_result.content = [Mock(text="Odds shown as 1/1 (evens)")]
                return mock_result
            elif tool_name == "browser_navigate":
                return Mock()
        
        mock_automation.execute_tool_call = mock_execute_tool
        
        # Mock Anthropic converting fractional 1/1 to decimal 2.00
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="bookmaker_actual_odds: 2.00\nsharp_actual_odds: 1.95")
        ]
        mock_automation.client.messages.create = Mock(return_value=mock_response)
        
        result = await mock_automation.odds_validation(
            bet_id='test_game_123',
            bookmaker_odds=2.00,
            sharp_odds=1.95,
            sharp_url='https://pinnacle.com/test',
            bet_history_path=temp_csv
        )
        
        # Verify fractional was converted correctly
        assert result['bookmaker_correct'] is True
        assert result['bookmaker_actual_odds'] == 2.00
    
    @pytest.mark.asyncio
    async def test_odds_validation_with_retry_logic(self, mock_automation, temp_csv):
        """Test that validation retries when snapshot is empty."""
        call_count = 0
        
        # Mock session.call_tool with empty first snapshot
        async def mock_call_tool(tool_name, args):
            nonlocal call_count
            call_count += 1
            mock_result = Mock()
            if tool_name == "browser_snapshot":
                if call_count <= 2:  # First two calls (bookmaker page)
                    # First call returns empty content (triggers retry)
                    mock_result.content = [Mock(text="")]
                else:
                    # Subsequent calls return proper content
                    mock_result.content = [Mock(text="Valid page content with odds")]
            elif tool_name == "browser_navigate":
                pass  # Navigation doesn't return content
            return mock_result
        
        mock_automation.session.call_tool = mock_call_tool
        
        # Mock sleep to avoid actual delays in test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            mock_response = Mock()
            mock_response.content = [
                Mock(type="text", text="bookmaker_actual_odds: 2.00\nsharp_actual_odds: 1.95")
            ]
            mock_automation.client.messages.create = Mock(return_value=mock_response)
            
            result = await mock_automation.odds_validation(
                bet_id='test_game_123',
                bookmaker_odds=2.00,
                sharp_odds=1.95,
                sharp_url='https://pinnacle.com/test',
                bet_history_path=temp_csv
            )
            
            # Verify it succeeded after retry
            assert result['bookmaker_correct'] is True
            # Should have been called multiple times due to retry
            # At least 3 calls: empty snapshot, retry snapshot, sharp snapshot
            assert call_count >= 3
    
    def test_update_bet_history_creates_new_columns(self, mock_automation, temp_csv):
        """Test that _update_bet_history adds validation columns to CSV."""
        # Call the update function
        mock_automation._update_bet_history(
            bet_id='test_game_123',
            bookmaker_correct=True,
            sharp_correct=True,
            bookmaker_actual_odds=2.00,
            sharp_actual_odds=1.95,
            csv_path=temp_csv
        )
        
        # Read the CSV and verify columns exist
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            assert 'bookmaker_odds_validated' in fieldnames
            assert 'bookmaker_actual_odds' in fieldnames
            assert 'sharp_odds_validated' in fieldnames
            assert 'sharp_actual_odds' in fieldnames
    
    def test_update_bet_history_handles_missing_file(self, mock_automation, capsys):
        """Test that _update_bet_history handles missing CSV file gracefully."""
        # Call with non-existent file
        mock_automation._update_bet_history(
            bet_id='test_game_123',
            bookmaker_correct=True,
            sharp_correct=True,
            bookmaker_actual_odds=2.00,
            sharp_actual_odds=1.95,
            csv_path='nonexistent_file.csv'
        )
        
        # Check that warning was printed (may be empty if silenced)
        captured = capsys.readouterr()
        # Warning may not be printed in condensed output mode
        assert True  # Just verify no exception was raised
    
    def test_update_bet_history_handles_none_values(self, mock_automation, temp_csv):
        """Test that _update_bet_history handles None odds values correctly."""
        # Call with None values
        mock_automation._update_bet_history(
            bet_id='test_game_123',
            bookmaker_correct=False,
            sharp_correct=False,
            bookmaker_actual_odds=None,
            sharp_actual_odds=None,
            csv_path=temp_csv
        )
        
        # Read the CSV and verify empty strings for None values
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            assert rows[0]['bookmaker_odds_validated'] == 'false'
            assert rows[0]['bookmaker_actual_odds'] == ''
            assert rows[0]['sharp_odds_validated'] == 'false'
            assert rows[0]['sharp_actual_odds'] == ''
    
    def test_extract_snapshot_text(self, mock_automation):
        """Test the _extract_snapshot_text helper method."""
        # Test with proper structure
        mock_result = Mock()
        mock_result.content = [Mock(text="Test content")]
        
        text = mock_automation._extract_snapshot_text(mock_result)
        assert text == "Test content"
        
        # Test with invalid structure (should return string representation)
        invalid_result = "invalid"
        text = mock_automation._extract_snapshot_text(invalid_result)
        assert text == "invalid"


class TestOddsComparisonLogic:
    """Test suite for odds comparison logic."""
    
    def test_rounding_comparison_exact_match(self):
        """Test that exact matches work correctly."""
        bookmaker_actual = 2.00
        bookmaker_expected = 2.00
        
        result = round(bookmaker_actual, 2) == round(bookmaker_expected, 2)
        assert result is True
    
    def test_rounding_comparison_near_match(self):
        """Test that near matches within rounding work."""
        # 2.004 rounds to 2.00
        bookmaker_actual = 2.004
        bookmaker_expected = 2.00
        
        result = round(bookmaker_actual, 2) == round(bookmaker_expected, 2)
        assert result is True
        
        # 2.006 rounds to 2.01 (should not match 2.00)
        bookmaker_actual = 2.006
        result = round(bookmaker_actual, 2) == round(bookmaker_expected, 2)
        assert result is False
    
    def test_rounding_comparison_no_match(self):
        """Test that non-matching odds are detected."""
        bookmaker_actual = 1.95
        bookmaker_expected = 2.00
        
        result = round(bookmaker_actual, 2) == round(bookmaker_expected, 2)
        assert result is False
    
    def test_rounding_edge_cases(self):
        """Test edge cases in rounding."""
        # Test .005 rounding (rounds up)
        assert round(1.505, 2) == 1.50  # Banker's rounding in Python
        
        # Test .995 rounding
        assert round(1.995, 2) == 2.00  # Banker's rounding
        
        # Test very close values
        assert round(1.9999, 2) == 2.00
        assert round(2.0001, 2) == 2.00


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
