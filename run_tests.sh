#!/bin/bash
# Run all tests for Tmux Orchestrator

echo "🧪 Running Tmux Orchestrator Test Suite..."
echo "=========================================="

# Set up Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

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

# Check if pytest is available
if python3 -m pytest --version >/dev/null 2>&1; then
    echo "Using pytest..."
    python3 -m pytest tests/ -v --tb=short
else
    echo "Using unittest..."
    python3 -m unittest discover -s tests -p "test_*.py" -v
fi

# Run coverage if available
echo ""
echo "📊 Code Coverage..."
echo "-------------------"

if python3 -m coverage --version >/dev/null 2>&1; then
    python3 -m coverage run -m unittest discover -s tests -p "test_*.py"
    python3 -m coverage report -m --include="*.py" --omit="tests/*,*/__pycache__/*"
else
    echo "⚠️  Coverage not installed (pip install coverage)"
fi

echo ""
echo "✅ Test suite complete!"