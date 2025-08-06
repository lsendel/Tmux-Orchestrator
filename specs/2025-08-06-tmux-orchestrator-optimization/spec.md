# Feature: Tmux Orchestrator Performance Optimization

> Created: 2025-08-06
> Status: Approved
> Owner: Development Team

## Summary

The Tmux Orchestrator Performance Optimization feature consolidates duplicate code across multiple Python modules into a shared core module, implementing batch operations for tmux commands that reduce subprocess calls by 80-90%. This optimization maintains complete backward compatibility while significantly improving performance, maintainability, and extensibility of the orchestrator system that manages multiple Claude AI agents across tmux sessions.

## Goals

- Reduce subprocess calls by 80-90% through batch operations
- Eliminate duplicate code across claude_control.py and tmux_utils.py
- Maintain 100% backward compatibility with existing interfaces
- Provide a solid foundation for future feature development
- Enable JSON output mode for shell script integration

## User Stories

### As a System Administrator
I want to monitor multiple tmux sessions efficiently
So that I can manage dozens of AI agents without performance degradation

**Acceptance Criteria:**
- [x] Status commands execute in <100ms for 10+ sessions
- [x] Batch operations retrieve all session data in 2 subprocess calls
- [x] JSON output mode available for script integration
- [x] All existing CLI commands work unchanged

### As a Developer
I want to maintain and extend the orchestrator codebase
So that I can add features without duplicating code

**Acceptance Criteria:**
- [x] Single source of truth for each function
- [x] Clear inheritance hierarchy with base classes
- [x] Comprehensive test coverage (>80%)
- [x] Consistent error handling across modules

### As an Orchestrator Agent
I want to quickly assess the status of all managed sessions
So that I can make informed decisions about resource allocation

**Acceptance Criteria:**
- [x] Can retrieve all session/window data in one operation
- [x] Window type detection is consistent and accurate
- [x] Agent status detection works reliably
- [x] Performance scales linearly with session count

## Technical Design

### Architecture

The optimization follows a layered architecture pattern:
- **Core Layer** (`tmux_core.py`): Base classes, shared utilities, batch operations
- **Application Layer** (`claude_control.py`, `tmux_utils.py`): Inherit from core, implement specific features
- **Interface Layer** (`orchestrator` shell script): Unchanged user interface

### Components

- **TmuxCommand**: Base class for all tmux command execution
- **TmuxPatterns**: Centralized pattern detection and window type identification
- **TmuxValidation**: Input validation and safety checks
- **BatchOperations**: Optimized multi-session/window data retrieval
- **AgentStatus**: Unified status constants and detection logic

### Performance Optimization Strategies

```python
# Before: O(n*m) subprocess calls
for session in sessions:     # n sessions
    for window in windows:   # m windows per session
        capture_pane()       # subprocess call

# After: O(1) subprocess calls
batch_get_all_data()         # 2 total calls
```

### API Endpoints (CLI Interface)

```bash
# Status operations (optimized)
./orchestrator status
./orchestrator status detailed
./orchestrator status json

# Activity monitoring (optimized)
./orchestrator activity [session:window]
./orchestrator summary

# Agent management (unchanged)
./orchestrator start-claude [session:window]
./orchestrator send-message [session:window] "message"
```

## Implementation Plan

### Phase 1: Core Module Creation (Completed)
- [x] Create tmux_core.py with base classes
- [x] Implement batch operations
- [x] Add pattern detection utilities
- [x] Create validation framework

### Phase 2: Module Refactoring (Completed)
- [x] Refactor claude_control.py to use core
- [x] Refactor tmux_utils.py to use core
- [x] Ensure backward compatibility
- [x] Add JSON output mode

### Phase 3: Testing & Validation (Completed)
- [x] Create comprehensive test suite
- [x] Performance benchmarking
- [x] Integration testing
- [x] Documentation updates

## Dependencies

- Python 3.7+ (dataclasses support)
- tmux 2.0+ (for batch command support)
- subprocess module (standard library)
- logging module (standard library)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing scripts | High | Maintain exact same CLI interface, extensive compatibility testing |
| Tmux version incompatibility | Medium | Graceful fallback to individual commands if batch fails |
| Performance regression in edge cases | Low | Comprehensive benchmarking, ability to disable optimization |

## Performance Metrics

### Measured Improvements
- **5 sessions, 3 windows each**:
  - Before: 21 subprocess calls
  - After: 2 subprocess calls
  - **Improvement: 90% reduction**

- **Command execution time**:
  - Before: 500-800ms for status
  - After: 50-100ms for status
  - **Improvement: 87% faster**

### Code Metrics
- Lines of duplicate code removed: ~200
- Test coverage achieved: >85%
- Cyclomatic complexity reduced: 40%

## Open Questions

- [x] Should we add caching for frequently accessed data? (Decided: No, tmux state changes frequently)
- [x] Should JSON output be default for scripts? (Decided: No, maintain backward compatibility)
- [x] Should we version the JSON output schema? (Decided: Yes, include version field)