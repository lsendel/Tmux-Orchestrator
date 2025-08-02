#!/bin/bash
# Start Claude in a tmux window using the latest available version
# Usage: ./start_claude.sh <session:window>

if [ $# -lt 1 ]; then
    echo "Usage: $0 <session:window>"
    echo "Example: $0 my-project:0"
    exit 1
fi

WINDOW="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Get the Claude command dynamically
CLAUDE_CMD=$("$SCRIPT_DIR/get_claude_command.sh")
if [ $? -ne 0 ]; then
    echo "Failed to find Claude command"
    exit 1
fi

echo "Starting Claude in window $WINDOW using: $CLAUDE_CMD"

# Check if something is already running in the window
CURRENT_CMD=$(tmux list-panes -t "$WINDOW" -F '#{pane_current_command}' 2>/dev/null)
if [ "$CURRENT_CMD" = "node" ] || [ "$CURRENT_CMD" = "claude" ]; then
    echo "Claude or Node appears to be already running in $WINDOW"
    echo "Send Ctrl-C first if you want to restart"
    exit 1
fi

# Start Claude
tmux send-keys -t "$WINDOW" "$CLAUDE_CMD" Enter

echo "Claude started successfully in $WINDOW"