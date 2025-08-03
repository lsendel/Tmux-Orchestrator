#!/bin/bash
# shellcheck disable=SC1091
# Dynamic scheduler with note for next check
# Usage: ./schedule_with_note.sh <minutes> "<note>" [target_window]

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/scripts/utils/load_env.sh"

MINUTES=${1:-$DEFAULT_SCHEDULE_MINUTES}
NOTE=${2:-"$DEFAULT_CHECK_NOTE"}
TARGET=${3:-"$DEFAULT_TARGET_WINDOW"}

# Get script directory dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTE_FILE="$SCRIPT_DIR/next_check_note.txt"

# Create a note file for the next check
{
    echo "=== Next Check Note ($(date)) ==="
    echo "Scheduled for: $MINUTES minutes"
    echo ""
    echo "$NOTE"
} > "$NOTE_FILE"

echo "Scheduling check in $MINUTES minutes with note: $NOTE"

# Calculate the exact time when the check will run
CURRENT_TIME=$(date +"%H:%M:%S")
RUN_TIME=$(date -v +"${MINUTES}"M +"%H:%M:%S" 2>/dev/null || date -d "+${MINUTES} minutes" +"%H:%M:%S" 2>/dev/null)

# Use nohup to completely detach the sleep process
# Use bc for floating point calculation
SECONDS=$(echo "$MINUTES * 60" | bc)
nohup bash -c "sleep '$SECONDS' && tmux send-keys -t '$TARGET' 'Time for orchestrator check! cat \"$NOTE_FILE\" && python3 \"$SCRIPT_DIR/claude_control.py\" status detailed' && sleep 1 && tmux send-keys -t '$TARGET' Enter" > /dev/null 2>&1 &

# Get the PID of the background process
SCHEDULE_PID=$!

echo "Scheduled successfully - process detached (PID: $SCHEDULE_PID)"
echo "SCHEDULED TO RUN AT: $RUN_TIME (in $MINUTES minutes from $CURRENT_TIME)"