"""
Unit tests for Kelly Criterion module
"""

import pytest
import os
from src.core.kelly_criterion import KellyCriterion, calculate_bet_size


class TestKellyCriterion:
    """Test cases for KellyCriterion class"""
    
    def test_initialization_with_bankroll(self):
        """Test initialization with explicit bankroll"""
        kelly = KellyCriterion(bankroll=1000)
        assert kelly.bankroll == 1000
    
    def test_initialization_from_env(self, monkeypatch):
        """Test initialization reading from environment variable"""
        monkeypatch.setenv('BANKROLL', '2500')
        kelly = KellyCriterion()
        assert kelly.bankroll == 2500
    
    def test_initialization_default(self, monkeypatch):
        """Test initialization with default value"""
        monkeypatch.delenv('BANKROLL', raising=False)
        kelly = KellyCriterion()
        assert kelly.bankroll == 1000  # default value
    
    def test_calculate_kelly_stake_positive_ev(self):
        """Test Kelly calculation with positive EV"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=2.5,
            true_probability=0.5,
            kelly_fraction=1.0
        )
        
        assert 'kelly_percentage' in result
        assert 'recommended_stake' in result
        assert 'bankroll' in result
        assert result['bankroll'] == 1000
        assert result['recommended_stake'] > 0
        assert result['kelly_percentage'] > 0
    
    def test_calculate_kelly_stake_negative_ev(self):
        """Test Kelly calculation with negative EV (should recommend 0)"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=1.5,
            true_probability=0.4,  # Low probability for the odds
            kelly_fraction=1.0
        )
        
        assert result['recommended_stake'] == 0
    
    def test_calculate_kelly_stake_half_kelly(self):
        """Test Kelly calculation with half Kelly fraction"""
        kelly = KellyCriterion(bankroll=1000)
        
        # Full Kelly
        full_kelly = kelly.calculate_kelly_stake(
            decimal_odds=2.5,
            true_probability=0.5,
            kelly_fraction=1.0
        )
        
        # Half Kelly
        half_kelly = kelly.calculate_kelly_stake(
            decimal_odds=2.5,
            true_probability=0.5,
            kelly_fraction=0.5
        )
        
        # Half Kelly should recommend half the stake
        assert half_kelly['recommended_stake'] == pytest.approx(
            full_kelly['recommended_stake'] / 2, rel=0.01
        )
    
    def test_calculate_kelly_stake_quarter_kelly(self):
        """Test Kelly calculation with quarter Kelly fraction"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=3.0,
            true_probability=0.6,
            kelly_fraction=0.25
        )
        
        assert result['recommended_stake'] > 0
        assert result['kelly_percentage'] > 0
    
    def test_calculate_expected_profit_positive(self):
        """Test expected profit calculation with positive EV"""
        kelly = KellyCriterion(bankroll=1000)
        expected_profit = kelly.calculate_expected_profit(
            stake=100,
            decimal_odds=2.5,
            true_probability=0.5
        )
        
        # (0.5 * 100 * 1.5) - (0.5 * 100) = 75 - 50 = 25
        assert expected_profit == pytest.approx(25.0, rel=0.01)
    
    def test_calculate_expected_profit_negative(self):
        """Test expected profit calculation with negative EV"""
        kelly = KellyCriterion(bankroll=1000)
        expected_profit = kelly.calculate_expected_profit(
            stake=100,
            decimal_odds=1.5,
            true_probability=0.4
        )
        
        # Should be negative
        assert expected_profit < 0
    
    def test_calculate_expected_profit_zero_stake(self):
        """Test expected profit with zero stake"""
        kelly = KellyCriterion(bankroll=1000)
        expected_profit = kelly.calculate_expected_profit(
            stake=0,
            decimal_odds=2.0,
            true_probability=0.5
        )
        
        assert expected_profit == 0.0
    
    def test_kelly_formula_accuracy(self):
        """Test Kelly formula calculation accuracy"""
        kelly = KellyCriterion(bankroll=1000)
        
        # Known values for manual verification
        # Odds: 2.0 (even money), True prob: 0.6
        # b = 1.0, p = 0.6, q = 0.4
        # Kelly = (1.0 * 0.6 - 0.4) / 1.0 = 0.2 = 20%
        result = kelly.calculate_kelly_stake(
            decimal_odds=2.0,
            true_probability=0.6,
            kelly_fraction=1.0
        )
        
        assert result['kelly_percentage'] == pytest.approx(20.0, rel=0.01)
        assert result['recommended_stake'] == pytest.approx(200.0, rel=0.01)
    
    def test_kelly_with_high_probability(self):
        """Test Kelly with very high true probability"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=1.5,
            true_probability=0.9,
            kelly_fraction=1.0
        )
        
        assert result['recommended_stake'] > 0
    
    def test_kelly_with_low_odds(self):
        """Test Kelly with low odds"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=1.1,
            true_probability=0.95,
            kelly_fraction=1.0
        )
        
        # Should still recommend something given high probability
        assert result['recommended_stake'] >= 0
    
    def test_kelly_rounding(self):
        """Test that stake is properly rounded to 2 decimal places"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=2.37,
            true_probability=0.543,
            kelly_fraction=1.0
        )
        
        # Should be rounded to 2 decimal places
        stake_str = f"{result['recommended_stake']:.2f}"
        assert result['recommended_stake'] == float(stake_str)


