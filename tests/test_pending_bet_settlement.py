"""
Tests for pending bet settlement logic.
Tests the changes where pending bets don't affect bankroll until settled.
"""

import pytest
import os
from datetime import datetime
from src.utils.backtest import HistoricalBacktester


class TestPendingBetBankrollHandling:
    """Test that pending bets don't affect bankroll until settlement"""
    
    @pytest.fixture
    def backtester(self):
        """Create a backtester instance"""
        # Set test environment variables
        os.environ['BANKROLL'] = '1000.0'
        os.environ['MIN_EDGE_PERCENTAGE'] = '2.0'
        os.environ['KELLY_FRACTION'] = '0.5'
        
        backtester = HistoricalBacktester()
        backtester.current_bankroll = 1000.0
        backtester.initial_bankroll = 1000.0
        return backtester
    
    def test_pending_bet_no_bankroll_change(self, backtester):
        """Pending bets should not change bankroll"""
        initial_bankroll = backtester.current_bankroll
        
        bet = {
            'stake': 100,
            'odds': 2.5,
            'game_id': 'test1',
            'commence_time': '2024-01-01T12:00:00Z'
        }
        
        backtester.place_bet(bet, result=None, bet_timestamp='2024-01-01T12:00:00Z')
        
        assert backtester.current_bankroll == initial_bankroll
        assert backtester.bets_placed[0]['bankroll_after'] is None
        assert backtester.bets_placed[0]['actual_profit'] == 0
    
    def test_multiple_pending_bets_no_cumulative_effect(self, backtester):
        """Multiple pending bets should not affect bankroll"""
        initial_bankroll = backtester.current_bankroll
        
        bets = [
            {'stake': 50, 'odds': 2.0, 'game_id': 'test1', 'commence_time': '2024-01-01T12:00:00Z'},
            {'stake': 75, 'odds': 3.0, 'game_id': 'test2', 'commence_time': '2024-01-01T13:00:00Z'},
            {'stake': 100, 'odds': 4.0, 'game_id': 'test3', 'commence_time': '2024-01-01T14:00:00Z'},
        ]
        
        for bet in bets:
            backtester.place_bet(bet, result=None, bet_timestamp=bet['commence_time'])
        
        # Bankroll should be unchanged despite 3 pending bets totaling 225 stake
        assert backtester.current_bankroll == initial_bankroll
        assert len(backtester.bets_placed) == 3
        assert all(b['bankroll_after'] is None for b in backtester.bets_placed)
    
    def test_won_bet_adds_profit_only(self, backtester):
        """Winning bet should add profit (not stake + profit)"""
        initial_bankroll = backtester.current_bankroll
        stake = 100
        odds = 3.0
        expected_profit = stake * (odds - 1)  # 200
        
        bet = {
            'stake': stake,
            'odds': odds,
            'game_id': 'test1',
            'commence_time': '2024-01-01T12:00:00Z'
        }
        
        backtester.place_bet(bet, result='won', bet_timestamp='2024-01-01T12:00:00Z')
        
        assert backtester.current_bankroll == initial_bankroll + expected_profit
        assert backtester.bets_placed[0]['actual_profit'] == expected_profit
        assert backtester.bets_placed[0]['bankroll_after'] == initial_bankroll + expected_profit
    
    def test_lost_bet_subtracts_stake(self, backtester):
        """Losing bet should subtract stake"""
        initial_bankroll = backtester.current_bankroll
        stake = 100
        
        bet = {
            'stake': stake,
            'odds': 2.5,
            'game_id': 'test1',
            'commence_time': '2024-01-01T12:00:00Z'
        }
        
        backtester.place_bet(bet, result='lost', bet_timestamp='2024-01-01T12:00:00Z')
        
        assert backtester.current_bankroll == initial_bankroll - stake
        assert backtester.bets_placed[0]['actual_profit'] == -stake
        assert backtester.bets_placed[0]['bankroll_after'] == initial_bankroll - stake
    
    def test_mixed_bets_correct_bankroll_progression(self, backtester):
        """Test bankroll progression with mix of won, lost, and pending bets"""
        initial_bankroll = 1000.0
        backtester.current_bankroll = initial_bankroll
        
        # Bet 1: Won (stake 100, odds 2.0, profit 100)
        backtester.place_bet(
            {'stake': 100, 'odds': 2.0, 'game_id': 'test1', 'commence_time': '2024-01-01T12:00:00Z'},
            result='won',
            bet_timestamp='2024-01-01T12:00:00Z'
        )
        assert backtester.current_bankroll == 1100.0  # +100 profit
        
        # Bet 2: Pending (stake 50, should not affect bankroll)
        backtester.place_bet(
            {'stake': 50, 'odds': 3.0, 'game_id': 'test2', 'commence_time': '2024-01-01T13:00:00Z'},
            result=None,
            bet_timestamp='2024-01-01T13:00:00Z'
        )
        assert backtester.current_bankroll == 1100.0  # No change
        
        # Bet 3: Lost (stake 75)
        backtester.place_bet(
            {'stake': 75, 'odds': 4.0, 'game_id': 'test3', 'commence_time': '2024-01-01T14:00:00Z'},
            result='lost',
            bet_timestamp='2024-01-01T14:00:00Z'
        )
        assert backtester.current_bankroll == 1025.0  # -75 stake
        
        # Bet 4: Pending (should not affect bankroll)
        backtester.place_bet(
            {'stake': 200, 'odds': 1.5, 'game_id': 'test4', 'commence_time': '2024-01-01T15:00:00Z'},
            result=None,
            bet_timestamp='2024-01-01T15:00:00Z'
        )
        assert backtester.current_bankroll == 1025.0  # No change
        
        # Bet 5: Won (stake 50, odds 5.0, profit 200)
        backtester.place_bet(
            {'stake': 50, 'odds': 5.0, 'game_id': 'test5', 'commence_time': '2024-01-01T16:00:00Z'},
            result='won',
            bet_timestamp='2024-01-01T16:00:00Z'
        )
        assert backtester.current_bankroll == 1225.0  # +200 profit
        
        # Verify bet records
        assert len(backtester.bets_placed) == 5
        assert backtester.bets_placed[0]['bankroll_after'] == 1100.0
        assert backtester.bets_placed[1]['bankroll_after'] is None  # Pending
        assert backtester.bets_placed[2]['bankroll_after'] == 1025.0
        assert backtester.bets_placed[3]['bankroll_after'] is None  # Pending
        assert backtester.bets_placed[4]['bankroll_after'] == 1225.0
    
    def test_bankroll_history_excludes_pending_bets(self, backtester):
        """Bankroll history should only include settled bets"""
        initial_count = len(backtester.bankroll_history)
        
        # Place pending bet
        backtester.place_bet(
            {'stake': 100, 'odds': 2.0, 'game_id': 'test1', 'commence_time': '2024-01-01T12:00:00Z'},
            result=None,
            bet_timestamp='2024-01-01T12:00:00Z'
        )
        
        # No new history entry for pending bet
        assert len(backtester.bankroll_history) == initial_count
        
        # Place winning bet
        backtester.place_bet(
            {'stake': 100, 'odds': 2.0, 'game_id': 'test2', 'commence_time': '2024-01-01T13:00:00Z'},
            result='won',
            bet_timestamp='2024-01-01T13:00:00Z'
        )
        
        # History should have new entry for winning bet
        assert len(backtester.bankroll_history) == initial_count + 1
        
        # Place losing bet
        backtester.place_bet(
            {'stake': 50, 'odds': 3.0, 'game_id': 'test3', 'commence_time': '2024-01-01T14:00:00Z'},
            result='lost',
            bet_timestamp='2024-01-01T14:00:00Z'
        )
        
        # History should have new entry for losing bet
        assert len(backtester.bankroll_history) == initial_count + 2
        
        # Place another pending bet
        backtester.place_bet(
            {'stake': 75, 'odds': 4.0, 'game_id': 'test4', 'commence_time': '2024-01-01T15:00:00Z'},
            result=None,
            bet_timestamp='2024-01-01T15:00:00Z'
        )
        
        # No new history entry for second pending bet
        assert len(backtester.bankroll_history) == initial_count + 2


