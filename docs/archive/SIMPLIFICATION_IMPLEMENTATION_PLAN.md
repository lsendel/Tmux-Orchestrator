# Simplification Implementation Plan

## Overview
This plan ensures we simplify the over-engineered code while maintaining:
- ✅ 97% test coverage
- ✅ All existing integrations
- ✅ Backward compatibility
- ✅ Improved maintainability

## Guiding Principles

1. **Incremental Changes**: Each phase is independently deployable
2. **Test-First Migration**: Update tests before changing implementation
3. **Compatibility Layer**: Maintain old interfaces during transition
4. **Measure Progress**: Track maintainability metrics throughout

## Maintainability Metrics

### Before Simplification
- **Cognitive Complexity**: High (10 classes to understand per module)
- **File Navigation**: 20+ class definitions across files
- **Onboarding Time**: ~2-3 hours to understand architecture
- **Change Impact**: Modifying one feature touches 3-5 classes
- **Mock Complexity**: Tests require 5+ mocks per test

### Target After Simplification
- **Cognitive Complexity**: Low (3-4 classes per module)
- **File Navigation**: 5 main classes total
- **Onboarding Time**: ~30 minutes
- **Change Impact**: 1-2 classes per feature
- **Mock Complexity**: 1-2 mocks per test

## Phase 0: Preparation (2 hours)

### 1. Create Safety Net
```bash
# Create a full backup with tests
git checkout -b simplification-backup
git add -A
git commit -m "Backup: Before simplification"
git tag pre-simplification-$(date +%Y%m%d)

# Create compatibility branch
git checkout -b feature/simplification
```

### 2. Set Up Compatibility Module
Create `compat.py` to maintain backward compatibility:

```python
# compat.py - Temporary compatibility layer
"""
Compatibility layer for gradual migration.
This file will be deleted after full migration.
"""

# Old imports will redirect here temporarily
```

### 3. Create Migration Tests
```python
# tests/test_compatibility.py
class TestBackwardCompatibility(unittest.TestCase):
    """Ensure old interfaces still work during migration"""
    
    def test_old_imports_work(self):
        # Test that old class names can still be imported
        from claude_control_refactored import ClaudeOrchestrator
        self.assertIsNotNone(ClaudeOrchestrator)
```

## Phase 1: Internal Consolidation (3 hours)

### Step 1.1: Merge Static Utility Classes

**File: claude_control_simplified.py**
```python
# Start with a new file to avoid breaking existing code
class TmuxClient:
    """Consolidated tmux operations (was TmuxCommandExecutor)"""
    
    @staticmethod
    def run_command(command: List[str]) -> subprocess.CompletedProcess:
        """From TmuxCommandExecutor.run_command"""
        try:
            return subprocess.run(command, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            raise
    
    @classmethod
    def get_sessions(cls) -> List[Dict[str, Any]]:
        """Simplified from TmuxCommandExecutor.get_sessions"""
        try:
            result = cls.run_command(["tmux", "list-sessions", "-F", 
                                     "#{session_name}:#{session_created}:#{session_windows}"])
            sessions = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        sessions.append({
                            'name': parts[0],
                            'created': parts[1],
                            'windows': int(parts[2])
                        })
            return sessions
        except subprocess.CalledProcessError:
            return []
```

### Step 1.2: Replace Enums with Constants
```python
# claude_control_simplified.py
# Simple constants instead of enums
class AgentStatus:
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    UNKNOWN = "unknown"
```

### Step 1.3: Convert Single-Method Classes to Functions
```python
# Instead of StatusFormatter class
def format_status(sessions: List[Dict], detailed: bool = False) -> None:
    """Direct formatting function"""
    if not sessions:
        print("\033[1;33mNo active sessions found\033[0m")
        return
    
    print("\n\033[0;34m🎯 Tmux Orchestrator Status\033[0m")
    print("=" * 50)
    # ... rest of formatting logic

# Instead of RegistryManager class  
def save_registry(sessions: List[Dict], registry_path: Path) -> None:
    """Save sessions to JSON file"""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "updated": datetime.now().isoformat(),
        "sessions": sessions
    }
    with open(registry_path, 'w') as f:
        json.dump(data, f, indent=2)
```