class TestCalculateBetSizeConvenienceFunction:
    """Test the convenience function"""
    
    def test_calculate_bet_size(self):
        """Test convenience function"""
        result = calculate_bet_size(
            decimal_odds=2.5,
            true_probability=0.5,
            bankroll=1000,
            kelly_fraction=0.5
        )
        
        assert 'kelly_percentage' in result
        assert 'recommended_stake' in result
        assert 'bankroll' in result
        assert result['bankroll'] == 1000
    
    def test_calculate_bet_size_reads_env(self, monkeypatch):
        """Test convenience function reads from environment"""
        monkeypatch.setenv('BANKROLL', '5000')
        result = calculate_bet_size(
            decimal_odds=2.0,
            true_probability=0.6,
            kelly_fraction=1.0
        )
        
        assert result['bankroll'] == 5000


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_probability_at_boundary_zero(self):
        """Test with probability at 0"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=2.0,
            true_probability=0.0,
            kelly_fraction=1.0
        )
        
        assert result['recommended_stake'] == 0
    
    def test_probability_at_boundary_one(self):
        """Test with probability at 1"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=1.1,
            true_probability=1.0,
            kelly_fraction=1.0
        )
        
        # Should recommend large stake but not infinite
        assert result['recommended_stake'] >= 0
        assert result['recommended_stake'] <= 1000
    
    def test_very_small_bankroll(self):
        """Test with very small bankroll"""
        kelly = KellyCriterion(bankroll=10)
        result = kelly.calculate_kelly_stake(
            decimal_odds=2.0,
            true_probability=0.6,
            kelly_fraction=1.0
        )
        
        assert result['bankroll'] == 10
        assert result['recommended_stake'] >= 0
        assert result['recommended_stake'] <= 10
    
    def test_very_large_bankroll(self):
        """Test with very large bankroll"""
        kelly = KellyCriterion(bankroll=1000000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=2.0,
            true_probability=0.6,
            kelly_fraction=1.0
        )
        
        assert result['bankroll'] == 1000000
        assert result['recommended_stake'] > 0
    
    def test_odds_at_boundary(self):
        """Test with odds at boundary (1.01)"""
        kelly = KellyCriterion(bankroll=1000)
        result = kelly.calculate_kelly_stake(
            decimal_odds=1.01,
            true_probability=0.99,
            kelly_fraction=1.0
        )
        
        assert result['recommended_stake'] >= 0
