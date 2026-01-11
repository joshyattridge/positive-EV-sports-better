#!/usr/bin/env python3
"""
Comprehensive Backtest Analysis Script

This script analyzes betting backtest results and provides detailed breakdowns by:
- EV percentage ranges
- Sports/leagues
- Bookmakers
- Markets
- Odds ranges
- Time-based patterns
- Stake sizes
- And more...

Usage:
    python analyze_backtest.py <path_to_csv_file>
    python analyze_backtest.py data/backtest_bet_history.csv
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
from matplotlib.backends.backend_pdf import PdfPages

warnings.filterwarnings('ignore')

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10


class BacktestAnalyzer:
    """Analyzes betting backtest data and generates comprehensive reports."""
    
    def __init__(self, csv_path):
        """Initialize analyzer with CSV file path."""
        self.csv_path = Path(csv_path)
        self.df = None
        self.settled_df = None
        self.load_data()
        
    def load_data(self):
        """Load and preprocess the backtest data."""
        print(f"\n{'='*80}")
        print(f"Loading data from: {self.csv_path}")
        print(f"{'='*80}\n")
        
        self.df = pd.read_csv(self.csv_path)
        
        # Convert date columns
        if 'date_placed' in self.df.columns:
            self.df['date_placed'] = pd.to_datetime(self.df['date_placed'], format='ISO8601')
        if 'commence_time' in self.df.columns:
            self.df['commence_time'] = pd.to_datetime(self.df['commence_time'], format='mixed', utc=True)
            
        # Filter to settled bets only for most analyses
        self.settled_df = self.df[self.df['bet_result'].isin(['win', 'loss'])].copy()
        
        print(f"Total bets: {len(self.df)}")
        print(f"Settled bets: {len(self.settled_df)}")
        print(f"Pending bets: {len(self.df[self.df['bet_result'] == 'pending'])}")
        print(f"Date range: {self.df['date_placed'].min()} to {self.df['date_placed'].max()}\n")
        
    def overall_summary(self):
        """Generate overall performance summary."""
        print(f"\n{'='*80}")
        print("OVERALL PERFORMANCE SUMMARY")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        total_bets = len(df)
        total_staked = df['recommended_stake'].sum()
        total_profit = df['actual_profit_loss'].sum()
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        
        wins = len(df[df['bet_result'] == 'win'])
        losses = len(df[df['bet_result'] == 'loss'])
        win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
        
        avg_stake = df['recommended_stake'].mean()
        avg_odds = df['bet_odds'].mean()
        avg_ev = df['ev_percentage'].mean()
        
        print(f"Total Settled Bets: {total_bets}")
        print(f"Total Staked: ${total_staked:.2f}")
        print(f"Total Profit/Loss: ${total_profit:.2f}")
        print(f"ROI: {roi:.2f}%")
        print(f"\nWins: {wins}")
        print(f"Losses: {losses}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"\nAverage Stake: ${avg_stake:.2f}")
        print(f"Average Odds: {avg_odds:.2f}")
        print(f"Average EV: {avg_ev:.2f}%")
        
        # Calculate expected vs actual
        expected_profit = df['expected_profit'].sum()
        print(f"\nExpected Profit: ${expected_profit:.2f}")
        print(f"Actual Profit: ${total_profit:.2f}")
        print(f"Difference: ${total_profit - expected_profit:.2f}")
        print(f"Actual vs Expected: {(total_profit / expected_profit * 100) if expected_profit != 0 else 0:.2f}%")
        
        return {
            'total_bets': total_bets,
            'total_staked': total_staked,
            'total_profit': total_profit,
            'roi': roi,
            'win_rate': win_rate
        }
    
    def analyze_by_ev_range(self):
        """Analyze performance by EV percentage ranges."""
        print(f"\n{'='*80}")
        print("ANALYSIS BY EV PERCENTAGE RANGE")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        # Define EV ranges
        bins = [0, 5, 10, 15, 20, 25, 30, 100]
        labels = ['0-5%', '5-10%', '10-15%', '15-20%', '20-25%', '25-30%', '30%+']
        
        df['ev_range'] = pd.cut(df['ev_percentage'], bins=bins, labels=labels, include_lowest=True)
        
        # Group by EV range
        ev_analysis = df.groupby('ev_range', observed=True).agg({
            'recommended_stake': ['count', 'sum'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum(),
            'ev_percentage': 'mean',
            'bet_odds': 'mean'
        }).round(2)
        
        ev_analysis.columns = ['Bet Count', 'Total Staked', 'Profit/Loss', 'Wins', 'Avg EV%', 'Avg Odds']
        ev_analysis['ROI%'] = (ev_analysis['Profit/Loss'] / ev_analysis['Total Staked'] * 100).round(2)
        ev_analysis['Win Rate%'] = (ev_analysis['Wins'] / ev_analysis['Bet Count'] * 100).round(2)
        
        print(ev_analysis)
        print(f"\nBest ROI EV Range: {ev_analysis['ROI%'].idxmax()}")
        print(f"Worst ROI EV Range: {ev_analysis['ROI%'].idxmin()}")
        
        return ev_analysis
    
    def analyze_by_sport(self):
        """Analyze performance by sport/league."""
        print(f"\n{'='*80}")
        print("ANALYSIS BY SPORT/LEAGUE")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        sport_analysis = df.groupby('sport').agg({
            'recommended_stake': ['count', 'sum'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum(),
            'ev_percentage': 'mean',
            'bet_odds': 'mean'
        }).round(2)
        
        sport_analysis.columns = ['Bet Count', 'Total Staked', 'Profit/Loss', 'Wins', 'Avg EV%', 'Avg Odds']
        sport_analysis['ROI%'] = (sport_analysis['Profit/Loss'] / sport_analysis['Total Staked'] * 100).round(2)
        sport_analysis['Win Rate%'] = (sport_analysis['Wins'] / sport_analysis['Bet Count'] * 100).round(2)
        
        # Sort by ROI
        sport_analysis = sport_analysis.sort_values('ROI%', ascending=False)
        
        print(sport_analysis)
        print(f"\nMost Profitable Sport: {sport_analysis['Profit/Loss'].idxmax()}")
        print(f"Least Profitable Sport: {sport_analysis['Profit/Loss'].idxmin()}")
        print(f"\nBest ROI Sport: {sport_analysis['ROI%'].idxmax()}")
        print(f"Worst ROI Sport: {sport_analysis['ROI%'].idxmin()}")
        
        return sport_analysis
    
    def analyze_by_bookmaker(self):
        """Analyze performance by bookmaker."""
        print(f"\n{'='*80}")
        print("ANALYSIS BY BOOKMAKER")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        bookmaker_analysis = df.groupby('bookmaker').agg({
            'recommended_stake': ['count', 'sum'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum(),
            'ev_percentage': 'mean',
            'bet_odds': 'mean'
        }).round(2)
        
        bookmaker_analysis.columns = ['Bet Count', 'Total Staked', 'Profit/Loss', 'Wins', 'Avg EV%', 'Avg Odds']
        bookmaker_analysis['ROI%'] = (bookmaker_analysis['Profit/Loss'] / bookmaker_analysis['Total Staked'] * 100).round(2)
        bookmaker_analysis['Win Rate%'] = (bookmaker_analysis['Wins'] / bookmaker_analysis['Bet Count'] * 100).round(2)
        
        # Sort by ROI
        bookmaker_analysis = bookmaker_analysis.sort_values('ROI%', ascending=False)
        
        print(bookmaker_analysis)
        print(f"\nMost Profitable Bookmaker: {bookmaker_analysis['Profit/Loss'].idxmax()}")
        print(f"Least Profitable Bookmaker: {bookmaker_analysis['Profit/Loss'].idxmin()}")
        
        return bookmaker_analysis
    
    def analyze_by_market(self):
        """Analyze performance by market type."""
        print(f"\n{'='*80}")
        print("ANALYSIS BY MARKET TYPE")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        market_analysis = df.groupby('market').agg({
            'recommended_stake': ['count', 'sum'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum(),
            'ev_percentage': 'mean',
            'bet_odds': 'mean'
        }).round(2)
        
        market_analysis.columns = ['Bet Count', 'Total Staked', 'Profit/Loss', 'Wins', 'Avg EV%', 'Avg Odds']
        market_analysis['ROI%'] = (market_analysis['Profit/Loss'] / market_analysis['Total Staked'] * 100).round(2)
        market_analysis['Win Rate%'] = (market_analysis['Wins'] / market_analysis['Bet Count'] * 100).round(2)
        
        # Sort by ROI
        market_analysis = market_analysis.sort_values('ROI%', ascending=False)
        
        print(market_analysis)
        print(f"\nMost Profitable Market: {market_analysis['Profit/Loss'].idxmax()}")
        print(f"Least Profitable Market: {market_analysis['Profit/Loss'].idxmin()}")
        
        return market_analysis
    
    def analyze_by_odds_range(self):
        """Analyze performance by odds ranges."""
        print(f"\n{'='*80}")
        print("ANALYSIS BY ODDS RANGE")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        # Define odds ranges
        bins = [1, 2, 3, 5, 7, 10, 100]
        labels = ['1.0-2.0', '2.0-3.0', '3.0-5.0', '5.0-7.0', '7.0-10.0', '10.0+']
        
        df['odds_range'] = pd.cut(df['bet_odds'], bins=bins, labels=labels, include_lowest=True)
        
        odds_analysis = df.groupby('odds_range', observed=True).agg({
            'recommended_stake': ['count', 'sum'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum(),
            'ev_percentage': 'mean',
            'bet_odds': 'mean'
        }).round(2)
        
        odds_analysis.columns = ['Bet Count', 'Total Staked', 'Profit/Loss', 'Wins', 'Avg EV%', 'Avg Odds']
        odds_analysis['ROI%'] = (odds_analysis['Profit/Loss'] / odds_analysis['Total Staked'] * 100).round(2)
        odds_analysis['Win Rate%'] = (odds_analysis['Wins'] / odds_analysis['Bet Count'] * 100).round(2)
        
        print(odds_analysis)
        print(f"\nBest ROI Odds Range: {odds_analysis['ROI%'].idxmax()}")
        print(f"Worst ROI Odds Range: {odds_analysis['ROI%'].idxmin()}")
        
        return odds_analysis
    
    def analyze_by_stake_size(self):
        """Analyze performance by stake size ranges."""
        print(f"\n{'='*80}")
        print("ANALYSIS BY STAKE SIZE")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        # Define stake ranges
        bins = [0, 20, 30, 40, 50, 100, 1000]
        labels = ['0-20', '20-30', '30-40', '40-50', '50-100', '100+']
        
        df['stake_range'] = pd.cut(df['recommended_stake'], bins=bins, labels=labels, include_lowest=True)
        
        stake_analysis = df.groupby('stake_range', observed=True).agg({
            'recommended_stake': ['count', 'sum', 'mean'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum(),
            'ev_percentage': 'mean',
            'bet_odds': 'mean'
        }).round(2)
        
        stake_analysis.columns = ['Bet Count', 'Total Staked', 'Avg Stake', 'Profit/Loss', 'Wins', 'Avg EV%', 'Avg Odds']
        stake_analysis['ROI%'] = (stake_analysis['Profit/Loss'] / stake_analysis['Total Staked'] * 100).round(2)
        stake_analysis['Win Rate%'] = (stake_analysis['Wins'] / stake_analysis['Bet Count'] * 100).round(2)
        
        print(stake_analysis)
        print(f"\nBest ROI Stake Range: {stake_analysis['ROI%'].idxmax()}")
        print(f"Worst ROI Stake Range: {stake_analysis['ROI%'].idxmin()}")
        
        return stake_analysis
    
    def analyze_time_patterns(self):
        """Analyze performance over time."""
        print(f"\n{'='*80}")
        print("TIME-BASED ANALYSIS")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        # By month
        df['month'] = df['date_placed'].dt.to_period('M')
        monthly = df.groupby('month').agg({
            'recommended_stake': ['count', 'sum'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum()
        }).round(2)
        
        monthly.columns = ['Bets', 'Staked', 'Profit/Loss', 'Wins']
        monthly['ROI%'] = (monthly['Profit/Loss'] / monthly['Staked'] * 100).round(2)
        monthly['Win Rate%'] = (monthly['Wins'] / monthly['Bets'] * 100).round(2)
        
        print("Monthly Performance:")
        print(monthly)
        
        # By day of week
        df['day_of_week'] = df['date_placed'].dt.day_name()
        dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        df['day_of_week'] = pd.Categorical(df['day_of_week'], categories=dow_order, ordered=True)
        
        dow = df.groupby('day_of_week', observed=True).agg({
            'recommended_stake': ['count', 'sum'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum()
        }).round(2)
        
        dow.columns = ['Bets', 'Staked', 'Profit/Loss', 'Wins']
        dow['ROI%'] = (dow['Profit/Loss'] / dow['Staked'] * 100).round(2)
        dow['Win Rate%'] = (dow['Wins'] / dow['Bets'] * 100).round(2)
        
        print("\n\nDay of Week Performance:")
        print(dow)
        
        return monthly, dow
    
    def analyze_kelly_performance(self):
        """Analyze Kelly Criterion sizing performance."""
        print(f"\n{'='*80}")
        print("KELLY CRITERION ANALYSIS")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        # By Kelly percentage bins
        bins = [0, 0.5, 1.0, 2.0, 3.0, 5.0, 100]
        labels = ['0-0.5%', '0.5-1%', '1-2%', '2-3%', '3-5%', '5%+']
        
        df['kelly_range'] = pd.cut(df['kelly_percentage'], bins=bins, labels=labels, include_lowest=True)
        
        kelly_analysis = df.groupby('kelly_range', observed=True).agg({
            'recommended_stake': ['count', 'sum', 'mean'],
            'actual_profit_loss': 'sum',
            'bet_result': lambda x: (x == 'win').sum(),
            'ev_percentage': 'mean',
            'kelly_percentage': 'mean'
        }).round(2)
        
        kelly_analysis.columns = ['Bet Count', 'Total Staked', 'Avg Stake', 'Profit/Loss', 'Wins', 'Avg EV%', 'Avg Kelly%']
        kelly_analysis['ROI%'] = (kelly_analysis['Profit/Loss'] / kelly_analysis['Total Staked'] * 100).round(2)
        kelly_analysis['Win Rate%'] = (kelly_analysis['Wins'] / kelly_analysis['Bet Count'] * 100).round(2)
        
        print(kelly_analysis)
        
        return kelly_analysis
    
    def create_visualizations(self):
        """Create comprehensive visualizations in a single PDF."""
        print(f"\n{'='*80}")
        print("GENERATING VISUALIZATIONS")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        # Create output directory for plots
        output_dir = self.csv_path.parent / 'analysis_plots'
        output_dir.mkdir(exist_ok=True)
        
        # Create PDF file
        pdf_filename = output_dir / 'backtest_analysis_report.pdf'
        
        with PdfPages(pdf_filename) as pdf:
            # 1. Bankroll Progression Over Time
            print("✓ Generating: Bankroll Progression Over Time")
            fig, ax = plt.subplots(figsize=(14, 8))
            df_sorted = df.sort_values('date_placed')
            # Get initial bankroll from first row (all rows have same value)
            initial_bankroll = df_sorted['bankroll'].iloc[0]
            df_sorted['cumulative_profit'] = df_sorted['actual_profit_loss'].cumsum()
            df_sorted['actual_bankroll'] = initial_bankroll + df_sorted['cumulative_profit']
            ax.plot(df_sorted['date_placed'], df_sorted['actual_bankroll'], linewidth=2.5, color='steelblue')
            ax.axhline(y=initial_bankroll, color='gray', linestyle='--', alpha=0.5, linewidth=2, label='Initial Bankroll')
            ax.fill_between(df_sorted['date_placed'], df_sorted['actual_bankroll'], initial_bankroll, 
                           where=(df_sorted['actual_bankroll'] >= initial_bankroll), alpha=0.3, color='green', label='Profit')
            ax.fill_between(df_sorted['date_placed'], df_sorted['actual_bankroll'], initial_bankroll, 
                           where=(df_sorted['actual_bankroll'] < initial_bankroll), alpha=0.3, color='red', label='Loss')
            ax.set_title('Bankroll Progression Over Time', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Bankroll ($)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best')
            plt.xticks(rotation=45)
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 2. Bankroll Progression by Bet Number
            print("✓ Generating: Bankroll Progression by Bet Number")
            fig, ax = plt.subplots(figsize=(14, 8))
            df_sorted = df.sort_values('date_placed')
            initial_bankroll = df_sorted['bankroll'].iloc[0]
            df_sorted['cumulative_profit'] = df_sorted['actual_profit_loss'].cumsum()
            df_sorted['actual_bankroll'] = initial_bankroll + df_sorted['cumulative_profit']
            df_sorted['bet_number'] = range(1, len(df_sorted) + 1)
            ax.plot(df_sorted['bet_number'], df_sorted['actual_bankroll'], linewidth=2.5, color='steelblue')
            ax.axhline(y=initial_bankroll, color='gray', linestyle='--', alpha=0.5, linewidth=2, label='Initial Bankroll')
            ax.fill_between(df_sorted['bet_number'], df_sorted['actual_bankroll'], initial_bankroll, 
                           where=(df_sorted['actual_bankroll'] >= initial_bankroll), alpha=0.3, color='green', label='Profit')
            ax.fill_between(df_sorted['bet_number'], df_sorted['actual_bankroll'], initial_bankroll, 
                           where=(df_sorted['actual_bankroll'] < initial_bankroll), alpha=0.3, color='red', label='Loss')
            ax.set_title('Bankroll Progression by Bet Number', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Bet Number', fontsize=12)
            ax.set_ylabel('Bankroll ($)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best')
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 3. Drawdown Percentage Over Time
            print("✓ Generating: Drawdown Percentage Over Time")
            fig, ax = plt.subplots(figsize=(14, 8))
            df_sorted = df.sort_values('date_placed')
            initial_bankroll = df_sorted['bankroll'].iloc[0]
            df_sorted['cumulative_profit'] = df_sorted['actual_profit_loss'].cumsum()
            df_sorted['actual_bankroll'] = initial_bankroll + df_sorted['cumulative_profit']
            
            # Calculate running maximum (peak) and drawdown
            df_sorted['running_max'] = df_sorted['actual_bankroll'].cummax()
            df_sorted['drawdown_pct'] = ((df_sorted['actual_bankroll'] - df_sorted['running_max']) / df_sorted['running_max'] * 100)
            
            ax.fill_between(df_sorted['date_placed'], df_sorted['drawdown_pct'], 0, 
                           alpha=0.4, color='red', label='Drawdown')
            ax.plot(df_sorted['date_placed'], df_sorted['drawdown_pct'], linewidth=2.5, color='darkred')
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.5, linewidth=1)
            
            # Add max drawdown annotation
            max_drawdown = df_sorted['drawdown_pct'].min()
            max_drawdown_date = df_sorted.loc[df_sorted['drawdown_pct'].idxmin(), 'date_placed']
            ax.annotate(f'Max Drawdown: {max_drawdown:.2f}%',
                       xy=(max_drawdown_date, max_drawdown),
                       xytext=(10, -30), textcoords='offset points',
                       bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                       arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'),
                       fontsize=11, fontweight='bold')
            
            ax.set_title('Drawdown Percentage Over Time', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Drawdown (%)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best')
            plt.xticks(rotation=45)
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 4. ROI by EV Range
            print("✓ Generating: ROI by EV Range")
            bins = [0, 5, 10, 15, 20, 25, 30, 100]
            labels = ['0-5%', '5-10%', '10-15%', '15-20%', '20-25%', '25-30%', '30%+']
            df['ev_range'] = pd.cut(df['ev_percentage'], bins=bins, labels=labels, include_lowest=True)
            
            ev_roi = df.groupby('ev_range', observed=True).apply(
                lambda x: (x['actual_profit_loss'].sum() / x['recommended_stake'].sum() * 100) if x['recommended_stake'].sum() > 0 else 0
            ).round(2)
            
            fig, ax = plt.subplots(figsize=(14, 8))
            colors = ['green' if x > 0 else 'red' for x in ev_roi.values]
            bars = ev_roi.plot(kind='bar', ax=ax, color=colors, edgecolor='black', linewidth=1.5)
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.5, linewidth=1)
            ax.set_title('ROI by EV Percentage Range', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('EV Range', fontsize=12)
            ax.set_ylabel('ROI (%)', fontsize=12)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
            # Add value labels on bars
            for i, v in enumerate(ev_roi.values):
                ax.text(i, v + (3 if v > 0 else -3), f'{v:.1f}%', ha='center', va='bottom' if v > 0 else 'top', fontweight='bold')
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 4. Profit by Sport (Top 20)
            print("✓ Generating: Profit by Sport")
            sport_profit = df.groupby('sport')['actual_profit_loss'].sum().sort_values(ascending=False).head(20)
            
            fig, ax = plt.subplots(figsize=(14, 10))
            colors = ['green' if x > 0 else 'red' for x in sport_profit.values]
            sport_profit.plot(kind='barh', ax=ax, color=colors, edgecolor='black', linewidth=1.5)
            ax.axvline(x=0, color='black', linestyle='-', linewidth=1)
            ax.set_title('Top 20 Sports by Profit/Loss', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Profit/Loss ($)', fontsize=12)
            ax.set_ylabel('Sport', fontsize=12)
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 5. Profit by Bookmaker
            print("✓ Generating: Profit by Bookmaker")
            bookmaker_profit = df.groupby('bookmaker')['actual_profit_loss'].sum().sort_values(ascending=False)
            
            fig, ax = plt.subplots(figsize=(14, 8))
            colors = ['green' if x > 0 else 'red' for x in bookmaker_profit.values]
            bookmaker_profit.plot(kind='bar', ax=ax, color=colors, edgecolor='black', linewidth=1.5)
            ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
            ax.set_title('Total Profit/Loss by Bookmaker', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Bookmaker', fontsize=12)
            ax.set_ylabel('Profit/Loss ($)', fontsize=12)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 6. ROI by Market Type
            print("✓ Generating: ROI by Market Type")
            market_roi = df.groupby('market').apply(
                lambda x: (x['actual_profit_loss'].sum() / x['recommended_stake'].sum() * 100) if x['recommended_stake'].sum() > 0 else 0
            ).sort_values(ascending=False).round(2)
            
            fig, ax = plt.subplots(figsize=(14, 8))
            colors = ['green' if x > 0 else 'red' for x in market_roi.values]
            market_roi.plot(kind='bar', ax=ax, color=colors, edgecolor='black', linewidth=1.5)
            ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
            ax.set_title('ROI by Market Type', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Market', fontsize=12)
            ax.set_ylabel('ROI (%)', fontsize=12)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
            # Add value labels
            for i, v in enumerate(market_roi.values):
                ax.text(i, v + (2 if v > 0 else -2), f'{v:.1f}%', ha='center', va='bottom' if v > 0 else 'top', fontweight='bold')
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 7. Win Rate by Odds Range
            print("✓ Generating: Win Rate by Odds Range")
            bins = [1, 2, 3, 5, 7, 10, 100]
            labels = ['1.0-2.0', '2.0-3.0', '3.0-5.0', '5.0-7.0', '7.0-10.0', '10.0+']
            df['odds_range'] = pd.cut(df['bet_odds'], bins=bins, labels=labels, include_lowest=True)
            
            odds_winrate = df.groupby('odds_range', observed=True).apply(
                lambda x: (x['bet_result'] == 'win').sum() / len(x) * 100
            ).round(2)
            
            fig, ax = plt.subplots(figsize=(14, 8))
            odds_winrate.plot(kind='bar', ax=ax, color='coral', edgecolor='black', linewidth=1.5)
            ax.set_title('Win Rate by Odds Range', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Odds Range', fontsize=12)
            ax.set_ylabel('Win Rate (%)', fontsize=12)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
            # Add value labels
            for i, v in enumerate(odds_winrate.values):
                ax.text(i, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontweight='bold')
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 8. EV Distribution
            print("✓ Generating: EV Distribution")
            fig, ax = plt.subplots(figsize=(14, 8))
            ax.hist(df['ev_percentage'], bins=40, edgecolor='black', alpha=0.7, color='skyblue')
            ax.axvline(df['ev_percentage'].mean(), color='red', linestyle='--', linewidth=2, 
                      label=f'Mean: {df["ev_percentage"].mean():.2f}%')
            ax.axvline(df['ev_percentage'].median(), color='green', linestyle='--', linewidth=2, 
                      label=f'Median: {df["ev_percentage"].median():.2f}%')
            ax.set_title('Distribution of EV Percentages', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('EV Percentage', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.legend(fontsize=11)
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 9. Actual vs Expected Profit by Month
            print("✓ Generating: Expected vs Actual Monthly")
            df['month'] = df['date_placed'].dt.to_period('M')
            monthly_comparison = df.groupby('month').agg({
                'expected_profit': 'sum',
                'actual_profit_loss': 'sum'
            })
            
            fig, ax = plt.subplots(figsize=(14, 8))
            x = range(len(monthly_comparison))
            width = 0.35
            bars1 = ax.bar([i - width/2 for i in x], monthly_comparison['expected_profit'], width, 
                          label='Expected', alpha=0.8, edgecolor='black', color='lightblue')
            bars2 = ax.bar([i + width/2 for i in x], monthly_comparison['actual_profit_loss'], width, 
                          label='Actual', alpha=0.8, edgecolor='black', color='lightcoral')
            ax.set_title('Expected vs Actual Profit by Month', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Month', fontsize=12)
            ax.set_ylabel('Profit ($)', fontsize=12)
            ax.set_xticks(x)
            ax.set_xticklabels([str(m) for m in monthly_comparison.index], rotation=45, ha='right')
            ax.legend(fontsize=11)
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 10. Bet Volume by Day of Week
            print("✓ Generating: Bet Volume by Day of Week")
            df['day_of_week'] = df['date_placed'].dt.day_name()
            dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            df['day_of_week'] = pd.Categorical(df['day_of_week'], categories=dow_order, ordered=True)
            
            dow_volume = df['day_of_week'].value_counts().reindex(dow_order, fill_value=0)
            
            fig, ax = plt.subplots(figsize=(14, 8))
            bars = dow_volume.plot(kind='bar', ax=ax, color='teal', edgecolor='black', linewidth=1.5, alpha=0.8)
            ax.set_title('Bet Volume by Day of Week', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Day of Week', fontsize=12)
            ax.set_ylabel('Number of Bets', fontsize=12)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
            # Add value labels on bars
            for i, v in enumerate(dow_volume.values):
                ax.text(i, v + max(dow_volume.values)*0.01, str(v), ha='center', va='bottom', fontweight='bold')
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 11. Bet Volume by Day of Month
            print("✓ Generating: Bet Volume by Day of Month")
            df['day_of_month'] = df['date_placed'].dt.day
            
            dom_volume = df['day_of_month'].value_counts().sort_index()
            
            fig, ax = plt.subplots(figsize=(16, 8))
            bars = dom_volume.plot(kind='bar', ax=ax, color='purple', edgecolor='black', linewidth=1.5, alpha=0.8)
            ax.set_title('Bet Volume by Day of Month', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Day of Month', fontsize=12)
            ax.set_ylabel('Number of Bets', fontsize=12)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 12. Bet Volume by Month of Year
            print("✓ Generating: Bet Volume by Month of Year")
            df['month_name'] = df['date_placed'].dt.month_name()
            month_order = ['January', 'February', 'March', 'April', 'May', 'June', 
                          'July', 'August', 'September', 'October', 'November', 'December']
            df['month_name'] = pd.Categorical(df['month_name'], categories=month_order, ordered=True)
            
            month_volume = df['month_name'].value_counts().reindex(month_order, fill_value=0)
            
            fig, ax = plt.subplots(figsize=(14, 8))
            bars = month_volume.plot(kind='bar', ax=ax, color='orange', edgecolor='black', linewidth=1.5, alpha=0.8)
            ax.set_title('Bet Volume by Month of Year', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Month', fontsize=12)
            ax.set_ylabel('Number of Bets', fontsize=12)
            ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
            # Add value labels on bars
            for i, v in enumerate(month_volume.values):
                if v > 0:  # Only show label if there are bets
                    ax.text(i, v + max(month_volume.values)*0.01, str(v), ha='center', va='bottom', fontweight='bold')
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 13. Bet Volume by Hour of Day
            print("✓ Generating: Bet Volume by Hour of Day")
            # Use timestamp instead of date_placed to get the hour
            if 'timestamp' in df.columns:
                df['timestamp_dt'] = pd.to_datetime(df['timestamp'])
                df['hour'] = df['timestamp_dt'].dt.hour
            else:
                df['hour'] = df['date_placed'].dt.hour
            
            hour_volume = df['hour'].value_counts().sort_index()
            
            fig, ax = plt.subplots(figsize=(16, 8))
            bars = hour_volume.plot(kind='bar', ax=ax, color='crimson', edgecolor='black', linewidth=1.5, alpha=0.8)
            ax.set_title('Bet Volume by Hour of Day (24-hour format)', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Hour of Day', fontsize=12)
            ax.set_ylabel('Number of Bets', fontsize=12)
            ax.set_xticklabels([f'{int(h):02d}:00' for h in hour_volume.index], rotation=45, ha='right')
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 14. Heatmap: Sport vs Market Performance (Top 15 sports)
            print("✓ Generating: Sport vs Market Heatmap")
            top_sports = df.groupby('sport')['actual_profit_loss'].sum().abs().nlargest(15).index
            df_filtered = df[df['sport'].isin(top_sports)]
            
            pivot = df_filtered.pivot_table(
                values='actual_profit_loss',
                index='sport',
                columns='market',
                aggfunc='sum',
                fill_value=0
            )
            
            fig, ax = plt.subplots(figsize=(14, 10))
            sns.heatmap(pivot, annot=True, fmt='.0f', cmap='RdYlGn', center=0, ax=ax, 
                       cbar_kws={'label': 'Profit/Loss ($)'}, linewidths=0.5)
            ax.set_title('Profit/Loss Heatmap: Top 15 Sports vs Market', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Market', fontsize=12)
            ax.set_ylabel('Sport', fontsize=12)
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 11. Combined Dashboard - Key Metrics
            print("✓ Generating: Performance Dashboard")
            fig = plt.figure(figsize=(16, 10))
            gs = fig.add_gridspec(3, 3, hspace=0.4, wspace=0.3)
            
            # Day of week profit
            df['day_of_week'] = df['date_placed'].dt.day_name()
            dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            df['day_of_week'] = pd.Categorical(df['day_of_week'], categories=dow_order, ordered=True)
            dow_profit = df.groupby('day_of_week', observed=True)['actual_profit_loss'].sum()
            
            ax1 = fig.add_subplot(gs[0, 0])
            colors = ['green' if x > 0 else 'red' for x in dow_profit.values]
            dow_profit.plot(kind='bar', ax=ax1, color=colors, edgecolor='black')
            ax1.set_title('Profit by Day of Week', fontweight='bold')
            ax1.set_xlabel('')
            ax1.set_ylabel('Profit ($)')
            ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax1.tick_params(axis='x', rotation=45)
            
            # Bet volume by day
            dow_volume = df['day_of_week'].value_counts().reindex(dow_order)
            ax2 = fig.add_subplot(gs[0, 1])
            dow_volume.plot(kind='bar', ax=ax2, color='mediumpurple', edgecolor='black')
            ax2.set_title('Bet Volume by Day', fontweight='bold')
            ax2.set_xlabel('')
            ax2.set_ylabel('Number of Bets')
            ax2.tick_params(axis='x', rotation=45)
            
            # ROI by stake size
            bins = [0, 20, 30, 40, 50, 100, 1000]
            labels = ['0-20', '20-30', '30-40', '40-50', '50-100', '100+']
            df['stake_range'] = pd.cut(df['recommended_stake'], bins=bins, labels=labels, include_lowest=True)
            stake_roi = df.groupby('stake_range', observed=True).apply(
                lambda x: (x['actual_profit_loss'].sum() / x['recommended_stake'].sum() * 100) if x['recommended_stake'].sum() > 0 else 0
            )
            
            ax3 = fig.add_subplot(gs[0, 2])
            colors = ['green' if x > 0 else 'red' for x in stake_roi.values]
            stake_roi.plot(kind='bar', ax=ax3, color=colors, edgecolor='black')
            ax3.set_title('ROI by Stake Size', fontweight='bold')
            ax3.set_xlabel('Stake Range ($)')
            ax3.set_ylabel('ROI (%)')
            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax3.tick_params(axis='x', rotation=45)
            
            # Monthly profit trend
            monthly_profit = df.groupby('month')['actual_profit_loss'].sum()
            ax4 = fig.add_subplot(gs[1, :])
            ax4.bar(range(len(monthly_profit)), monthly_profit.values, 
                   color=['green' if x > 0 else 'red' for x in monthly_profit.values],
                   edgecolor='black', alpha=0.7)
            ax4.plot(range(len(monthly_profit)), monthly_profit.cumsum().values, 
                    color='blue', linewidth=2, marker='o', label='Cumulative')
            ax4.set_title('Monthly Profit Trend', fontweight='bold', fontsize=12)
            ax4.set_xlabel('Month')
            ax4.set_ylabel('Profit ($)')
            ax4.set_xticks(range(len(monthly_profit)))
            ax4.set_xticklabels([str(m) for m in monthly_profit.index], rotation=45, ha='right')
            ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            
            # Top bookmakers comparison
            top_bookmakers = df.groupby('bookmaker')['actual_profit_loss'].sum().nlargest(5)
            ax5 = fig.add_subplot(gs[2, 0])
            colors = ['green' if x > 0 else 'red' for x in top_bookmakers.values]
            top_bookmakers.plot(kind='barh', ax=ax5, color=colors, edgecolor='black')
            ax5.set_title('Top 5 Bookmakers by Profit', fontweight='bold', fontsize=10)
            ax5.set_xlabel('Profit ($)')
            ax5.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
            
            # Market comparison
            market_comparison = df.groupby('market').agg({
                'actual_profit_loss': 'sum',
                'recommended_stake': 'count'
            })
            ax6 = fig.add_subplot(gs[2, 1])
            market_comparison['actual_profit_loss'].plot(kind='bar', ax=ax6, 
                color=['green' if x > 0 else 'red' for x in market_comparison['actual_profit_loss'].values],
                edgecolor='black')
            ax6.set_title('Profit by Market', fontweight='bold')
            ax6.set_xlabel('Market')
            ax6.set_ylabel('Profit ($)')
            ax6.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax6.tick_params(axis='x', rotation=45)
            
            # Summary stats table
            ax7 = fig.add_subplot(gs[2, 2])
            ax7.axis('off')
            summary_data = [
                ['Total Bets', f"{len(df):,}"],
                ['Total Staked', f"${df['recommended_stake'].sum():,.0f}"],
                ['Total Profit', f"${df['actual_profit_loss'].sum():,.0f}"],
                ['ROI', f"{(df['actual_profit_loss'].sum() / df['recommended_stake'].sum() * 100):.2f}%"],
                ['Win Rate', f"{(df['bet_result'] == 'win').sum() / len(df) * 100:.2f}%"],
                ['Avg EV', f"{df['ev_percentage'].mean():.2f}%"],
            ]
            table = ax7.table(cellText=summary_data, cellLoc='left', loc='center',
                            colWidths=[0.6, 0.4])
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2)
            for i in range(len(summary_data)):
                table[(i, 0)].set_facecolor('#E8E8E8')
                table[(i, 0)].set_text_props(weight='bold')
                table[(i, 1)].set_facecolor('#F5F5F5')
            ax7.set_title('Summary Statistics', fontweight='bold', pad=20)
            
            fig.suptitle('Backtest Performance Dashboard', fontsize=18, fontweight='bold', y=0.98)
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 11. ROI vs EV Scatter Plot - Validate model accuracy
            print("✓ Generating: ROI vs EV Validation")
            fig, ax = plt.subplots(figsize=(14, 8))
            
            # Group by EV percentage bins and calculate actual ROI
            df['ev_bin'] = pd.cut(df['ev_percentage'], bins=20)
            scatter_data = df.groupby('ev_bin', observed=True).agg({
                'ev_percentage': 'mean',
                'actual_profit_loss': 'sum',
                'recommended_stake': ['sum', 'count']
            })
            scatter_data['roi'] = (scatter_data[('actual_profit_loss', 'sum')] / 
                                  scatter_data[('recommended_stake', 'sum')] * 100)
            scatter_data['bet_count'] = scatter_data[('recommended_stake', 'count')]
            scatter_data['ev_mean'] = scatter_data[('ev_percentage', 'mean')]
            
            # Scatter plot with size based on bet count
            scatter = ax.scatter(scatter_data['ev_mean'], scatter_data['roi'], 
                               s=scatter_data['bet_count']*2, alpha=0.6, c=scatter_data['roi'],
                               cmap='RdYlGn', edgecolors='black', linewidth=1)
            
            # Add diagonal line showing perfect correlation
            max_val = max(scatter_data['ev_mean'].max(), scatter_data['roi'].max())
            ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2, alpha=0.5, label='Perfect Correlation')
            
            # Add trend line
            z = np.polyfit(scatter_data['ev_mean'].dropna(), scatter_data['roi'].dropna(), 1)
            p = np.poly1d(z)
            ax.plot(scatter_data['ev_mean'].sort_values(), p(scatter_data['ev_mean'].sort_values()), 
                   "b-", linewidth=2, alpha=0.7, label=f'Trend: ROI = {z[0]:.2f}×EV + {z[1]:.2f}')
            
            ax.set_title('Model Validation: Expected EV vs Actual ROI', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Expected Value (%)', fontsize=12)
            ax.set_ylabel('Actual ROI (%)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=11)
            plt.colorbar(scatter, ax=ax, label='ROI (%)')
            ax.text(0.02, 0.98, 'Bubble size = # of bets', transform=ax.transAxes, 
                   fontsize=10, verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 12. Drawdown Analysis
            print("✓ Generating: Drawdown Analysis")
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
            
            df_sorted = df.sort_values('date_placed')
            initial_bankroll = df_sorted['bankroll'].iloc[0]
            df_sorted['cumulative'] = df_sorted['actual_profit_loss'].cumsum()
            df_sorted['actual_bankroll'] = initial_bankroll + df_sorted['cumulative']
            df_sorted['running_max'] = df_sorted['actual_bankroll'].cummax()
            df_sorted['drawdown'] = df_sorted['actual_bankroll'] - df_sorted['running_max']
            df_sorted['drawdown_pct'] = (df_sorted['drawdown'] / df_sorted['running_max']) * 100
            
            # Bankroll with drawdown
            ax1.plot(df_sorted['date_placed'], df_sorted['actual_bankroll'], linewidth=2, label='Bankroll', color='blue')
            ax1.plot(df_sorted['date_placed'], df_sorted['running_max'], linewidth=2, linestyle='--', 
                    label='Peak Bankroll', color='green', alpha=0.7)
            ax1.fill_between(df_sorted['date_placed'], df_sorted['actual_bankroll'], df_sorted['running_max'], 
                           alpha=0.3, color='red', label='Drawdown')
            ax1.set_title('Bankroll with Drawdown Periods', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Bankroll ($)', fontsize=12)
            ax1.legend(loc='best')
            ax1.grid(True, alpha=0.3)
            
            # Drawdown chart
            ax2.fill_between(df_sorted['date_placed'], df_sorted['drawdown'], 0, alpha=0.7, color='red')
            ax2.plot(df_sorted['date_placed'], df_sorted['drawdown'], linewidth=1, color='darkred')
            max_dd = df_sorted['drawdown'].min()
            max_dd_date = df_sorted.loc[df_sorted['drawdown'].idxmin(), 'date_placed']
            ax2.axhline(y=max_dd, color='black', linestyle='--', linewidth=1, alpha=0.5)
            ax2.text(max_dd_date, max_dd, f'Max DD: ${max_dd:.0f}', fontsize=10, 
                    verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
            ax2.set_title('Drawdown Over Time', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Date', fontsize=12)
            ax2.set_ylabel('Drawdown ($)', fontsize=12)
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 13. Win/Loss Streaks Analysis
            print("✓ Generating: Win/Loss Streaks")
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            df_sorted = df.sort_values('date_placed')
            df_sorted['win'] = (df_sorted['bet_result'] == 'win').astype(int)
            df_sorted['streak'] = df_sorted['win'].groupby((df_sorted['win'] != df_sorted['win'].shift()).cumsum()).cumsum()
            df_sorted['loss_streak'] = (1 - df_sorted['win']).groupby(((1 - df_sorted['win']) != (1 - df_sorted['win']).shift()).cumsum()).cumsum()
            
            # Win streaks
            win_streaks = df_sorted[df_sorted['win'] == 1].groupby((df_sorted['win'] != df_sorted['win'].shift()).cumsum())['streak'].max()
            if len(win_streaks) > 0:
                ax1.hist(win_streaks, bins=range(1, win_streaks.max()+2), edgecolor='black', alpha=0.7, color='green')
                ax1.axvline(win_streaks.mean(), color='red', linestyle='--', linewidth=2, 
                          label=f'Avg: {win_streaks.mean():.1f}')
                ax1.axvline(win_streaks.max(), color='darkgreen', linestyle='--', linewidth=2, 
                          label=f'Max: {win_streaks.max():.0f}')
            ax1.set_title('Win Streak Distribution', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Consecutive Wins', fontsize=12)
            ax1.set_ylabel('Frequency', fontsize=12)
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Loss streaks
            loss_streaks = df_sorted[df_sorted['win'] == 0].groupby(((1 - df_sorted['win']) != (1 - df_sorted['win']).shift()).cumsum())['loss_streak'].max()
            if len(loss_streaks) > 0:
                ax2.hist(loss_streaks, bins=range(1, min(loss_streaks.max()+2, 30)), edgecolor='black', alpha=0.7, color='red')
                ax2.axvline(loss_streaks.mean(), color='darkred', linestyle='--', linewidth=2, 
                          label=f'Avg: {loss_streaks.mean():.1f}')
                ax2.axvline(loss_streaks.max(), color='black', linestyle='--', linewidth=2, 
                          label=f'Max: {loss_streaks.max():.0f}')
            ax2.set_title('Loss Streak Distribution', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Consecutive Losses', fontsize=12)
            ax2.set_ylabel('Frequency', fontsize=12)
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 14. Bookmaker ROI Comparison (Detailed)
            print("✓ Generating: Bookmaker Deep Dive")
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
            
            bookmaker_stats = df.groupby('bookmaker').agg({
                'actual_profit_loss': 'sum',
                'recommended_stake': ['sum', 'count'],
                'bet_result': lambda x: (x == 'win').sum(),
                'ev_percentage': 'mean'
            })
            bookmaker_stats.columns = ['profit', 'stake', 'bets', 'wins', 'avg_ev']
            bookmaker_stats['roi'] = (bookmaker_stats['profit'] / bookmaker_stats['stake'] * 100)
            bookmaker_stats['win_rate'] = (bookmaker_stats['wins'] / bookmaker_stats['bets'] * 100)
            bookmaker_stats = bookmaker_stats.sort_values('roi', ascending=False)
            
            # ROI comparison
            colors = ['green' if x > 0 else 'red' for x in bookmaker_stats['roi'].values]
            bookmaker_stats['roi'].plot(kind='barh', ax=ax1, color=colors, edgecolor='black')
            ax1.axvline(x=0, color='black', linestyle='-', linewidth=1)
            ax1.set_title('ROI by Bookmaker', fontweight='bold')
            ax1.set_xlabel('ROI (%)')
            
            # Win rate comparison
            bookmaker_stats['win_rate'].sort_values(ascending=False).plot(kind='barh', ax=ax2, 
                                                                          color='skyblue', edgecolor='black')
            ax2.set_title('Win Rate by Bookmaker', fontweight='bold')
            ax2.set_xlabel('Win Rate (%)')
            
            # Total profit comparison
            top_profit = bookmaker_stats.nlargest(10, 'profit')
            colors = ['green' if x > 0 else 'red' for x in top_profit['profit'].values]
            top_profit['profit'].plot(kind='barh', ax=ax3, color=colors, edgecolor='black')
            ax3.axvline(x=0, color='black', linestyle='-', linewidth=1)
            ax3.set_title('Top 10 Bookmakers by Total Profit', fontweight='bold')
            ax3.set_xlabel('Total Profit ($)')
            
            # Bet volume comparison
            bookmaker_stats.nlargest(10, 'bets')['bets'].plot(kind='barh', ax=ax4, 
                                                               color='mediumpurple', edgecolor='black')
            ax4.set_title('Top 10 Bookmakers by Bet Volume', fontweight='bold')
            ax4.set_xlabel('Number of Bets')
            
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 15. Profit Distribution
            print("✓ Generating: Profit Distribution Analysis")
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
            
            # Individual bet profit distribution
            ax1.hist(df['actual_profit_loss'], bins=50, edgecolor='black', alpha=0.7, color='steelblue')
            ax1.axvline(df['actual_profit_loss'].mean(), color='red', linestyle='--', linewidth=2,
                       label=f'Mean: ${df["actual_profit_loss"].mean():.2f}')
            ax1.axvline(df['actual_profit_loss'].median(), color='green', linestyle='--', linewidth=2,
                       label=f'Median: ${df["actual_profit_loss"].median():.2f}')
            ax1.set_title('Individual Bet Profit/Loss Distribution', fontweight='bold')
            ax1.set_xlabel('Profit/Loss ($)')
            ax1.set_ylabel('Frequency')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Win size vs Loss size
            wins = df[df['bet_result'] == 'win']['actual_profit_loss']
            losses = df[df['bet_result'] == 'loss']['actual_profit_loss']
            
            ax2.hist([wins, losses.abs()], bins=30, label=['Wins', 'Losses'], 
                    color=['green', 'red'], alpha=0.6, edgecolor='black')
            ax2.set_title('Win Size vs Loss Size Distribution', fontweight='bold')
            ax2.set_xlabel('Amount ($)')
            ax2.set_ylabel('Frequency')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # Box plot by EV range
            bins = [0, 10, 15, 20, 25, 100]
            labels = ['0-10%', '10-15%', '15-20%', '20-25%', '25%+']
            df['ev_range_box'] = pd.cut(df['ev_percentage'], bins=bins, labels=labels, include_lowest=True)
            
            df.boxplot(column='actual_profit_loss', by='ev_range_box', ax=ax3)
            ax3.set_title('Profit Distribution by EV Range', fontweight='bold')
            ax3.set_xlabel('EV Range')
            ax3.set_ylabel('Profit/Loss ($)')
            ax3.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5)
            plt.sca(ax3)
            plt.xticks(rotation=45)
            
            # Cumulative profit by bet number
            df_sorted = df.sort_values('date_placed')
            df_sorted['bet_number'] = range(1, len(df_sorted) + 1)
            df_sorted['cumulative'] = df_sorted['actual_profit_loss'].cumsum()
            
            ax4.plot(df_sorted['bet_number'], df_sorted['cumulative'], linewidth=2, color='blue')
            ax4.fill_between(df_sorted['bet_number'], df_sorted['cumulative'], 0, 
                           where=(df_sorted['cumulative'] >= 0), alpha=0.3, color='green')
            ax4.fill_between(df_sorted['bet_number'], df_sorted['cumulative'], 0, 
                           where=(df_sorted['cumulative'] < 0), alpha=0.3, color='red')
            ax4.set_title('Cumulative Profit by Bet Number', fontweight='bold')
            ax4.set_xlabel('Bet Number')
            ax4.set_ylabel('Cumulative Profit ($)')
            ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 16. Time-Based Patterns Deep Dive
            print("✓ Generating: Time Pattern Analysis")
            fig = plt.figure(figsize=(14, 10))
            gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
            
            # Hour of day (if timestamp available)
            if 'timestamp' in df.columns:
                try:
                    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
                    hourly_profit = df.groupby('hour')['actual_profit_loss'].sum()
                    ax1 = fig.add_subplot(gs[0, 0])
                    colors = ['green' if x > 0 else 'red' for x in hourly_profit.values]
                    hourly_profit.plot(kind='bar', ax=ax1, color=colors, edgecolor='black')
                    ax1.set_title('Profit by Hour of Day', fontweight='bold')
                    ax1.set_xlabel('Hour')
                    ax1.set_ylabel('Profit ($)')
                    ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                except:
                    ax1 = fig.add_subplot(gs[0, 0])
                    ax1.text(0.5, 0.5, 'Hour data not available', ha='center', va='center')
                    ax1.axis('off')
            else:
                ax1 = fig.add_subplot(gs[0, 0])
                ax1.text(0.5, 0.5, 'Hour data not available', ha='center', va='center')
                ax1.axis('off')
            
            # Rolling 30-bet average
            ax2 = fig.add_subplot(gs[0, 1])
            df_sorted = df.sort_values('date_placed')
            df_sorted['rolling_roi'] = (df_sorted['actual_profit_loss'].rolling(30).sum() / 
                                       df_sorted['recommended_stake'].rolling(30).sum() * 100)
            ax2.plot(df_sorted['date_placed'], df_sorted['rolling_roi'], linewidth=2, color='purple')
            ax2.axhline(y=0, color='red', linestyle='--', linewidth=1)
            ax2.set_title('Rolling 30-Bet ROI', fontweight='bold')
            ax2.set_ylabel('ROI (%)')
            ax2.grid(True, alpha=0.3)
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
            # Month-over-month growth
            ax3 = fig.add_subplot(gs[1, :])
            df['month'] = df['date_placed'].dt.to_period('M')
            monthly_profit = df.groupby('month')['actual_profit_loss'].sum()
            
            ax3.bar(range(len(monthly_profit)), monthly_profit.values,
                   color=['green' if x > 0 else 'red' for x in monthly_profit.values],
                   edgecolor='black', alpha=0.7, label='Monthly Profit')
            
            # Add cumulative line
            ax3_twin = ax3.twinx()
            ax3_twin.plot(range(len(monthly_profit)), monthly_profit.cumsum().values,
                         color='blue', linewidth=3, marker='o', markersize=6, label='Cumulative')
            
            ax3.set_title('Monthly Profit with Cumulative Trend', fontweight='bold', fontsize=12)
            ax3.set_xlabel('Month')
            ax3.set_ylabel('Monthly Profit ($)', color='black')
            ax3_twin.set_ylabel('Cumulative Profit ($)', color='blue')
            ax3.set_xticks(range(len(monthly_profit)))
            ax3.set_xticklabels([str(m) for m in monthly_profit.index], rotation=45, ha='right')
            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax3.legend(loc='upper left')
            ax3_twin.legend(loc='upper right')
            ax3.grid(True, alpha=0.3)
            
            # Week of month pattern
            ax4 = fig.add_subplot(gs[2, 0])
            df['week_of_month'] = ((df['date_placed'].dt.day - 1) // 7) + 1
            week_profit = df.groupby('week_of_month')['actual_profit_loss'].sum()
            colors = ['green' if x > 0 else 'red' for x in week_profit.values]
            week_profit.plot(kind='bar', ax=ax4, color=colors, edgecolor='black')
            ax4.set_title('Profit by Week of Month', fontweight='bold')
            ax4.set_xlabel('Week (1=First week, 5=Last few days)')
            ax4.set_ylabel('Profit ($)')
            ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax4.tick_params(axis='x', rotation=0)
            
            # Quarter analysis
            ax5 = fig.add_subplot(gs[2, 1])
            df['quarter'] = df['date_placed'].dt.quarter
            df['year'] = df['date_placed'].dt.year
            df['year_quarter'] = df['year'].astype(str) + '-Q' + df['quarter'].astype(str)
            quarter_profit = df.groupby('year_quarter')['actual_profit_loss'].sum()
            colors = ['green' if x > 0 else 'red' for x in quarter_profit.values]
            quarter_profit.plot(kind='bar', ax=ax5, color=colors, edgecolor='black')
            ax5.set_title('Profit by Quarter', fontweight='bold')
            ax5.set_xlabel('Quarter')
            ax5.set_ylabel('Profit ($)')
            ax5.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax5.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            pdf.savefig(fig, dpi=300, bbox_inches='tight')
            plt.close()
            
            # Add metadata to PDF
            d = pdf.infodict()
            d['Title'] = 'Backtest Analysis Report'
            d['Author'] = 'Betting Analysis Script'
            d['Subject'] = 'Comprehensive betting backtest analysis'
            d['Keywords'] = 'Betting, Analysis, EV, ROI, Sports'
            d['CreationDate'] = datetime.now()
        
        print(f"\n✓ All visualizations saved to: {pdf_filename}")
        print(f"  Total pages: 22")
        print(f"  File size: {pdf_filename.stat().st_size / 1024 / 1024:.2f} MB")
    
    def generate_full_report(self):
        """Generate complete analysis report."""
        print(f"\n{'#'*80}")
        print(f"# COMPREHENSIVE BACKTEST ANALYSIS REPORT")
        print(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"# File: {self.csv_path.name}")
        print(f"{'#'*80}")
        
        # Run all analyses
        self.overall_summary()
        self.analyze_by_ev_range()
        self.analyze_by_sport()
        self.analyze_by_bookmaker()
        self.analyze_by_market()
        self.analyze_by_odds_range()
        self.analyze_by_stake_size()
        self.analyze_time_patterns()
        self.analyze_kelly_performance()
        
        # Generate visualizations
        self.create_visualizations()
        
        print(f"\n{'='*80}")
        print("ANALYSIS COMPLETE!")
        print(f"{'='*80}\n")
        
        # Key Findings Summary
        self.print_key_findings()
    
    def print_key_findings(self):
        """Print summary of key findings and recommendations."""
        print(f"\n{'='*80}")
        print("KEY FINDINGS & RECOMMENDATIONS")
        print(f"{'='*80}\n")
        
        df = self.settled_df
        
        # Best performing categories
        print("TOP PERFORMERS:")
        print("-" * 80)
        
        # Best sport
        sport_roi = df.groupby('sport').apply(
            lambda x: (x['actual_profit_loss'].sum() / x['recommended_stake'].sum() * 100) if x['recommended_stake'].sum() > 0 else 0
        ).sort_values(ascending=False)
        if len(sport_roi) > 0:
            print(f"✓ Best Sport (ROI): {sport_roi.index[0]} ({sport_roi.iloc[0]:.2f}%)")
        
        # Best bookmaker
        book_roi = df.groupby('bookmaker').apply(
            lambda x: (x['actual_profit_loss'].sum() / x['recommended_stake'].sum() * 100) if x['recommended_stake'].sum() > 0 else 0
        ).sort_values(ascending=False)
        if len(book_roi) > 0:
            print(f"✓ Best Bookmaker (ROI): {book_roi.index[0]} ({book_roi.iloc[0]:.2f}%)")
        
        # Best market
        market_roi = df.groupby('market').apply(
            lambda x: (x['actual_profit_loss'].sum() / x['recommended_stake'].sum() * 100) if x['recommended_stake'].sum() > 0 else 0
        ).sort_values(ascending=False)
        if len(market_roi) > 0:
            print(f"✓ Best Market (ROI): {market_roi.index[0]} ({market_roi.iloc[0]:.2f}%)")
        
        # Best EV range
        bins = [0, 5, 10, 15, 20, 25, 30, 100]
        labels = ['0-5%', '5-10%', '10-15%', '15-20%', '20-25%', '25-30%', '30%+']
        df['ev_range'] = pd.cut(df['ev_percentage'], bins=bins, labels=labels, include_lowest=True)
        
        ev_roi = df.groupby('ev_range', observed=True).apply(
            lambda x: (x['actual_profit_loss'].sum() / x['recommended_stake'].sum() * 100) if x['recommended_stake'].sum() > 0 else 0
        ).sort_values(ascending=False)
        if len(ev_roi) > 0:
            print(f"✓ Best EV Range (ROI): {ev_roi.index[0]} ({ev_roi.iloc[0]:.2f}%)")
        
        print("\n" + "-" * 80)
        print("WORST PERFORMERS:")
        print("-" * 80)
        
        # Worst categories
        if len(sport_roi) > 0:
            print(f"✗ Worst Sport (ROI): {sport_roi.index[-1]} ({sport_roi.iloc[-1]:.2f}%)")
        if len(book_roi) > 0:
            print(f"✗ Worst Bookmaker (ROI): {book_roi.index[-1]} ({book_roi.iloc[-1]:.2f}%)")
        if len(market_roi) > 0:
            print(f"✗ Worst Market (ROI): {market_roi.index[-1]} ({market_roi.iloc[-1]:.2f}%)")
        
        print("\n" + "-" * 80)
        print("RECOMMENDATIONS:")
        print("-" * 80)
        
        total_roi = (df['actual_profit_loss'].sum() / df['recommended_stake'].sum() * 100)
        
        if total_roi > 0:
            print(f"✓ Overall strategy is profitable (ROI: {total_roi:.2f}%)")
            print(f"✓ Consider increasing stake sizes on best-performing categories")
            print(f"✓ Focus on: {sport_roi.index[0]}, {book_roi.index[0]}, {market_roi.index[0]}")
        else:
            print(f"✗ Overall strategy is unprofitable (ROI: {total_roi:.2f}%)")
            print(f"✗ Consider avoiding: {sport_roi.index[-1]}, {book_roi.index[-1]}, {market_roi.index[-1]}")
        
        # Check if high EV is actually better
        if len(ev_roi) > 2:
            if ev_roi.iloc[0] < ev_roi.iloc[-1]:
                print(f"⚠ Warning: Lower EV bets performing better than high EV bets - review model")
        
        print()


def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_backtest.py <path_to_csv_file>")
        print("Example: python analyze_backtest.py data/backtest_bet_history.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    if not Path(csv_file).exists():
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)
    
    # Run analysis
    analyzer = BacktestAnalyzer(csv_file)
    analyzer.generate_full_report()


if __name__ == "__main__":
    main()
