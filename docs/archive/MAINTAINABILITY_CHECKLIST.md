# Maintainability Checklist & Risk Mitigation

## Pre-Implementation Checklist

### 1. Code Understanding
- [ ] Document all current integration points
- [ ] List all scripts that import these modules
- [ ] Identify critical paths that cannot break
- [ ] Map all external dependencies

### 2. Testing Infrastructure
- [ ] Ensure all tests are currently passing
- [ ] Create performance benchmarks for comparison
- [ ] Set up continuous integration if not present
- [ ] Create integration test suite for external scripts

## Risk Mitigation Strategies

### High-Risk Areas

#### 1. **External Script Dependencies**
**Risk**: Other scripts break when imports change
**Mitigation**:
```python
# Create import_test.py to verify all imports work
import subprocess
import sys

scripts_to_test = [
    'orchestrator',
    'send-claude-message.sh',
    'schedule_with_note.sh',
    'start_claude.sh'
]

for script in scripts_to_test:
    result = subprocess.run([script, '--help'], capture_output=True)
    print(f"{script}: {'✓' if result.returncode == 0 else '✗'}")
```

#### 2. **State Management Changes**
**Risk**: Simplified classes might handle state differently
**Mitigation**:
- Add state validation tests
- Use property decorators to maintain interface
- Log all state changes during transition

#### 3. **Concurrent Access**
**Risk**: Simplified code might not handle concurrency
**Mitigation**:
```python
# Add threading tests
import threading
import time

def test_concurrent_access():
    monitor = ClaudeMonitor()
    results = []
    
    def access_monitor():
        agents = monitor.find_all_agents()
        results.append(len(agents))
    
    threads = [threading.Thread(target=access_monitor) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(set(results)) == 1  # All threads see same state
```

## Maintainability Patterns

### 1. **Clear Module Structure**
```
tmux-orchestrator/
├── core/
│   ├── __init__.py
│   ├── claude_monitor.py    # Main monitoring logic
│   ├── tmux_client.py       # Tmux interactions
│   └── constants.py         # Shared constants
├── utils/
│   ├── formatting.py        # Display utilities
│   └── persistence.py       # Save/load functions
├── orchestrator             # Main CLI
└── tests/
    ├── unit/               # Unit tests
    ├── integration/        # Integration tests
    └── compatibility/      # Backward compatibility tests
```

### 2. **Documentation Standards**
Every class and function must have:
```python
def find_all_agents(self) -> List[Dict[str, Any]]:
    """Find all Claude agents across tmux sessions.
    
    Returns:
        List of dicts with keys: session, window, name, status, process
        
    Raises:
        subprocess.CalledProcessError: If tmux command fails
        
    Example:
        >>> monitor = ClaudeMonitor()
        >>> agents = monitor.find_all_agents()
        >>> print(f"Found {len(agents)} agents")
    """
```

### 3. **Error Handling Pattern**
```python
class TmuxError(Exception):
    """Base exception for tmux operations"""
    pass

class TmuxClient:
    def get_sessions(self) -> List[Dict]:
        try:
            result = self.run_command(["tmux", "list-sessions"])
            return self._parse_sessions(result.stdout)
        except subprocess.CalledProcessError as e:
            if "no server running" in str(e):
                return []  # Empty list is valid when no tmux
            raise TmuxError(f"Failed to list sessions: {e}")
```

### 4. **Configuration Pattern**
```python
# config.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class OrchestratorConfig:
    """Central configuration"""
    coding_dir: Path = Path.home() / "IdeaProjects"
    registry_dir: Path = Path("./registry")
    claude_startup_delay: float = 5.0
    max_capture_lines: int = 1000
    
    @classmethod
    def from_env(cls):
        """Load from environment variables"""
        import os
        return cls(
            coding_dir=Path(os.getenv('CODING_DIR', cls.coding_dir)),
            # ... etc
        )
```

## Post-Implementation Verification

### 1. **Performance Metrics**
```bash
# Before and after comparison
time python3 -c "from claude_control import ClaudeOrchestrator; o = ClaudeOrchestrator(); o.status()"

# Memory usage
/usr/bin/time -l python3 -c "..."
```

### 2. **Complexity Metrics**
```bash
# Install radon for complexity analysis
pip install radon

# Measure cyclomatic complexity
radon cc *.py -a

# Measure maintainability index
radon mi *.py

# Before: MI ~65 (concerning)
# Target: MI >80 (good)
```

### 3. **Developer Experience Test**
Create `developer_test.md`:
```markdown
## New Developer Onboarding Test

Task: Add a new feature to filter agents by status

Time yourself completing these steps:
1. [ ] Understand the codebase structure (target: <10 min)
2. [ ] Find where to add the feature (target: <5 min)
3. [ ] Implement the feature (target: <30 min)
4. [ ] Add tests (target: <20 min)
5. [ ] Verify nothing broke (target: <10 min)

Total target: <75 minutes
```

## Long-term Maintenance Guidelines

### 1. **Prevent Re-complication**
- Code review checklist:
  - [ ] New class has >3 methods?
  - [ ] Single responsibility clear?
  - [ ] Could this be a function instead?
  - [ ] Abstraction adds clear value?

### 2. **Regular Health Checks**
Monthly maintenance tasks:
```bash
# Complexity check
./check_complexity.sh

# Unused code check
vulture *.py

# Dependency check
pip list --outdated

# Test coverage
pytest --cov=. --cov-report=html
```

### 3. **Documentation Maintenance**
- Update examples when APIs change
- Keep README.md current
- Document design decisions in ADR (Architecture Decision Records)

## Emergency Procedures

### If Simplification Goes Wrong

1. **Immediate Rollback**
```bash
git checkout pre-simplification-$(date +%Y%m%d)
```

2. **Partial Rollback**
```bash
# Only revert specific module
git checkout main -- claude_control.py
git checkout feature/simplification -- tmux_utils.py
```

3. **Feature Flag Approach**
```python
# In __init__.py
import os

if os.getenv('USE_SIMPLIFIED', 'false').lower() == 'true':
    from .claude_monitor import ClaudeMonitor
else:
    from .claude_control_refactored import ClaudeOrchestrator as ClaudeMonitor
```

## Success Metrics Dashboard

Create `metrics_dashboard.py`:
```python
def generate_dashboard():
    """Generate maintainability dashboard"""
    
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'code_metrics': {
            'total_classes': count_classes(),
            'avg_methods_per_class': avg_methods(),
            'total_loc': total_lines(),
            'avg_function_length': avg_function_lines()
        },
        'test_metrics': {
            'total_tests': count_tests(),
            'coverage_percent': get_coverage(),
            'avg_test_setup_lines': avg_test_setup(),
            'mock_complexity': mock_count_average()
        },
        'quality_metrics': {
            'cyclomatic_complexity': get_cc_average(),
            'maintainability_index': get_mi_score(),
            'technical_debt_ratio': calc_debt_ratio()
        }
    }
    
    # Generate visual dashboard
    create_dashboard_html(metrics)
    
    # Check against thresholds
    check_metric_thresholds(metrics)
```

## Final Verification Checklist

Before declaring simplification complete:

- [ ] All tests pass with ≥95% coverage
- [ ] All integration scripts work unchanged
- [ ] Performance is same or better
- [ ] New developer onboarding <30 minutes
- [ ] No class has >7 methods
- [ ] No function has >30 lines
- [ ] Cyclomatic complexity <10 for all functions
- [ ] Clear documentation for all public APIs
- [ ] Rollback procedure tested
- [ ] Metrics dashboard shows improvement