#!/bin/bash
# Quick Test Runner Script for Positive EV Sports Betting System
# This script provides easy commands to run tests in different configurations

# Note: Don't use 'set -e' here because we want to show test results even if some tests fail
# The script will still return the pytest exit code at the end

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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
        TEST_EXIT_CODE=$?
        ;;
    
    fast)
        echo -e "${GREEN}Running fast tests only...${NC}\n"
        pytest -v -m "not slow"
        TEST_EXIT_CODE=$?
        ;;
    
    coverage)
        echo -e "${GREEN}Running tests with coverage report...${NC}\n"
        pytest --cov=src --cov-report=term-missing --cov-report=html
        TEST_EXIT_CODE=$?
        echo -e "\n${GREEN}✓ Coverage report generated in htmlcov/index.html${NC}"
        ;;
    
    kelly)
        echo -e "${GREEN}Running Kelly Criterion tests...${NC}\n"
        pytest -v tests/test_kelly_criterion.py
        TEST_EXIT_CODE=$?
        ;;
    
    scanner)
        echo -e "${GREEN}Running EV Scanner tests...${NC}\n"
        pytest -v tests/test_positive_ev_scanner.py
        TEST_EXIT_CODE=$?
        ;;
    
    accuracy)
        echo -e "${GREEN}Running EV Calculation Accuracy tests...${NC}\n"
        pytest -v tests/test_ev_calculation_accuracy.py
        TEST_EXIT_CODE=$?
        ;;
    
    logger)
        echo -e "${GREEN}Running Bet Logger tests...${NC}\n"
        pytest -v tests/test_bet_logger.py
        TEST_EXIT_CODE=$?
        ;;
    
    backtest)
        echo -e "${GREEN}Running Backtest tests...${NC}\n"
        pytest -v tests/test_backtest.py
        TEST_EXIT_CODE=$?
        ;;
    
    action)
        echo -e "${GREEN}Running Action Logger tests...${NC}\n"
        pytest -v tests/test_action_logger.py
        TEST_EXIT_CODE=$?
        ;;
    
    auto)
        echo -e "${GREEN}Running Auto Bet Placer tests...${NC}\n"
        pytest -v tests/test_auto_bet_placer.py
        TEST_EXIT_CODE=$?
        ;;
    
    manage)
        echo -e "${GREEN}Running Manage Bets tests...${NC}\n"
        pytest -v tests/test_manage_bets.py
        TEST_EXIT_CODE=$?
        ;;
    
    verbose)
        echo -e "${GREEN}Running all tests with verbose output...${NC}\n"
        pytest -vv -s
        TEST_EXIT_CODE=$?
        ;;
    
    debug)
        echo -e "${GREEN}Running tests in debug mode (drops to debugger on failure)...${NC}\n"
        pytest -vv --pdb
        TEST_EXIT_CODE=$?
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
        echo "  accuracy   - Run EV Calculation Accuracy tests only"
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
        TEST_EXIT_CODE=0
        ;;
    
    *)
        echo -e "${YELLOW}Unknown option: $TEST_TYPE${NC}"
        echo "Run './run_tests.sh help' for usage information"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}================================${NC}"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${YELLOW}⚠ Some tests failed (exit code: $TEST_EXIT_CODE)${NC}"
    echo -e "${YELLOW}See output above for details${NC}"
fi
echo -e "${BLUE}================================${NC}"

# Exit with the pytest exit code so CI/CD tools can detect failures
exit $TEST_EXIT_CODE
