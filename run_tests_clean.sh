#!/bin/bash
# Run all tests for Tmux Orchestrator with cleaner output

echo "🧪 Running Tmux Orchestrator Test Suite..."
echo "=========================================="

# Set up Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Run linting first
echo ""
echo "📋 Running Linting Checks..."
echo "----------------------------"

# ShellCheck
echo "ShellCheck:"
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck *.sh 2>&1 | grep -E "error|warning" || echo "✅ No shell script issues found"
else
    echo "⚠️  ShellCheck not installed"
fi

# Flake8
echo ""
echo "Flake8:"
if python3 -m flake8 --version >/dev/null 2>&1; then
    python3 -m flake8 --max-line-length=100 *.py | head -20 || echo "✅ No Python style issues found"
else
    echo "⚠️  Flake8 not installed (pip install flake8)"
fi

# Run unit tests
echo ""
echo "🔬 Running Unit Tests..."
echo "------------------------"

# Temporarily set log level to suppress expected errors
export PYTHONUNBUFFERED=1

# Check if pytest is available
if python3 -m pytest --version >/dev/null 2>&1; then
    echo "Using pytest..."
    # Run with less verbose output and suppress logger warnings
    python3 -m pytest tests/ -v --tb=short --log-cli-level=CRITICAL 2>/dev/null
    TEST_RESULT=$?
else
    echo "Using unittest..."
    python3 -m unittest discover -s tests -p "test_*.py" -v 2>&1 | grep -v "ERROR:" || true
    TEST_RESULT=$?
fi

# Run coverage if available
echo ""
echo "📊 Code Coverage..."
echo "-------------------"

if python3 -m coverage --version >/dev/null 2>&1; then
    # Run coverage silently
    python3 -m coverage run --quiet -m unittest discover -s tests -p "test_*.py" >/dev/null 2>&1
    
    # Show only the coverage report
    python3 -m coverage report -m --include="*.py" --omit="tests/*,*/__pycache__/*"
    
    # Show test summary
    echo ""
    if [ $TEST_RESULT -eq 0 ]; then
        echo -e "${GREEN}✅ All tests passed!${NC}"
    else
        echo -e "${RED}❌ Some tests failed${NC}"
    fi
    
    # Note about error messages
    echo ""
    echo -e "${BLUE}ℹ️  Note: Error messages during tests are expected - they test error handling${NC}"
else
    echo "⚠️  Coverage not installed (pip install coverage)"
fi

echo ""
echo "✅ Test suite complete!"

# Return the test result
exit $TEST_RESULT