class TestBankrollNeverNegativeFromPending:
    """Test that pending bets can never cause negative bankroll display"""
    
    @pytest.fixture
    def backtester(self):
        """Create a backtester instance"""
        # Set test environment variables
        os.environ['BANKROLL'] = '1000.0'
        os.environ['MIN_EDGE_PERCENTAGE'] = '2.0'
        os.environ['KELLY_FRACTION'] = '0.5'
        
        backtester = HistoricalBacktester()
        backtester.current_bankroll = 1000.0
        backtester.initial_bankroll = 1000.0
        return backtester
    
    def test_large_pending_stakes_dont_cause_negative_bankroll(self, backtester):
        """Large pending stakes should not cause negative bankroll"""
        initial_bankroll = backtester.current_bankroll
        
        # Place pending bets with very large stakes
        for i in range(5):
            backtester.place_bet(
                {'stake': 500, 'odds': 2.0, 'game_id': f'test{i}', 'commence_time': '2024-01-01T12:00:00Z'},
                result=None,
                bet_timestamp='2024-01-01T12:00:00Z'
            )
        
        # Bankroll should remain unchanged (not go negative)
        assert backtester.current_bankroll == initial_bankroll
        assert backtester.current_bankroll > 0
    
    def test_pending_then_lost_sequence(self, backtester):
        """Test that bankroll tracking works correctly with pending -> lost sequence"""
        initial_bankroll = 1000.0
        backtester.current_bankroll = initial_bankroll
        
        # Place bet as pending first
        bet = {
            'stake': 100,
            'odds': 2.0,
            'game_id': 'test1',
            'commence_time': '2024-01-01T12:00:00Z'
        }
        
        backtester.place_bet(bet.copy(), result=None, bet_timestamp='2024-01-01T12:00:00Z')
        assert backtester.current_bankroll == 1000.0  # Unchanged
        
        # Now the bet loses (would typically happen in settle_pending_bets)
        backtester.place_bet(bet.copy(), result='lost', bet_timestamp='2024-01-01T13:00:00Z')
        assert backtester.current_bankroll == 900.0  # -100 stake
    
    def test_csv_export_no_negative_intermediate_values(self, backtester):
        """Verify that CSV export won't show negative intermediate bankroll values"""
        initial_bankroll = 1000.0
        backtester.current_bankroll = initial_bankroll
        
        # Simulate a backtest sequence
        sequences = [
            ({'stake': 100, 'odds': 2.0}, 'won'),   # +100 -> 1100
            ({'stake': 200, 'odds': 3.0}, None),     # pending -> still 1100
            ({'stake': 150, 'odds': 4.0}, 'lost'),   # -150 -> 950
            ({'stake': 300, 'odds': 1.5}, None),     # pending -> still 950
            ({'stake': 50, 'odds': 10.0}, 'won'),    # +450 -> 1400
        ]
        
        for i, (bet_data, result) in enumerate(sequences):
            bet = {
                **bet_data,
                'game_id': f'test{i}',
                'commence_time': f'2024-01-01T{12+i}:00:00Z'
            }
            backtester.place_bet(bet, result=result, bet_timestamp=bet['commence_time'])
        
        # Check all bankroll_after values are either None (pending) or positive
        for bet in backtester.bets_placed:
            if bet['bankroll_after'] is not None:
                assert bet['bankroll_after'] > 0, f"Negative bankroll detected: {bet['bankroll_after']}"
        
        # Verify final bankroll is correct
        assert backtester.current_bankroll == 1400.0
        
        # Verify only settled bets have bankroll_after values
        settled_count = sum(1 for b in backtester.bets_placed if b['bankroll_after'] is not None)
        assert settled_count == 3  # Only won/lost bets, not pending
