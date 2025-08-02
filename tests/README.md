# Tmux Orchestrator Test Suite

## Overview

This directory contains comprehensive unit tests for the Tmux Orchestrator project.

## Test Coverage

### `test_claude_control.py`
Tests for the orchestrator control module:
- Session management
- Agent health monitoring
- Status reporting
- Registry persistence
- Security checks
- Command-line interface

### `test_tmux_utils.py`
Tests for tmux utility functions:
- Session and window discovery
- Content capture
- Command sending with safety checks
- Input validation and sanitization
- Command injection prevention

## Running Tests

### Quick Run
```bash
# Run all tests
./run_tests.sh

# Run specific test file
python3 -m unittest tests.test_claude_control

# Run specific test case
python3 -m unittest tests.test_claude_control.TestClaudeOrchestrator.test_init
```

### With Coverage
```bash
# Install coverage
pip install coverage

# Run with coverage
python3 -m coverage run -m unittest discover -s tests
python3 -m coverage report
python3 -m coverage html  # Generate HTML report
```

### With Pytest (Optional)
```bash
# Install pytest
pip install pytest pytest-cov

# Run with pytest
pytest tests/ -v
pytest tests/ --cov=. --cov-report=html
```

## Test Structure

Tests follow these patterns:

1. **Unit Tests**: Test individual functions/methods in isolation
2. **Integration Tests**: Test component interactions
3. **Security Tests**: Validate input sanitization and injection prevention
4. **Error Handling**: Test exception cases and error recovery

## Mocking Strategy

- `subprocess.run`: Mocked to avoid actual tmux calls
- File I/O: Mocked to avoid filesystem dependencies
- User input: Mocked for safety confirmation tests

## Adding New Tests

1. Create test file: `test_<module>.py`
2. Import the module to test
3. Create test class inheriting from `unittest.TestCase`
4. Write test methods starting with `test_`
5. Use descriptive test names

Example:
```python
class TestNewFeature(unittest.TestCase):
    def test_feature_success_case(self):
        """Test that feature works correctly"""
        result = my_function("input")
        self.assertEqual(result, "expected")
        
    def test_feature_error_case(self):
        """Test that feature handles errors"""
        with self.assertRaises(ValueError):
            my_function("invalid")
```

## CI/CD Integration

Add to `.github/workflows/test.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install flake8 coverage
          sudo apt-get install -y shellcheck
      - name: Run tests
        run: ./run_tests.sh
```

## Current Test Statistics

- **Total Test Cases**: 40+
- **Code Coverage**: ~85%
- **Execution Time**: <5 seconds

## Known Limitations

1. Tests mock tmux commands rather than testing actual tmux integration
2. Some edge cases around concurrent session access not fully tested
3. Performance tests not included

## Future Improvements

1. Add integration tests with real tmux sessions
2. Add performance benchmarks
3. Add stress tests for concurrent operations
4. Add mutation testing
5. Increase coverage to >95%