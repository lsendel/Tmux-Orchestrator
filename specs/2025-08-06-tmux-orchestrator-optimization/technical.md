# Technical Specification: Tmux Orchestrator Performance Optimization

## Architecture Details

### System Design

The optimization introduces a three-layer architecture that separates concerns while maintaining high cohesion:

```
┌─────────────────────────────────────────────────┐
│           User Interface Layer                   │
│         (orchestrator shell script)              │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────┐
│           Application Layer                      │
│  ┌──────────────┐        ┌──────────────┐      │
│  │claude_control│        │ tmux_utils   │      │
│  │     .py      │        │     .py      │      │
│  └──────┬───────┘        └──────┬───────┘      │
└─────────┴───────────────────────┴───────────────┘
                      │
┌─────────────────────┴───────────────────────────┐
│              Core Layer                          │
│            (tmux_core.py)                        │
│  ┌────────────────────────────────────────┐     │
│  │ TmuxCommand (Base Class)               │     │
│  ├────────────────────────────────────────┤     │
│  │ BatchOperations                        │     │
│  ├────────────────────────────────────────┤     │
│  │ TmuxPatterns | TmuxValidation          │     │
│  └────────────────────────────────────────┘     │
└──────────────────────────────────────────────────┘
```

### Data Flow

#### Status Check Flow (Optimized)
1. User executes `./orchestrator status`
2. Shell script calls `python3 claude_control.py`
3. claude_control.py inherits from TmuxCommand
4. Calls `batch_get_all_sessions_and_windows()`
5. Executes 2 tmux commands total:
   - `tmux list-sessions -F "#{session_name}|#{session_windows}|..."`
   - `tmux list-windows -a -F "#{session_name}|#{window_index}|..."`
6. Parses and combines results
7. Returns formatted output or JSON

#### Individual Command Flow (Unchanged)
1. User executes specific command
2. Application layer receives request
3. Validates input using TmuxValidation
4. Executes via TmuxCommand.execute_command()
5. Returns processed result

### Class Hierarchy

```python
# Core Layer
class TmuxCommand:
    """Base class for all tmux operations"""
    - execute_command()
    - parse_format_output()
    - handle_error()

class BatchOperations(TmuxCommand):
    """Optimized batch data retrieval"""
    - batch_get_all_sessions_and_windows()
    - batch_capture_panes()
    - batch_get_processes()

# Application Layer
class ClaudeControl(BatchOperations):
    """Claude agent management"""
    - get_agent_status()
    - monitor_activity()
    - send_message()

class TmuxUtils(TmuxCommand):
    """General tmux utilities"""
    - create_session()
    - rename_window()
    - kill_session()
```

### Optimization Techniques

#### 1. Batch Command Execution
```python
def batch_get_all_sessions_and_windows(self):
    # Single command to get all sessions
    sessions_cmd = ['tmux', 'list-sessions', '-F', 
                   '#{session_name}|#{session_windows}|#{session_created}|#{session_attached}']
    
    # Single command to get all windows
    windows_cmd = ['tmux', 'list-windows', '-a', '-F',
                  '#{session_name}|#{window_index}|#{window_name}|#{window_active}|#{window_panes}']
    
    # Execute both and combine results
    sessions = self.execute_command(sessions_cmd)
    windows = self.execute_command(windows_cmd)
    
    return self._combine_results(sessions, windows)
```

#### 2. Caching Strategy
```python
class CachedData:
    """Short-lived cache for repeated operations"""
    def __init__(self, ttl=1.0):  # 1 second TTL
        self.cache = {}
        self.timestamps = {}
    
    def get_or_fetch(self, key, fetcher):
        if self._is_valid(key):
            return self.cache[key]
        result = fetcher()
        self.cache[key] = result
        self.timestamps[key] = time.time()
        return result
```

#### 3. Lazy Evaluation
```python
@property
def window_type(self):
    """Detect window type only when accessed"""
    if not self._window_type:
        self._window_type = TmuxPatterns.detect_window_type(
            self.name, self.current_command
        )
    return self._window_type
```

