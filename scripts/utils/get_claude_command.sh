#!/bin/bash
# shellcheck disable=SC1091
# Dynamic Claude command finder
# This script finds the correct Claude command to use, prioritizing local installations

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load_env.sh"

# Function to check if a command exists and is executable
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get Claude version
get_claude_version() {
    "$1" --version 2>/dev/null | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1
}

# Priority order for finding Claude:
# 1. Local installation in ~/.claude/local
# 2. Local node_modules in current project
# 3. Global npm installation
# 4. System PATH claude

CLAUDE_CMD=""
CLAUDE_VERSION=""

# Check 1: Local Claude installation (preferred)
if [ -x "${CLAUDE_LOCAL_PATH}" ]; then
    CLAUDE_CMD="${CLAUDE_LOCAL_PATH}"
    CLAUDE_VERSION=$(get_claude_version "$CLAUDE_CMD")
    echo "# Using local Claude installation: $CLAUDE_CMD (v$CLAUDE_VERSION)" >&2

# Check 2: Check for project-local installation
elif [ -x "${CLAUDE_PROJECT_PATH}" ]; then
    CLAUDE_CMD="${CLAUDE_PROJECT_PATH}"
    CLAUDE_VERSION=$(get_claude_version "$CLAUDE_CMD")
    echo "# Using project-local Claude: $CLAUDE_CMD (v$CLAUDE_VERSION)" >&2

# Check 3: Global npm installation
elif [ -x "${CLAUDE_GLOBAL_PATH}" ]; then
    CLAUDE_CMD="${CLAUDE_GLOBAL_PATH}"
    CLAUDE_VERSION=$(get_claude_version "$CLAUDE_CMD")
    echo "# Using global npm Claude: $CLAUDE_CMD (v$CLAUDE_VERSION)" >&2

# Check 4: System PATH
elif command_exists claude; then
    CLAUDE_CMD="claude"
    CLAUDE_VERSION=$(get_claude_version "$CLAUDE_CMD")
    echo "# Using system Claude: $CLAUDE_CMD (v$CLAUDE_VERSION)" >&2

else
    echo "# ERROR: Claude not found in any expected location!" >&2
    echo "# Please install Claude using one of these methods:" >&2
    echo "#   - npm install -g ${CLAUDE_NPM_PACKAGE}" >&2
    echo "#   - claude install (if you have an older version)" >&2
    exit 1
fi

# Export for use in other scripts
export CLAUDE_COMMAND="$CLAUDE_CMD"
export CLAUDE_VERSION="$CLAUDE_VERSION"

# If called directly, output the command
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    echo "$CLAUDE_CMD"
fi