#!/bin/bash
# Check what agents are currently working on

if [ $# -lt 1 ]; then
    echo "Usage: $0 <session:window>"
    echo "Example: $0 zamaz-mcp-llm:0"
    exit 1
fi

TARGET="$1"
LINES="${2:-30}"

echo "=== Recent activity from $TARGET (last $LINES lines) ==="
echo ""

# Capture the pane content
OUTPUT=$(tmux capture-pane -t "$TARGET" -p -S -"$LINES" 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "$OUTPUT" | tail -"$LINES"
else
    echo "Error: Could not capture from $TARGET"
    echo "Make sure the session:window exists"
fi