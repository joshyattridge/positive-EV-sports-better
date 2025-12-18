#!/usr/bin/env python3
"""
Parameter Optimization Script

Performs grid search over betting parameters to find optimal settings
that maximize returns while minimizing drawdown and variance.
"""

import subprocess
import json
import os
import csv
import itertools
from pathlib import Path
from typing import Dict, List, Tuple
import time
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import shutil
import tempfile
from tqdm import tqdm

class ParameterOptimizer:
    """Optimizes betting parameters using grid search."""
    
    def __init__(self, backtest_start: str, backtest_end: str, monte_carlo_runs: int):
        self.backtest_start = backtest_start
        self.backtest_end = backtest_end
        self.monte_carlo_runs = monte_carlo_runs
        self.results = []
        self.env_backup = self._backup_env()
        
    def _backup_env(self) -> Dict[str, str]:
        """Backup current .env settings."""
        backup = {}
        env_path = Path('.env')
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        backup[key] = value
        return backup
    
    def _update_env(self, params: Dict[str, float]):
        """Update .env file with new parameters."""
        env_path = Path('.env')
        
        # Read entire file
        with open(env_path) as f:
            lines = f.readlines()
        
        # Update parameters
        updated_lines = []
        for line in lines:
            updated = False
            for param, value in params.items():
                if line.startswith(f"{param}="):
                    updated_lines.append(f"{param}={value}\n")
                    updated = True
                    break
            if not updated:
                updated_lines.append(line)
        
        # Write back
        with open(env_path, 'w') as f:
            f.writelines(updated_lines)
    
    def _restore_env(self):
        """Restore original .env settings."""
        env_path = Path('.env')
        with open(env_path) as f:
            lines = f.readlines()
        
        updated_lines = []
        for line in lines:
            updated = False
            for key, value in self.env_backup.items():
                if line.startswith(f"{key}="):
                    updated_lines.append(f"{key}={value}\n")
                    updated = True
                    break
            if not updated:
                updated_lines.append(line)
        
        with open(env_path, 'w') as f:
            f.writelines(updated_lines)
    
    def _run_backtest(self) -> Dict:
        """Run backtest and return results."""
        cmd = [
            "./run.sh", "backtest",
            "--start", self.backtest_start,
            "--end", self.backtest_end,
            "--monte-carlo", str(self.monte_carlo_runs)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                input="y\n",  # Auto-confirm the backtest prompt
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout (actual time ~102 seconds)
            )
            
            if result.returncode != 0:
                return None
            
            # Parse results from backtest
            return self._parse_backtest_results()
        
        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            return None
    
    def _parse_backtest_results(self) -> Dict:
        """Parse backtest results from bet history CSV."""
        csv_path = Path('data/backtest_bet_history.csv')
        
        if not csv_path.exists():
            return None
        
        total_bets = 0
        wins = 0
        total_profit = 0
        bankroll_history = []
        starting_bankroll = 5000.0
        min_bankroll = starting_bankroll
        max_bankroll = starting_bankroll
        
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_bets += 1
                if row['bet_result'] == 'won':
                    wins += 1
                total_profit += float(row['actual_profit_loss'])
                bankroll = float(row['bankroll_after'])
                bankroll_history.append(bankroll)
                min_bankroll = min(min_bankroll, bankroll)
                max_bankroll = max(max_bankroll, bankroll)
        
        if total_bets == 0:
            return None
        
        # Calculate metrics
        win_rate = wins / total_bets
        final_bankroll = bankroll_history[-1] if bankroll_history else starting_bankroll
        total_return = (final_bankroll - starting_bankroll) / starting_bankroll
        max_drawdown = (starting_bankroll - min_bankroll) / starting_bankroll
        
        # Calculate volatility (standard deviation of bankroll changes)
        if len(bankroll_history) > 1:
            changes = [bankroll_history[i] - bankroll_history[i-1] 
                      for i in range(1, len(bankroll_history))]
            avg_change = sum(changes) / len(changes)
            variance = sum((c - avg_change) ** 2 for c in changes) / len(changes)
            volatility = variance ** 0.5
        else:
            volatility = 0
        
        # Calculate Sharpe ratio (return per unit risk)
        sharpe_ratio = total_return / volatility if volatility > 0 else 0
        
        # Calculate smoothness score (higher is better)
        # Penalize drawdown and volatility, reward return
        smoothness_score = (
            total_return * 100  # Reward returns
            - max_drawdown * 200  # Heavily penalize drawdown
            - (volatility / starting_bankroll) * 50  # Penalize volatility
        )
        
        return {
            'total_bets': total_bets,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'total_return_pct': total_return * 100,
            'max_drawdown_pct': max_drawdown * 100,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'smoothness_score': smoothness_score,
            'final_bankroll': final_bankroll
        }
    
    def optimize(self, parameter_grid: Dict[str, List[float]], max_workers: int = None):
        """
        Run grid search optimization sequentially with progress bar.
        
        Args:
            parameter_grid: Dictionary mapping parameter names to lists of values to test
            max_workers: Unused (kept for API compatibility)
        """
        # Generate all parameter combinations
        param_names = list(parameter_grid.keys())
        param_values = list(parameter_grid.values())
        combinations = list(itertools.product(*param_values))
        
        total_combinations = len(combinations)
        
        print(f"🔍 Starting grid search with {total_combinations} parameter combinations...")
        print(f"📊 Backtest period: {self.backtest_start} to {self.backtest_end}")
        print(f"🎲 Monte Carlo runs: {self.monte_carlo_runs}")
        print()
        
        start_time = time.time()
        successful = 0
        failed = 0
        best_smoothness = float('-inf')
        best_return = float('-inf')
        
        # Run backtests sequentially with progress bar
        with tqdm(total=total_combinations, desc="🔍 Optimizing", unit="test", 
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
            
            for values in combinations:
                params = dict(zip(param_names, values))
                
                # Update .env with new parameters
                self._update_env(params)
                
                # Run backtest
                results = self._run_backtest()
                
                if results:
                    results['parameters'] = params
                    self.results.append(results)
                    successful += 1
                    
                    # Track best results
                    if results['smoothness_score'] > best_smoothness:
                        best_smoothness = results['smoothness_score']
                    if results['total_return_pct'] > best_return:
                        best_return = results['total_return_pct']
                    
                    # Update progress bar with stats
                    pbar.set_postfix({
                        'Success': successful,
                        'Failed': failed,
                        'Best Smooth': f"{best_smoothness:.1f}",
                        'Best Return': f"{best_return:.1f}%"
                    })
                else:
                    failed += 1
                    pbar.set_postfix({
                        'Success': successful,
                        'Failed': failed,
                        'Best Smooth': f"{best_smoothness:.1f}",
                        'Best Return': f"{best_return:.1f}%"
                    })
                
                pbar.update(1)
        
        elapsed_time = time.time() - start_time
        print(f"\n✅ Grid search complete in {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
        
        # Restore original .env
        self._restore_env()
        
        # Save and display results
        self._save_results()
        self._display_best_results()
    
    def _run_single_backtest(self, params: Dict[str, float]) -> Dict:
        """
        Run a single backtest with given parameters (for parallel execution).
        
        Args:
            params: Parameter dictionary
            
        Returns:
            Results dictionary or None
        """
        try:
            # Update main .env with parameters (simpler approach - use lock for thread safety)
            import threading
            lock = threading.Lock()
            
            with lock:
                self._update_env(params)
            
            # Run backtest
            cmd = [
                "./run.sh", "backtest",
                "--start", self.backtest_start,
                "--end", self.backtest_end,
                "--monte-carlo", str(self.monte_carlo_runs)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=os.getcwd()
            )
            
            if result.returncode != 0:
                return None
            
            # Parse results immediately
            with lock:
                return self._parse_backtest_results()
        
        except Exception as e:
            return None
    
    def _save_results(self):
        """Save optimization results to JSON file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'optimization_results_{timestamp}.json'
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"💾 Results saved to {output_file}")
    
    def _display_best_results(self):
        """Display top parameter combinations."""
        if not self.results:
            print("No results to display")
            return
        
        # Sort by smoothness score (descending)
        sorted_results = sorted(
            self.results,
            key=lambda x: x['smoothness_score'],
            reverse=True
        )
        
        print("\n" + "="*80)
        print("🏆 TOP 5 PARAMETER COMBINATIONS (by Smoothness Score)")
        print("="*80 + "\n")
        
        for i, result in enumerate(sorted_results[:5], 1):
            print(f"#{i} - Smoothness Score: {result['smoothness_score']:.2f}")
            print("Parameters:")
            for param, value in result['parameters'].items():
                print(f"  {param}: {value}")
            print(f"Performance:")
            print(f"  Total Return: {result['total_return_pct']:.2f}%")
            print(f"  Max Drawdown: {result['max_drawdown_pct']:.2f}%")
            print(f"  Sharpe Ratio: {result['sharpe_ratio']:.4f}")
            print(f"  Win Rate: {result['win_rate']*100:.2f}%")
            print(f"  Total Bets: {result['total_bets']}")
            print(f"  Final Bankroll: £{result['final_bankroll']:.2f}")
            print()
        
        # Also show best by return
        print("="*80)
        print("💰 TOP 3 BY TOTAL RETURN")
        print("="*80 + "\n")
        
        by_return = sorted(self.results, key=lambda x: x['total_return_pct'], reverse=True)
        for i, result in enumerate(by_return[:3], 1):
            print(f"#{i} - Return: {result['total_return_pct']:.2f}% | Drawdown: {result['max_drawdown_pct']:.2f}%")
            for param, value in result['parameters'].items():
                print(f"  {param}: {value}")
            print()
        
        # Show best by drawdown (lowest)
        print("="*80)
        print("🛡️  TOP 3 BY LOWEST DRAWDOWN")
        print("="*80 + "\n")
        
        by_drawdown = sorted(self.results, key=lambda x: x['max_drawdown_pct'])
        for i, result in enumerate(by_drawdown[:3], 1):
            print(f"#{i} - Drawdown: {result['max_drawdown_pct']:.2f}% | Return: {result['total_return_pct']:.2f}%")
            for param, value in result['parameters'].items():
                print(f"  {param}: {value}")
            print()


def main():
    """Main optimization routine."""
    
    # Define parameter grid - focused on key parameters
    parameter_grid = {
        'MIN_EV_THRESHOLD': [0.02, 0.03, 0.04],
        'MIN_TRUE_PROBABILITY': [0.0, 0.35],
        'MAX_ODDS': [0.0, 10.0],
        'KELLY_FRACTION': [0.20, 0.25],
        'MIN_KELLY_PERCENTAGE': [0.0, 0.01]
    }
    
    # Calculate total combinations
    total = 1
    for values in parameter_grid.values():
        total *= len(values)
    
    # Each test takes ~102 seconds with 10,000 Monte Carlo runs
    estimated_time = total * 102 / 60
    
    print(f"⚠️  WARNING: This will run {total} backtests with 10,000 Monte Carlo simulations each!")
    print(f"⏱️  Estimated time: {estimated_time:.0f} minutes (~{estimated_time/60:.1f} hours)")
    print()
    response = input("Continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Optimization cancelled")
        return
    
    # Run optimization with full Monte Carlo (~102 seconds per test = ~40 minutes total)
    optimizer = ParameterOptimizer(
        backtest_start='2025-01-01',
        backtest_end='2025-02-01',
        monte_carlo_runs=10000  # Full Monte Carlo for accurate statistics
    )
    
    print("💡 Running full Monte Carlo (10,000 runs) for accurate variance analysis")
    print()
    
    optimizer.optimize(parameter_grid)


if __name__ == '__main__':
    main()
