#!/bin/bash
# Quick Test Runner Script for Positive EV Sports Betting System
# This script provides easy commands to run tests in different configurations

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Test Runner - Positive EV System${NC}"
echo -e "${BLUE}================================${NC}\n"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}pytest not found. Installing test dependencies...${NC}"
    pip install -r requirements.txt
fi

# Parse command line arguments
TEST_TYPE=${1:-all}

case $TEST_TYPE in
    all)
        echo -e "${GREEN}Running all tests...${NC}\n"
        pytest -v
        ;;
    
    fast)
        echo -e "${GREEN}Running fast tests only...${NC}\n"
        pytest -v -m "not slow"
        ;;
    
    coverage)
        echo -e "${GREEN}Running tests with coverage report...${NC}\n"
        pytest --cov=src --cov-report=term-missing --cov-report=html
        echo -e "\n${GREEN}✓ Coverage report generated in htmlcov/index.html${NC}"
        ;;
    
    kelly)
        echo -e "${GREEN}Running Kelly Criterion tests...${NC}\n"
        pytest -v tests/test_kelly_criterion.py
        ;;
    
    scanner)
        echo -e "${GREEN}Running EV Scanner tests...${NC}\n"
        pytest -v tests/test_positive_ev_scanner.py
        ;;
    
    logger)
        echo -e "${GREEN}Running Bet Logger tests...${NC}\n"
        pytest -v tests/test_bet_logger.py
        ;;
    
    backtest)
        echo -e "${GREEN}Running Backtest tests...${NC}\n"
        pytest -v tests/test_backtest.py
        ;;
    
    action)
        echo -e "${GREEN}Running Action Logger tests...${NC}\n"
        pytest -v tests/test_action_logger.py
        ;;
    
    auto)
        echo -e "${GREEN}Running Auto Bet Placer tests...${NC}\n"
        pytest -v tests/test_auto_bet_placer.py
        ;;
    
    manage)
        echo -e "${GREEN}Running Manage Bets tests...${NC}\n"
        pytest -v tests/test_manage_bets.py
        ;;
    
    verbose)
        echo -e "${GREEN}Running all tests with verbose output...${NC}\n"
        pytest -vv -s
        ;;
    
    debug)
        echo -e "${GREEN}Running tests in debug mode (drops to debugger on failure)...${NC}\n"
        pytest -vv --pdb
        ;;
    
    help)
        echo "Usage: ./run_tests.sh [option]"
        echo ""
        echo "Options:"
        echo "  all        - Run all tests (default)"
        echo "  fast       - Run only fast tests (exclude slow tests)"
        echo "  coverage   - Run tests with coverage report"
        echo "  kelly      - Run Kelly Criterion tests only"
        echo "  scanner    - Run EV Scanner tests only"
        echo "  logger     - Run Bet Logger tests only"
        echo "  backtest   - Run Backtest tests only"
        echo "  action     - Run Action Logger tests only"
        echo "  auto       - Run Auto Bet Placer tests only"
        echo "  manage     - Run Manage Bets tests only"
        echo "  verbose    - Run all tests with extra verbose output"
        echo "  debug      - Run tests in debug mode"
        echo "  help       - Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh                  # Run all tests"
        echo "  ./run_tests.sh coverage        # Run with coverage"
        echo "  ./run_tests.sh kelly           # Run Kelly tests only"
        ;;
    
    *)
        echo -e "${YELLOW}Unknown option: $TEST_TYPE${NC}"
        echo "Run './run_tests.sh help' for usage information"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}✓ Test run complete!${NC}"
echo -e "${BLUE}================================${NC}"