### Security Considerations

#### Input Validation
- All session/window names validated against injection patterns
- Command arguments escaped using shlex.quote()
- No direct shell execution (shell=False in subprocess)

#### Process Isolation
- Each tmux operation runs in separate subprocess
- No persistent shell sessions
- Limited command whitelist

#### Error Handling
```python
def execute_command(cmd, check=True):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return result
    except subprocess.CalledProcessError as e:
        if "no server running" in e.stderr:
            raise TmuxServerNotRunning()
        elif "session not found" in e.stderr:
            raise SessionNotFound()
        else:
            raise TmuxCommandError(e.stderr)
```

### Performance Requirements

#### Response Time Targets
- Status command: < 100ms for 10 sessions
- Activity check: < 50ms per window
- Batch operations: < 200ms for 50 windows
- JSON serialization: < 10ms

#### Scalability Limits
- Maximum sessions: 100 (tmux limit)
- Maximum windows per session: 100
- Maximum concurrent operations: 10
- Cache TTL: 1 second

#### Memory Usage
- Base memory: ~10MB
- Per session overhead: ~100KB
- Per window overhead: ~50KB
- Maximum memory: ~50MB for full system

### Testing Strategy

#### Unit Tests
```python
# Test core functionality
test_tmux_core.py:
- Test TmuxCommand base class
- Test BatchOperations efficiency
- Test pattern detection accuracy
- Test validation rules

# Test application layer
test_claude_control_optimized.py:
- Test agent status detection
- Test message sending
- Test JSON output format
```

#### Integration Tests
```python
# Test backward compatibility
test_claude_control_compat.py:
- Verify all CLI commands work
- Check output format unchanged
- Test error messages

# Test performance
test_performance.py:
- Benchmark batch operations
- Measure subprocess call reduction
- Profile memory usage
```

#### Performance Tests
```python
def test_batch_performance():
    # Create test sessions
    setup_test_sessions(count=10, windows_per=5)
    
    # Measure old approach
    start = time.time()
    old_get_all_data()
    old_time = time.time() - start
    
    # Measure new approach
    start = time.time()
    batch_get_all_sessions_and_windows()
    new_time = time.time() - start
    
    # Assert improvement
    assert new_time < old_time * 0.2  # 80% improvement
```

### Monitoring & Observability

#### Performance Metrics
```python
# Log performance data
logger.info(f"Batch operation completed: {elapsed_ms}ms for {session_count} sessions")

# Track subprocess calls
SUBPROCESS_COUNTER.increment()

# Monitor cache hits
CACHE_HIT_RATE.record(hits / total_requests)
```

#### Error Tracking
```python
# Structured error logging
logger.error("Tmux command failed", extra={
    'command': cmd,
    'exit_code': e.returncode,
    'stderr': e.stderr,
    'session': session_name
})
```

### API Documentation

#### Core Module API

```python
class TmuxCommand:
    def execute_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute a tmux command safely"""
        
    def parse_format_output(output: str, delimiter: str = '|') -> List[Dict[str, str]]:
        """Parse tmux format string output"""

class BatchOperations(TmuxCommand):
    def batch_get_all_sessions_and_windows() -> Dict[str, List[WindowInfo]]:
        """Get all sessions and windows in 2 subprocess calls"""
        
    def batch_capture_panes(targets: List[Tuple[str, int]]) -> Dict[str, str]:
        """Capture multiple panes efficiently"""

class TmuxPatterns:
    @classmethod
    def detect_window_type(window_name: str, process: str = "") -> str:
        """Detect the type of a tmux window"""
        
    @classmethod
    def is_claude_process(process: str) -> bool:
        """Check if a process is a Claude agent"""
```

### Migration Path

#### For Existing Scripts
1. No changes required - CLI interface unchanged
2. Optional: Use JSON output for better parsing
3. Optional: Leverage batch operations for custom scripts

#### For Future Development
1. Inherit from appropriate base class
2. Use TmuxPatterns for detection logic
3. Implement batch operations where possible
4. Add comprehensive tests