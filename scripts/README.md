# Scripts Directory

This directory contains utility scripts for the Tmux Orchestrator.

## Directory Structure

```
scripts/
├── utils/           # Utility scripts used by the orchestrator
│   ├── get_claude_command.sh    # Finds the best available Claude installation
│   ├── load_env.sh              # Loads environment variables
│   ├── send-claude-message.sh   # Sends messages to Claude agents
│   └── start_claude.sh          # Starts Claude in tmux windows
└── README.md        # This file
```

## Utils Scripts

### get_claude_command.sh
Dynamically finds the best available Claude installation:
- Prioritizes local installation (~/.claude/local)
- Falls back to global npm or system PATH
- Returns both command path and version

### load_env.sh
Loads environment variables from .env file and sets defaults for:
- Schedule minutes
- Check notes
- Target windows
- Other orchestrator settings

### send-claude-message.sh
Handles sending messages to Claude agents in tmux:
- Manages timing between message and Enter key
- Works with both windows and panes
- Prevents common messaging errors

### start_claude.sh
Wrapper script to start Claude in tmux windows:
- Uses get_claude_command.sh to find Claude
- Prevents accidental double-starts
- Provides consistent startup interface

## Usage

These scripts are called by the main orchestrator script and should not typically be run directly.