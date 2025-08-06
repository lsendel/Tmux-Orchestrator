# Architectural Decision Records: Tmux Orchestrator Optimization

## Decision 1: Shared Core Module Architecture
**Date**: 2025-08-06
**Status**: Accepted

**Context**: The codebase had significant code duplication between claude_control.py and tmux_utils.py, with identical subprocess execution patterns, error handling, and parsing logic appearing in both modules.

**Decision**: Create a shared core module (tmux_core.py) that consolidates all duplicate code into reusable base classes and utilities.

**Consequences**: 
- Positive: Single source of truth for each function, easier maintenance, consistent behavior
- Negative: Additional layer of abstraction, slightly more complex inheritance hierarchy
- Mitigation: Keep inheritance shallow (max 2 levels), comprehensive documentation

---

## Decision 2: Batch Operations Over Individual Calls
**Date**: 2025-08-06
**Status**: Accepted

**Context**: The original implementation made O(n*m) subprocess calls to gather information about n sessions with m windows each, causing significant performance degradation with multiple sessions.

**Decision**: Implement batch operations that retrieve all session and window data in exactly 2 subprocess calls using tmux's format strings.

**Consequences**:
- Positive: 80-90% reduction in subprocess calls, dramatically improved performance
- Negative: More complex parsing logic, potential for larger memory footprint with many sessions
- Mitigation: Efficient parsing algorithms, memory usage monitoring

---

## Decision 3: Maintain 100% Backward Compatibility
**Date**: 2025-08-06
**Status**: Accepted

**Context**: The orchestrator is used by existing shell scripts and automation tools that depend on specific output formats and command-line interfaces.

**Decision**: Keep all existing CLI commands, output formats, and error messages exactly the same while adding new capabilities (like JSON output) as optional features.

**Consequences**:
- Positive: Zero breaking changes, no migration required for existing users
- Negative: Some legacy patterns must be maintained, can't optimize certain interfaces
- Mitigation: New features added as extensions, deprecation warnings for future changes

---

## Decision 4: JSON Output as Secondary Format
**Date**: 2025-08-06
**Status**: Accepted

**Context**: Shell scripts need to parse orchestrator output, but changing the default format would break existing integrations.

**Decision**: Add JSON output as an optional mode (`--json` flag or `json` command) while keeping human-readable format as default.

**Consequences**:
- Positive: Machine-readable format available, maintains compatibility
- Negative: Must maintain two output formats
- Mitigation: Shared data structures, format converters

---

## Decision 5: Class-Based Inheritance Pattern
**Date**: 2025-08-06
**Status**: Accepted

**Context**: Need to share code between modules while maintaining clear separation of concerns and allowing for future extensions.

**Decision**: Use class-based inheritance with TmuxCommand as the base class, BatchOperations for optimized operations, and application classes inheriting as needed.

**Consequences**:
- Positive: Clear hierarchy, easy to extend, follows SOLID principles
- Negative: More complex than functional approach, requires understanding of inheritance
- Mitigation: Comprehensive documentation, clear naming conventions

---

## Decision 6: No Caching by Default
**Date**: 2025-08-06
**Status**: Accepted

**Context**: Tmux session state changes frequently, and stale data could lead to incorrect decisions by the orchestrator.

**Decision**: Do not implement caching by default. Each command gets fresh data from tmux.

**Consequences**:
- Positive: Always accurate data, no cache invalidation complexity
- Negative: Cannot optimize repeated queries within short time windows
- Mitigation: Batch operations minimize the performance impact, optional caching can be added later

---

## Decision 7: Subprocess Over Tmux Python Libraries
**Date**: 2025-08-06
**Status**: Accepted

**Context**: Several Python libraries exist for tmux interaction (libtmux, tmuxp), but they add dependencies and may not support all tmux features.

**Decision**: Continue using subprocess to execute tmux commands directly, maintaining zero dependencies beyond Python standard library.

**Consequences**:
- Positive: No external dependencies, full tmux feature access, easier debugging
- Negative: More low-level code, manual parsing required
- Mitigation: Robust error handling, comprehensive parsing utilities

---

## Decision 8: Pattern-Based Window Type Detection
**Date**: 2025-08-06
**Status**: Accepted

**Context**: Need to identify different types of windows (Claude agents, dev servers, shells) for appropriate handling and monitoring.

**Decision**: Use pattern matching on window names and running processes with a centralized TmuxPatterns class.

**Consequences**:
- Positive: Flexible detection, easy to extend patterns, works with any naming convention
- Negative: May have false positives, requires maintenance as patterns evolve
- Mitigation: Priority ordering of patterns, regular expression support, configuration options

---

## Decision 9: Comprehensive Test Coverage Requirement
**Date**: 2025-08-06
**Status**: Accepted

**Context**: The orchestrator is a critical system component managing multiple AI agents. Bugs could cause loss of work or system instability.

**Decision**: Require >80% test coverage with unit tests, integration tests, and performance benchmarks.

**Consequences**:
- Positive: High confidence in changes, regression prevention, documented behavior
- Negative: Slower initial development, test maintenance overhead
- Mitigation: Test automation, clear test organization, focus on critical paths

---

## Decision 10: Logging Over Print Statements
**Date**: 2025-08-06
**Status**: Accepted

**Context**: Need visibility into system operations for debugging and monitoring without cluttering normal output.

**Decision**: Use Python's logging module with configurable levels instead of print statements.

**Consequences**:
- Positive: Configurable verbosity, structured logging, better debugging
- Negative: Slightly more complex than print statements
- Mitigation: Clear logging guidelines, sensible defaults

---

## Future Considerations

### Potential Decision: Async/Await Architecture
**Status**: Under Consideration

**Context**: Could further improve performance with concurrent operations.

**Considerations**:
- Would require Python 3.7+ (currently supporting 3.6+)
- Significant refactoring needed
- May complicate debugging

### Potential Decision: WebSocket Monitoring
**Status**: Under Consideration

**Context**: Real-time monitoring without polling would reduce system load.

**Considerations**:
- Would add complexity
- Requires additional infrastructure
- Better suited for web UI integration

### Potential Decision: Plugin Architecture
**Status**: Under Consideration

**Context**: Allow extending orchestrator without modifying core code.

**Considerations**:
- Increases flexibility
- Adds complexity
- Need to define stable plugin API