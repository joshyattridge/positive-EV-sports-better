"""
Odds Utilities Module

Utility functions for odds calculations and conversions.
"""

from fractions import Fraction


def calculate_implied_probability(decimal_odds: float) -> float:
    """
    Calculate implied probability from decimal odds.
    
    Args:
        decimal_odds: Odds in decimal format
        
    Returns:
        Implied probability (0 to 1)
    """
    return 1 / decimal_odds


def decimal_to_fractional(decimal_odds: float) -> str:
    """
    Convert decimal odds to fractional format.
    
    Args:
        decimal_odds: Odds in decimal format (e.g., 3.50)
        
    Returns:
        Fractional odds as string (e.g., "5/2")
    """
    # Subtract 1 to get the profit ratio
    profit_ratio = decimal_odds - 1
    
    # Convert to fraction and simplify
    frac = Fraction(profit_ratio).limit_denominator(100)
    
    return f"{frac.numerator}/{frac.denominator}"


def calculate_ev(bet_odds: float, true_probability: float) -> float:
    """
    Calculate expected value of a bet.
    
    Args:
        bet_odds: The odds being offered (decimal)
        true_probability: Estimated true probability of outcome
        
    Returns:
        Expected value as percentage (0.05 = 5% EV)
    """
    return (true_probability * (bet_odds - 1)) - (1 - true_probability)
