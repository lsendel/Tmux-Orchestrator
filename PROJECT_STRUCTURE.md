# Tmux Orchestrator Project Structure

## Directory Layout

```
Tmux-Orchestrator/
├── orchestrator              # Main CLI entry point
├── claude_control.py         # Claude agent monitoring and control
├── tmux_utils.py            # Tmux session management utilities
├── schedule_with_note.sh    # Scheduling script for orchestrator checks
├── run_tests.sh             # Test runner script
├── install.sh               # Installation script
├── requirements.txt         # Python dependencies
├── README.md                # Main documentation
├── CLAUDE.md                # Claude-specific project knowledge
├── QUICKSTART.md            # Quick start guide
├── DEPLOYMENT_COMPLETE.md   # Deployment documentation
├── SIMPLIFICATION_PROGRESS.md # Simplification notes
├── PROJECT_STRUCTURE.md     # This file
│
├── scripts/                 # Organized utility scripts
│   ├── utils/              # Core utility scripts
│   │   ├── get_claude_command.sh    # Claude command finder
│   │   ├── load_env.sh             # Environment loader
│   │   ├── send-claude-message.sh  # Message sender
│   │   └── start_claude.sh         # Claude starter
│   └── README.md           # Scripts documentation
│
├── docs/                   # Documentation
│   ├── images/            # Documentation images
│   │   └── Orchestrator.png # Architecture diagram
│   └── archive/           # Archived documentation
│       ├── CLEAN_CODE_REFACTORING.md
│       ├── FINAL_TEST_COVERAGE_REPORT.md
│       ├── IMPLEMENTATION_SUMMARY.md
│       ├── LEARNINGS.md
│       ├── LINTING_REPORT.md
│       ├── MAINTAINABILITY_CHECKLIST.md
│       ├── OVER_ENGINEERING_ANALYSIS.md
│       ├── SIMPLIFICATION_COMPARISON.md
│       ├── SIMPLIFICATION_IMPLEMENTATION_PLAN.md
│       ├── SIMPLIFIED_REFACTORING_PLAN.md
│       └── TEST_COVERAGE_REPORT.md
│
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── test_claude_control_compat.py      # Backward compatibility tests
│   ├── test_claude_control_simplified.py  # Core functionality tests
│   ├── test_coverage_improvements.py      # Additional coverage tests
│   ├── test_edge_cases.py                # Edge case tests
│   ├── test_tmux_utils_compat.py         # Tmux utils compatibility
│   ├── test_tmux_utils_simplified.py     # Tmux utils core tests
│   └── README.md                         # Test documentation
│
├── registry/               # Runtime data
│   ├── logs/              # Agent conversation logs
│   └── sessions.json      # Active session tracking
│
└── .env.example           # Environment variable template

## Core Components

### 1. Main Entry Point
- **orchestrator**: Bash script providing CLI interface for all operations

### 2. Python Modules
- **claude_control.py**: Monitors Claude agents, tracks health status
- **tmux_utils.py**: Manages tmux sessions, windows, and communication

### 3. Utility Scripts
- **schedule_with_note.sh**: Schedules periodic orchestrator checks
- **scripts/utils/**: Collection of helper scripts for Claude operations

### 4. Configuration
- **.env**: Central configuration for all settings (created from .env.example)
- **.env.example**: Template with all available configuration options

### 5. Testing
- **run_tests.sh**: Runs linting, unit tests, and coverage reports
- **tests/**: Comprehensive test suite with 97% coverage

## Key Features

1. **Simplified Architecture**: Reduced from 20+ classes to 2 main modules
2. **High Test Coverage**: 97% overall coverage
3. **Dynamic Claude Discovery**: Automatically finds best Claude version
4. **Organized Structure**: Clear separation of concerns
5. **Clean Documentation**: Archived old docs, maintained current ones

## Usage Flow

1. User runs `orchestrator <command>`
2. Orchestrator uses Python modules for tmux operations
3. Utility scripts handle Claude-specific tasks
4. Registry tracks active sessions and logs
5. Tests ensure reliability

This structure supports easy maintenance, clear organization, and efficient operation of the AI orchestration system.