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


def calculate_market_vig(odds_list: list) -> float:
    """
    Calculate the bookmaker's vig (margin) from a list of odds for all outcomes.
    
    Args:
        odds_list: List of decimal odds for all outcomes in a market
                   e.g., [2.10, 3.50, 3.80] for home/draw/away
    
    Returns:
        Vig as a decimal (0.05 = 5% vig)
        Returns 0.0 if calculation fails
    """
    if not odds_list or len(odds_list) < 2:
        return 0.0
    
    try:
        # Sum implied probabilities
        total_probability = sum(1/odds for odds in odds_list if odds > 0)
        
        # Vig is the excess over 100%
        vig = total_probability - 1.0
        
        # Ensure non-negative (can be negative in rare arbitrage situations)
        return max(0.0, vig)
    except (ZeroDivisionError, TypeError):
        return 0.0


def remove_vig_proportional(odds_list: list) -> list:
    """
    Remove vig from odds using proportional method.
    This is the simplest method - assumes vig is distributed proportionally.
    
    Args:
        odds_list: List of decimal odds for all outcomes
    
    Returns:
        List of fair (no-vig) decimal odds
    """
    if not odds_list or len(odds_list) < 2:
        return odds_list
    
    try:
        # Calculate implied probabilities with vig
        implied_probs = [1/odds for odds in odds_list if odds > 0]
        
        if not implied_probs:
            return odds_list
        
        # Total probability (should be > 1.0 due to vig)
        total_prob = sum(implied_probs)
        
        if total_prob <= 1.0:
            # No vig or negative vig (arbitrage) - return as is
            return odds_list
        
        # Remove vig proportionally
        fair_probs = [prob / total_prob for prob in implied_probs]
        
        # Convert back to odds
        fair_odds = [1 / prob if prob > 0 else odds_list[i] 
                     for i, prob in enumerate(fair_probs)]
        
        return fair_odds
    except (ZeroDivisionError, TypeError):
        return odds_list


def remove_vig_power(odds_list: list, power: float = 1.5) -> list:
    """
    Remove vig using power method (more sophisticated).
    Accounts for favorite-longshot bias by weighting probabilities.
    
    Args:
        odds_list: List of decimal odds for all outcomes
        power: Exponential weighting factor (1.5 is typical)
    
    Returns:
        List of fair (no-vig) decimal odds
    """
    if not odds_list or len(odds_list) < 2:
        return odds_list
    
    try:
        # Calculate implied probabilities with vig
        implied_probs = [1/odds for odds in odds_list if odds > 0]
        
        if not implied_probs:
            return odds_list
        
        # Apply power transformation
        powered_probs = [prob ** power for prob in implied_probs]
        
        # Normalize to sum to 1.0
        total_powered = sum(powered_probs)
        
        if total_powered <= 0:
            return odds_list
        
        fair_probs = [prob / total_powered for prob in powered_probs]
        
        # Convert back to odds
        fair_odds = [1 / prob if prob > 0 else odds_list[i] 
                     for i, prob in enumerate(fair_probs)]
        
        return fair_odds
    except (ZeroDivisionError, TypeError):
        return odds_list


def remove_vig_shin(odds_list: list, max_iterations: int = 1000) -> list:
    """
    Remove vig using Shin's method (most sophisticated).
    Accounts for insider trading probability and favorite-longshot bias.
    This is considered the most accurate for theoretical fair value.
    
    Args:
        odds_list: List of decimal odds for all outcomes
        max_iterations: Maximum iterations for convergence
    
    Returns:
        List of fair (no-vig) decimal odds
    """
    if not odds_list or len(odds_list) < 2:
        return odds_list
    
    try:
        # Calculate implied probabilities with vig
        implied_probs = [1/odds for odds in odds_list if odds > 0]
        
        if not implied_probs:
            return odds_list
        
        n = len(implied_probs)
        
        # Initial guess for insider trading probability (z)
        z = 0.0
        
        # Iteratively solve for z using Shin's equation
        for _ in range(max_iterations):
            # Calculate fair probabilities given current z
            sum_sqrt = sum((prob * (1 - z)) ** 0.5 for prob in implied_probs)
            
            if sum_sqrt == 0:
                break
            
            # Update z
            z_new = (sum(implied_probs) - sum_sqrt ** 2) / (n - sum_sqrt ** 2)
            
            # Ensure z is in valid range [0, 1)
            z_new = max(0.0, min(z_new, 0.99))
            
            # Check convergence
            if abs(z_new - z) < 1e-6:
                z = z_new
                break
            
            z = z_new
        
        # Calculate fair probabilities
        fair_probs = []
        sum_sqrt = sum((prob * (1 - z)) ** 0.5 for prob in implied_probs)
        
        for prob in implied_probs:
            if sum_sqrt > 0:
                fair_prob = ((prob * (1 - z)) ** 0.5) / sum_sqrt
                fair_probs.append(fair_prob)
            else:
                fair_probs.append(prob)
        
        # Normalize (should already sum to 1.0, but ensure it)
        total = sum(fair_probs)
        if total > 0 and abs(total - 1.0) > 1e-6:
            fair_probs = [p / total for p in fair_probs]
        
        # Convert back to odds
        fair_odds = [1 / prob if prob > 0 else odds_list[i] 
                     for i, prob in enumerate(fair_probs)]
        
        return fair_odds
    except (ZeroDivisionError, TypeError, ValueError):
        # Fall back to proportional method if Shin fails
        return remove_vig_proportional(odds_list)


def calculate_ev_with_vig_removal(bet_odds: float, bet_market_odds: list, 
                                   sharp_odds: float, sharp_market_odds: list,
                                   method: str = 'proportional') -> float:
    """
    Calculate EV with vig removal from both betting bookmaker and sharp books.
    
    Args:
        bet_odds: The odds being offered by betting bookmaker (decimal)
        bet_market_odds: All odds in the market from betting bookmaker (for vig calculation)
        sharp_odds: Average odds from sharp bookmakers (decimal)
        sharp_market_odds: All odds in the market from sharp bookmakers (for vig calculation)
        method: Vig removal method ('proportional', 'power', 'shin')
    
    Returns:
        Expected value as percentage (0.05 = 5% EV)
    """
    # Remove vig from sharp odds to get true probability
    if method == 'shin':
        sharp_fair_odds_list = remove_vig_shin(sharp_market_odds)
    elif method == 'power':
        sharp_fair_odds_list = remove_vig_power(sharp_market_odds)
    else:  # proportional (default)
        sharp_fair_odds_list = remove_vig_proportional(sharp_market_odds)
    
    # Find the fair odds for our outcome (assume it's at same index)
    # In practice, this is handled by the scanner matching outcomes
    sharp_fair_odds = sharp_odds  # Will be replaced by scanner with matched outcome
    if sharp_market_odds and len(sharp_fair_odds_list) == len(sharp_market_odds):
        # Find index of sharp_odds in sharp_market_odds
        try:
            idx = sharp_market_odds.index(sharp_odds)
            sharp_fair_odds = sharp_fair_odds_list[idx]
        except (ValueError, IndexError):
            sharp_fair_odds = sharp_odds
    
    # Calculate true probability from vig-free sharp odds
    true_probability = 1 / sharp_fair_odds if sharp_fair_odds > 0 else 0
    
    # Calculate EV using betting bookmaker's odds (with vig) vs true probability
    return calculate_ev(bet_odds, true_probability)
