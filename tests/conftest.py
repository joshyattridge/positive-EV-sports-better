"""
Test configuration and fixtures

This module contains shared pytest fixtures and configuration
for all tests in the test suite.
"""

import pytest
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def reset_environment():
    """
    Reset environment variables before each test to ensure isolation.
    This fixture runs automatically for all tests.
    """
    original_env = os.environ.copy()
    yield
    # Restore original environment after test
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_env_vars():
    """
    Provide standard environment variables for testing.
    """
    return {
        'ODDS_API_KEY': 'test_api_key',
        'ANTHROPIC_API_KEY': 'test_anthropic_key',
        'BANKROLL': '1000',
        'KELLY_FRACTION': '0.25',
        'MIN_EV_THRESHOLD': '0.02',
        'MIN_TRUE_PROBABILITY': '0.40',
        'SHARP_BOOKS': 'pinnacle,betfair',
        'BETTING_BOOKMAKERS': 'bet365,williamhill',
        'ORDER_BY': 'expected_profit',
        'SORT_ORDER': 'desc',
        'ONE_BET_PER_GAME': 'false',
        'SKIP_ALREADY_BET_GAMES': 'true'
    }


@pytest.fixture
def sample_odds_data():
    """
    Sample odds data for testing.
    """
    return {
        'data': [
            {
                'id': 'game_123',
                'sport_key': 'soccer_epl',
                'home_team': 'Arsenal',
                'away_team': 'Chelsea',
                'commence_time': '2024-01-15T15:00:00Z',
                'bookmakers': [
                    {
                        'key': 'pinnacle',
                        'title': 'Pinnacle',
                        'markets': [
                            {
                                'key': 'h2h',
                                'outcomes': [
                                    {'name': 'Arsenal', 'price': 2.3},
                                    {'name': 'Chelsea', 'price': 3.0},
                                    {'name': 'Draw', 'price': 3.5}
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
                                    {'name': 'Arsenal', 'price': 2.5},
                                    {'name': 'Chelsea', 'price': 3.2},
                                    {'name': 'Draw', 'price': 3.4}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_betting_opportunity():
    """
    Sample betting opportunity for testing.
    """
    return {
        'game_id': 'test_game_123',
        'sport': 'soccer_epl',
        'game': 'Arsenal @ Chelsea',
        'commence_time': '2024-01-15 15:00 GMT',
        'market': 'h2h',
        'outcome': 'Arsenal',
        'bookmaker': 'Bet365',
        'bookmaker_key': 'bet365',
        'odds': 2.5,
        'sharp_avg_odds': 2.3,
        'ev_percentage': 3.5,
        'true_probability': 0.45,
        'bookmaker_probability': 0.40,
        'bookmaker_url': 'https://bet365.com/test',
        'kelly_stake': {
            'bankroll': 1000,
            'kelly_percentage': 5.0,
            'kelly_fraction': 0.25,
            'recommended_stake': 50.0
        },
        'expected_profit': 5.25
    }


def pytest_configure(config):
    """
    Configure pytest with custom settings.
    """
    # Register custom markers
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