## Phase 2: Core Consolidation (4 hours)

### Step 2.1: Create Simplified Main Classes

**claude_control_simplified.py**
```python
class ClaudeMonitor:
    """Simplified monitoring of Claude agents"""
    
    def __init__(self):
        self.tmux = TmuxClient()
        self.health_indicators = {
            'ready': ["Human:", "> ", "Ready", "I'll help", "I can help"],
            'error': ["Error:", "error:", "ERROR", "Failed", "failed"],
            'busy': ["Processing", "Working on", "Let me", "I'm currently", "..."]
        }
    
    def find_all_agents(self) -> List[Dict[str, Any]]:
        """Find all Claude agents across sessions"""
        all_agents = []
        
        for session in self.tmux.get_sessions():
            windows = self.tmux.get_windows(session['name'])
            
            for window in windows:
                if self._is_claude_window(window):
                    output = self.tmux.capture_pane(session['name'], window['index'])
                    all_agents.append({
                        'session': session['name'],
                        'window': window['index'],
                        'name': window['name'],
                        'status': self._check_health(output),
                        'process': window.get('command', '')
                    })
        
        return all_agents
    
    def _is_claude_window(self, window: Dict) -> bool:
        """Check if window contains Claude"""
        indicators = ["claude", "Claude", "node"]
        combined = f"{window.get('name', '')} {window.get('command', '')}"
        return any(ind in combined for ind in indicators)
```

### Step 2.2: Create Compatibility Layer
```python
# In compat.py
from claude_control_simplified import TmuxClient, ClaudeMonitor, AgentStatus

# Map old names to new implementations
class TmuxCommandExecutor:
    """Compatibility wrapper"""
    run_command = TmuxClient.run_command
    get_sessions = TmuxClient.get_sessions
    get_windows = TmuxClient.get_windows
    capture_pane = TmuxClient.capture_pane

# Add to claude_control_refactored.py temporarily
try:
    from compat import *  # During migration
except ImportError:
    pass  # After migration complete
```

## Phase 3: Test Migration Strategy (4 hours)

### Step 3.1: Create Test Adapters
```python
# tests/test_claude_control_simplified.py
import unittest
from unittest.mock import patch, MagicMock

# Import both old and new for comparison
from claude_control_simplified import ClaudeMonitor, TmuxClient

class TestSimplifiedImplementation(unittest.TestCase):
    """Test the simplified implementation maintains same behavior"""
    
    def setUp(self):
        self.monitor = ClaudeMonitor()
    
    @patch('subprocess.run')
    def test_find_agents_same_behavior(self, mock_run):
        """Ensure simplified version produces same results"""
        # Use same test data as original tests
        mock_run.side_effect = [
            MagicMock(stdout="session1:123:2\n", returncode=0),
            MagicMock(stdout="0:Claude:node\n1:Shell:bash\n", returncode=0),
            MagicMock(stdout="> Ready", returncode=0)
        ]
        
        agents = self.monitor.find_all_agents()
        
        # Same assertions as original
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]['status'], 'ready')
```

### Step 3.2: Parallel Testing Approach
```python
# tests/test_migration_parity.py
class TestMigrationParity(unittest.TestCase):
    """Ensure old and new implementations produce identical results"""
    
    @patch('subprocess.run')
    def test_parity_find_agents(self, mock_run):
        # Set up identical mocks
        test_data = [
            MagicMock(stdout="session1:123:2\n", returncode=0),
            MagicMock(stdout="0:Claude:node\n", returncode=0),
            MagicMock(stdout="> Ready", returncode=0)
        ]
        
        # Test old implementation
        mock_run.side_effect = test_data.copy()
        old_orchestrator = ClaudeOrchestrator()  # Old
        old_result = old_orchestrator.get_active_sessions()
        
        # Test new implementation  
        mock_run.side_effect = test_data.copy()
        new_monitor = ClaudeMonitor()  # New
        new_result = new_monitor.find_all_agents()
        
        # Compare results (with format adaptation)
        self.assertEqual(len(old_result), len(new_result))
```

