"""
Kelly Criterion Bankroll Management

Implements the Kelly Criterion formula to calculate optimal bet sizing
based on expected value and bankroll.
"""

import os
from typing import Optional


class KellyCriterion:
    """
    Kelly Criterion calculator for optimal bet sizing.
    
    The Kelly Criterion formula:
    f* = (bp - q) / b
    
    Where:
    - f* = fraction of bankroll to bet
    - b = decimal odds - 1 (net odds received)
    - p = probability of winning
    - q = probability of losing (1 - p)
    """
    
    def __init__(self, bankroll: Optional[float] = None):
        """
        Initialize Kelly Criterion calculator.
        
        Args:
            bankroll: Total bankroll amount (reads from env if not provided)
        """
        self.bankroll = bankroll or float(os.getenv('BANKROLL', '1000'))
        self.bet_rounding = float(os.getenv('BET_ROUNDING', '0'))
    
    def round_to_nearest(self, value: float, nearest: float) -> float:
        """
        Round a value to the nearest multiple of a given number.
        
        Args:
            value: The value to round
            nearest: The multiple to round to (e.g., 5 for nearest £5)
            
        Returns:
            Rounded value
        """
        if nearest == 0:
            return value
        return round(value / nearest) * nearest
    
    def calculate_kelly_stake(
        self, 
        decimal_odds: float, 
        true_probability: float,
        kelly_fraction: float = 1.0
    ) -> dict:
        """
        Calculate the optimal stake using Kelly Criterion.
        
        Args:
            decimal_odds: The odds being offered (decimal format)
            true_probability: Estimated true probability of outcome (0 to 1)
            kelly_fraction: Fraction of Kelly to use (1.0 = full Kelly, 0.5 = half Kelly)
            
        Returns:
            Dictionary containing:
                - kelly_percentage: Percentage of bankroll to bet
                - recommended_stake: Actual stake amount
                - bankroll: Total bankroll
        """
        # Kelly formula: f* = (bp - q) / b
        # Where b = decimal_odds - 1
        b = decimal_odds - 1
        p = true_probability
        q = 1 - p
        
        # Calculate Kelly percentage
        kelly_percentage = ((b * p) - q) / b
        
        # Apply Kelly fraction (e.g., 0.5 for half Kelly)
        kelly_percentage *= kelly_fraction
        
        # Calculate stake based on bankroll
        recommended_stake = kelly_percentage * self.bankroll
        
        # Ensure stake is not negative (shouldn't bet if EV is negative)
        recommended_stake = max(0, recommended_stake)
        
        # Apply bet rounding
        recommended_stake = self.round_to_nearest(recommended_stake, self.bet_rounding)
        
        return {
            'kelly_percentage': kelly_percentage * 100,  # Convert to percentage
            'recommended_stake': round(recommended_stake, 2),
            'bankroll': self.bankroll
        }
    
    def calculate_expected_profit(
        self,
        stake: float,
        decimal_odds: float,
        true_probability: float
    ) -> float:
        """
        Calculate expected profit for a given stake.
        
        Args:
            stake: Amount to bet
            decimal_odds: The odds being offered (decimal format)
            true_probability: Estimated true probability of outcome (0 to 1)
            
        Returns:
            Expected profit amount
        """
        # Expected profit = (probability of win * profit if win) - (probability of loss * loss)
        profit_if_win = stake * (decimal_odds - 1)
        loss_if_lose = stake
        
        expected_profit = (true_probability * profit_if_win) - ((1 - true_probability) * loss_if_lose)
        
        return round(expected_profit, 2)
    
    def format_stake_recommendation(self, stake_info: dict) -> str:
        """
        Format stake recommendation as a readable string.
        
        Args:
            stake_info: Dictionary returned by calculate_kelly_stake
            
        Returns:
            Formatted string with stake recommendation
        """
        lines = []
        lines.append(f"💰 Kelly Stake: {stake_info['kelly_percentage']:.2f}% of bankroll")
        lines.append(f"💵 Recommended Bet: £{stake_info['recommended_stake']:.2f}")
        
        if stake_info['is_capped']:
            lines.append(f"⚠️  Capped at max bet size (Raw Kelly: £{stake_info['raw_kelly_stake']:.2f})")
        
        return "\n   ".join(lines)


def calculate_bet_size(
    decimal_odds: float,
    true_probability: float,
    bankroll: Optional[float] = None,
    kelly_fraction: float = 1.0
) -> dict:
    """
    Convenience function to calculate bet size using Kelly Criterion.
    
    Args:
        decimal_odds: The odds being offered (decimal format)
        true_probability: Estimated true probability of outcome (0 to 1)
        bankroll: Total bankroll (reads from env if not provided)
        kelly_fraction: Fraction of Kelly to use (1.0 = full Kelly)
        
    Returns:
        Dictionary with stake recommendation
    """
    kelly = KellyCriterion(bankroll=bankroll)
    return kelly.calculate_kelly_stake(decimal_odds, true_probability, kelly_fraction)
