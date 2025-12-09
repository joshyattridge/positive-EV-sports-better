"""
Core betting modules.

This package contains the core functionality for positive EV scanning
and Kelly Criterion bet sizing.
"""

from .positive_ev_scanner import PositiveEVScanner
from .kelly_criterion import KellyCriterion

__all__ = ['PositiveEVScanner', 'KellyCriterion']