## Phase 4: Incremental Rollout (3 hours)

### Step 4.1: Update Integration Points

**orchestrator** (shell script)
```bash
# Add fallback mechanism
if [ -f "$SCRIPT_DIR/claude_control_simplified.py" ]; then
    CLAUDE_CONTROL="claude_control_simplified.py"
else
    CLAUDE_CONTROL="claude_control.py"
fi

# Update commands to use variable
status)
    python3 "$SCRIPT_DIR/$CLAUDE_CONTROL" status "$@"
    ;;
```

### Step 4.2: Update External Scripts
```python
# send-claude-message.sh
# No changes needed - it uses tmux directly

# schedule_with_note.sh  
# No changes needed - it uses 'at' command

# Other integration points
# Check each and update imports if needed
```

## Phase 5: Final Cleanup (2 hours)

### Step 5.1: Remove Old Code
```bash
# After confirming everything works
git rm claude_control_refactored.py
git rm tmux_utils_refactored.py
git rm compat.py

# Rename simplified versions
git mv claude_control_simplified.py claude_control.py
git mv tmux_utils_simplified.py tmux_utils.py
```

### Step 5.2: Update Documentation
- Update docstrings to reflect simplified architecture
- Update README.md with new class structure
- Update CLAUDE.md with simplified examples

## Testing Strategy Throughout

### Continuous Coverage Monitoring
```bash
# Run after each phase
python3 -m pytest tests/ --cov=. --cov-report=term-missing

# Ensure coverage never drops below 95%
# Current: 97%
# Minimum acceptable: 95%
```

### Test Update Pattern
For each consolidated class:
1. Run existing tests to establish baseline
2. Update test imports to use new structure
3. Simplify mock setup
4. Verify same test coverage
5. Remove redundant tests

Example:
```python
# Before: Complex mocking
mock_executor = MagicMock()
mock_validator = MagicMock()  
mock_health = MagicMock()
analyzer = SessionAnalyzer(mock_executor, mock_health)

# After: Simple mocking
mock_tmux = MagicMock()
monitor = ClaudeMonitor()
monitor.tmux = mock_tmux
```

## Rollback Plan

If issues arise at any phase:
```bash
# Quick rollback
git checkout pre-simplification-$(date +%Y%m%d)

# Or selective rollback
git checkout HEAD~1 claude_control.py
```

## Success Criteria

### Maintainability Metrics (Measurable)
- [ ] Reduce classes from 20 to ≤6
- [ ] Reduce total LOC by ≥40%
- [ ] Reduce average mock count per test by ≥50%
- [ ] Maintain test coverage ≥95%
- [ ] All integration tests pass

### Code Quality Metrics
- [ ] Cyclomatic complexity ≤10 per function
- [ ] No class with >7 methods
- [ ] No function >30 lines
- [ ] Clear single responsibility per class

### Developer Experience
- [ ] New developer can understand structure in <30 min
- [ ] Any feature change touches ≤2 classes
- [ ] Tests are readable without extensive setup

## Phase Timeline

| Phase | Duration | Risk | Rollback Time |
|-------|----------|------|---------------|
| 0: Preparation | 2 hours | None | N/A |
| 1: Internal Consolidation | 3 hours | Low | 5 min |
| 2: Core Consolidation | 4 hours | Medium | 15 min |
| 3: Test Migration | 4 hours | Low | 10 min |
| 4: Incremental Rollout | 3 hours | Medium | 20 min |
| 5: Final Cleanup | 2 hours | Low | 30 min |

**Total: 18 hours** (can be done over 3-4 days)

## Monitoring During Implementation

Create `simplification_metrics.py`:
```python
def measure_complexity():
    """Track metrics during simplification"""
    metrics = {
        'classes': count_classes(),
        'average_methods_per_class': calc_methods(),
        'total_loc': count_lines(),
        'test_mock_complexity': analyze_test_mocks(),
        'coverage': get_coverage_percent()
    }
    
    with open('simplification_progress.json', 'a') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics
        }, f)
        f.write('\n')
```

Run after each phase to ensure we're improving, not just changing.