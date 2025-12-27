#!/usr/bin/env python3
"""
Test SerpAPI Sports Results integration.

Usage:
    python3 scripts/test_serpapi.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from src.utils.google_search_scraper import GoogleSearchScraper


def test_serpapi():
    """Test SerpAPI configuration and score fetching."""
    
    print("=" * 60)
    print("Testing SerpAPI Sports Results Integration")
    print("=" * 60)
    
    # Initialize scraper
    try:
        scraper = GoogleSearchScraper()
        print("✅ SerpAPI configuration loaded")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("\nTo fix this:")
        print("1. Sign up at https://serpapi.com/")
        print("2. Get your API key from https://serpapi.com/manage-api-key")
        print("3. Add to .env file: SERPAPI_KEY=your_key_here")
        return
    
    print()
    
    # Test cases
    test_cases = [
        {
            'description': 'Premier League: Plymouth vs Bristol City (2025-01-01)',
            'query': 'Plymouth Argyle vs Bristol City 2025-01-01 score',
            'away_team': 'Bristol City',
            'home_team': 'Plymouth Argyle',
            'expected': '2-2 draw'
        },
        {
            'description': 'NFL: Bills vs Patriots',
            'query': 'Buffalo Bills vs New England Patriots December 2024 final score',
            'away_team': 'New England Patriots',
            'home_team': 'Buffalo Bills',
            'expected': None
        },
        {
            'description': 'NBA: Lakers recent game',
            'query': 'Los Angeles Lakers last game result',
            'away_team': 'Lakers',
            'home_team': 'Opponent',
            'expected': None
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"Test {i}: {test['description']}")
        print(f"Query: {test['query']}")
        print("=" * 60)
        
        # Search
        print("\n🔍 Searching...")
        results = scraper.search_sports_score(test['query'])
        
        if not results:
            print("❌ No results returned")
            continue
        
        # Check for sports_results
        if 'sports_results' in results:
            print("✅ Found sports_results in response")
            
            sports = results['sports_results']
            
            # Show what we found
            if 'game_spotlight' in sports:
                print("\n📌 Game Spotlight:")
                gs = sports['game_spotlight']
                print(f"   League: {gs.get('league', 'N/A')}")
                print(f"   Date: {gs.get('date', 'N/A')}")
                print(f"   Status: {gs.get('status', 'N/A')}")
                if 'teams' in gs:
                    print(f"   Teams:")
                    for team in gs['teams']:
                        print(f"      {team.get('name', 'N/A')}: {team.get('score', 'N/A')}")
            
            if 'games' in sports and sports['games']:
                print(f"\n📅 Found {len(sports['games'])} games")
                for j, game in enumerate(sports['games'][:3], 1):
                    print(f"\n   Game {j}:")
                    print(f"      Tournament: {game.get('tournament', 'N/A')}")
                    print(f"      Date: {game.get('date', 'N/A')}")
                    if 'teams' in game:
                        for team in game['teams']:
                            print(f"      {team.get('name', 'N/A')}: {team.get('score', 'N/A')}")
        else:
            print("⚠️  No sports_results found in response")
            if 'organic_results' in results:
                print(f"   Found {len(results['organic_results'])} organic results instead")
        
        # Try to parse score
        print("\n🎯 Parsing score...")
        score = scraper.parse_score_from_results(results, test['away_team'], test['home_team'])
        
        if score:
            away_score, home_score, winner = score
            print(f"✅ Score parsed: {test['away_team']} {away_score} - {home_score} {test['home_team']}")
            print(f"   Winner: {winner}")
            if test['expected']:
                print(f"   Expected: {test['expected']}")
        else:
            print("❌ Could not parse score")
            if test['expected']:
                print(f"   Expected: {test['expected']}")
    
    # Print statistics
    print("\n" + "=" * 60)
    scraper.print_stats()
    print("=" * 60)


if __name__ == '__main__':
    test_serpapi()
