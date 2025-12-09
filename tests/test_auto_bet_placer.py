"""
Unit tests for Auto Bet Placer script
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from scripts.auto_bet_placer import AutoBetPlacer


@pytest.fixture
def auto_bet_placer():
    """Create an AutoBetPlacer instance for testing"""
    with patch.dict('os.environ', {
        'ODDS_API_KEY': 'test_api_key',
        'ANTHROPIC_API_KEY': 'test_anthropic_key',
        'BANKROLL': '1000',
        'BET365_USERNAME': 'testuser',
        'BET365_PASSWORD': 'testpass'
    }):
        with patch('scripts.auto_bet_placer.BrowserAutomation'), \
             patch('scripts.auto_bet_placer.Anthropic'):
            return AutoBetPlacer(headless=True)


class TestAutoBetPlacerInitialization:
    """Test initialization"""
    
    def test_initialization(self, auto_bet_placer):
        """Test initialization creates necessary components"""
        assert auto_bet_placer.scanner is not None
        assert auto_bet_placer.automation is not None
        assert auto_bet_placer.kelly is not None
        assert auto_bet_placer.bet_logger is not None


class TestGetBookmakerCredentials:
    """Test bookmaker credential retrieval"""
    
    def test_get_credentials_success(self, auto_bet_placer):
        """Test successful credential retrieval"""
        with patch.dict('os.environ', {
            'BET365_USERNAME': 'testuser',
            'BET365_PASSWORD': 'testpass'
        }):
            credentials = auto_bet_placer.get_bookmaker_credentials('bet365')
            
            assert credentials['username'] == 'testuser'
            assert credentials['password'] == 'testpass'
    
    def test_get_credentials_missing(self, auto_bet_placer):
        """Test credential retrieval fails when missing"""
        with pytest.raises(ValueError, match='Credentials not found'):
            auto_bet_placer.get_bookmaker_credentials('unknownbookie')
    
    def test_get_credentials_case_insensitive(self, auto_bet_placer):
        """Test credentials work with different cases"""
        with patch.dict('os.environ', {
            'BET365_USERNAME': 'testuser',
            'BET365_PASSWORD': 'testpass'
        }):
            credentials = auto_bet_placer.get_bookmaker_credentials('BET365')
            
            assert credentials['username'] == 'testuser'
            assert credentials['password'] == 'testpass'


class TestFindBestOpportunity:
    """Test finding best opportunity"""
    
    @patch('scripts.auto_bet_placer.PositiveEVScanner')
    def test_find_best_opportunity_success(self, mock_scanner_class, auto_bet_placer):
        """Test finding best opportunity successfully"""
        # Mock scanner to return opportunities
        mock_scanner = Mock()
        mock_scanner.scan_all_sports.return_value = {
            'soccer_epl': [
                {
                    'sport': 'soccer_epl',
                    'game': 'Arsenal @ Chelsea',
                    'market': 'h2h',
                    'outcome': 'Arsenal',
                    'bookmaker': 'Bet365',
                    'bookmaker_key': 'bet365',
                    'odds': 2.5,
                    'ev_percentage': 5.0,
                    'expected_profit': 10.0,
                    'bookmaker_url': 'https://bet365.com',
                    'kelly_stake': {'recommended_stake': 50.0}
                }
            ]
        }
        mock_scanner.sort_opportunities.side_effect = lambda x: x
        mock_scanner.filter_one_bet_per_game.side_effect = lambda x: x
        
        auto_bet_placer.scanner = mock_scanner
        
        best_opp = auto_bet_placer.find_best_opportunity()
        
        assert best_opp is not None
        assert best_opp['game'] == 'Arsenal @ Chelsea'
    
    @patch('scripts.auto_bet_placer.PositiveEVScanner')
    def test_find_best_opportunity_none_found(self, mock_scanner_class, auto_bet_placer):
        """Test when no opportunities found"""
        mock_scanner = Mock()
        mock_scanner.scan_all_sports.return_value = {}
        
        auto_bet_placer.scanner = mock_scanner
        
        best_opp = auto_bet_placer.find_best_opportunity()
        
        assert best_opp is None


class TestDescribeBet:
    """Test bet description generation"""
    
    def test_describe_bet_h2h_home(self, auto_bet_placer):
        """Test h2h bet description for home team"""
        description = auto_bet_placer._describe_bet(
            'h2h',
            'Arsenal',
            'Chelsea',
            'Arsenal'
        )
        
        assert 'Arsenal' in description
        assert 'win' in description.lower()
    
    def test_describe_bet_h2h_away(self, auto_bet_placer):
        """Test h2h bet description for away team"""
        description = auto_bet_placer._describe_bet(
            'h2h',
            'Chelsea',
            'Chelsea',
            'Arsenal'
        )
        
        assert 'Chelsea' in description
        assert 'win' in description.lower()
    
    def test_describe_bet_h2h_draw(self, auto_bet_placer):
        """Test h2h bet description for draw"""
        description = auto_bet_placer._describe_bet(
            'h2h',
            'Draw',
            'Chelsea',
            'Arsenal'
        )
        
        assert 'Draw' in description
    
    def test_describe_bet_spreads(self, auto_bet_placer):
        """Test spreads bet description"""
        description = auto_bet_placer._describe_bet(
            'spreads',
            'Arsenal (+1.5)',
            'Chelsea',
            'Arsenal'
        )
        
        assert 'Arsenal' in description
    
    def test_describe_bet_totals(self, auto_bet_placer):
        """Test totals bet description"""
        description = auto_bet_placer._describe_bet(
            'totals',
            'Over (2.5)',
            'Chelsea',
            'Arsenal'
        )
        
        assert 'Over' in description or 'points' in description.lower()


class TestGenerateBetPrompt:
    """Test bet prompt generation"""
    
    def test_generate_bet_prompt(self, auto_bet_placer):
        """Test prompt generation"""
        opportunity = {
            'bookmaker': 'Bet365',
            'bookmaker_key': 'bet365',
            'bookmaker_url': 'https://bet365.com/test',
            'game': 'Arsenal @ Chelsea',
            'market': 'h2h',
            'outcome': 'Arsenal',
            'odds': 2.5,
            'kelly_stake': {'recommended_stake': 50.0}
        }
        
        credentials = {
            'username': 'testuser',
            'password': 'testpass'
        }
        
        prompt = auto_bet_placer.generate_bet_prompt(opportunity, credentials)
        
        assert 'Bet365' in prompt
        assert 'Arsenal' in prompt
        assert '2.5' in prompt or '2.50' in prompt
        assert '50.0' in prompt or '50.00' in prompt
    
    def test_generate_bet_prompt_includes_credentials(self, auto_bet_placer):
        """Test prompt includes credentials"""
        opportunity = {
            'bookmaker': 'Bet365',
            'bookmaker_key': 'bet365',
            'bookmaker_url': 'https://bet365.com',
            'game': 'Arsenal @ Chelsea',
            'market': 'h2h',
            'outcome': 'Arsenal',
            'odds': 2.0,
            'kelly_stake': {'recommended_stake': 100.0}
        }
        
        credentials = {
            'username': 'myuser',
            'password': 'mypass'
        }
        
        prompt = auto_bet_placer.generate_bet_prompt(opportunity, credentials)
        
        assert 'myuser' in prompt
        assert 'mypass' in prompt


class TestVerifyBetPlacement:
    """Test bet placement verification"""
    
    @pytest.mark.asyncio
    async def test_verify_bet_placement_success(self, auto_bet_placer):
        """Test verification when bet was placed"""
        mock_response = Mock()
        mock_response.content = [Mock(text='YES')]
        
        with patch.object(auto_bet_placer.anthropic_client.messages, 'create', return_value=mock_response):
            result = await auto_bet_placer._verify_bet_placement([], 'Bet placed successfully')
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_bet_placement_failure(self, auto_bet_placer):
        """Test verification when bet was not placed"""
        mock_response = Mock()
        mock_response.content = [Mock(text='NO')]
        
        with patch.object(auto_bet_placer.anthropic_client.messages, 'create', return_value=mock_response):
            result = await auto_bet_placer._verify_bet_placement([], 'Bet not placed')
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_verify_bet_placement_error(self, auto_bet_placer):
        """Test verification handles errors gracefully"""
        with patch.object(auto_bet_placer.anthropic_client.messages, 'create', side_effect=Exception('API Error')):
            result = await auto_bet_placer._verify_bet_placement([], 'Test response')
            
            # Should return False on error (conservative default)
            assert result is False


class TestPlaceBestBet:
    """Test place_best_bet functionality"""
    
    @pytest.mark.asyncio
    async def test_place_best_bet_no_opportunities(self, auto_bet_placer):
        """Test when no opportunities are found"""
        with patch.object(auto_bet_placer, 'find_best_opportunity', return_value=None):
            result = await auto_bet_placer.place_best_bet()
            
            assert result['success'] is False
            assert 'No betting opportunities' in result['message']
    
    @pytest.mark.asyncio
    async def test_place_best_bet_missing_credentials(self, auto_bet_placer):
        """Test when credentials are missing"""
        opportunity = {
            'bookmaker_key': 'unknownbookie',
            'bookmaker': 'Unknown Bookie'
        }
        
        with patch.object(auto_bet_placer, 'find_best_opportunity', return_value=opportunity):
            result = await auto_bet_placer.place_best_bet()
            
            assert result['success'] is False
            assert 'Credentials not found' in result['message']
    
    @pytest.mark.asyncio
    async def test_place_best_bet_dry_run(self, auto_bet_placer):
        """Test dry run mode"""
        opportunity = {
            'bookmaker_key': 'bet365',
            'bookmaker': 'Bet365',
            'bookmaker_url': 'https://bet365.com',
            'game': 'Test Game',
            'market': 'h2h',
            'outcome': 'Team A',
            'odds': 2.0,
            'kelly_stake': {'recommended_stake': 100.0}
        }
        
        with patch.object(auto_bet_placer, 'find_best_opportunity', return_value=opportunity):
            with patch.object(auto_bet_placer, 'get_bookmaker_credentials', return_value={'username': 'test', 'password': 'test'}):
                with patch.object(auto_bet_placer, 'generate_bet_prompt', return_value='Test prompt'):
                    result = await auto_bet_placer.place_best_bet(dry_run=True)
                    
                    assert result['success'] is True
                    assert 'Dry run' in result['message']


class TestEdgeCases:
    """Test edge cases"""
    
    def test_initialization_headless_mode(self):
        """Test initialization in headless mode"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'ANTHROPIC_API_KEY': 'test'
        }):
            with patch('scripts.auto_bet_placer.BrowserAutomation') as mock_browser, \
                 patch('scripts.auto_bet_placer.Anthropic'):
                placer = AutoBetPlacer(headless=True)
                mock_browser.assert_called_once_with(headless=True)
    
    def test_initialization_non_headless_mode(self):
        """Test initialization in non-headless mode"""
        with patch.dict('os.environ', {
            'ODDS_API_KEY': 'test',
            'ANTHROPIC_API_KEY': 'test'
        }):
            with patch('scripts.auto_bet_placer.BrowserAutomation') as mock_browser, \
                 patch('scripts.auto_bet_placer.Anthropic'):
                placer = AutoBetPlacer(headless=False)
                mock_browser.assert_called_once_with(headless=False)
