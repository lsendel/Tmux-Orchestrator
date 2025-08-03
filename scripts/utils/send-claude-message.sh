#!/bin/bash
# shellcheck disable=SC1091
# Send message to Claude agent in tmux window
# Usage: send-claude-message.sh <session:window> <message>

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load_env.sh"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session:window> <message>"
    echo "Example: $0 agentic-seek:3 'Hello Claude!'"
    exit 1
fi

WINDOW="$1"
shift  # Remove first argument, rest is the message
MESSAGE="$*"

# Send the message
tmux send-keys -t "$WINDOW" "$MESSAGE"

# Wait for UI to register (configurable delay)
sleep "${MESSAGE_DELAY:-0.5}"

# Send Enter to submit
tmux send-keys -t "$WINDOW" Enter

echo "Message sent to $WINDOW: $MESSAGE"
