#!/bin/bash
# shellcheck disable=SC1091
# Load environment variables from .env file
# This script should be sourced by other scripts: source ./load_env.sh

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find project root by looking for key files
find_project_root() {
    local dir="$SCRIPT_DIR"
    while [ "$dir" != "/" ]; do
        if [ -f "$dir/orchestrator" ] && [ -f "$dir/claude_control.py" ]; then
            echo "$dir"
            return
        fi
        dir="$(dirname "$dir")"
    done
    # Fallback to two levels up
    echo "$(cd "$SCRIPT_DIR/../.." && pwd)"
}

PROJECT_ROOT="$(find_project_root)"

# Check if .env file exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    # Export all variables from .env file
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo "Warning: .env file not found at $PROJECT_ROOT/.env"
    echo "Using default values. Copy .env.example to .env and customize."
    
    # Set critical defaults if .env is missing
    export CODING_DIR="${CODING_DIR:-$HOME/Coding}"
    export MESSAGE_DELAY="${MESSAGE_DELAY:-0.5}"
    export CLAUDE_STARTUP_DELAY="${CLAUDE_STARTUP_DELAY:-5}"
    export DEFAULT_TARGET_WINDOW="${DEFAULT_TARGET_WINDOW:-tmux-orc:0}"
    export DEFAULT_SCHEDULE_MINUTES="${DEFAULT_SCHEDULE_MINUTES:-3}"
    export DEFAULT_CHECK_NOTE="${DEFAULT_CHECK_NOTE:-Standard check-in}"
fi

# Function to get env variable with default
get_env() {
    local var_name="$1"
    local default_value="$2"
    local value="${!var_name}"
    echo "${value:-$default_value}"
}