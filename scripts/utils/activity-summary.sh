#!/bin/bash
# Generate a comprehensive activity summary for all agents

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}🎯 Tmux Orchestrator Activity Summary${NC}"
echo -e "${BLUE}=================================================${NC}"
echo "Generated at: $(date)"
echo ""

# Get all sessions with Claude agents
SESSIONS=$(python3 "$PROJECT_ROOT/claude_control.py" status detailed 2>/dev/null | grep -E "📁|Window" | grep -B1 "Claude\|Project-Manager" | grep "📁" | awk '{print $2}')

if [ -z "$SESSIONS" ]; then
    echo "No active Claude agents found."
    exit 0
fi

# Function to extract key information from agent output
extract_activity() {
    local content="$1"
    local lines=15
    
    # Look for recent activity patterns
    echo "$content" | tail -50 | grep -E "(Working on|Currently|Task:|Implementing|Fixing|Creating|Running|Building|Checking|ERROR|Failed|Success)" | tail -$lines || echo "No specific activity found"
}

# Function to get agent summary
get_agent_summary() {
    local target="$1"
    local window_name="$2"
    local status="$3"
    
    echo -e "\n${CYAN}📍 $target ($window_name) [$status]${NC}"
    echo "-------------------------------------------"
    
    # Capture recent output
    local output=$(tmux capture-pane -t "$target" -p -S -100 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Get last human message to agent
        local last_human=$(echo "$output" | grep -E "^Human:" | tail -1 | sed 's/Human: //')
        if [ -n "$last_human" ]; then
            echo -e "${YELLOW}Last Request:${NC} $last_human"
        fi
        
        # Get current activity
        echo -e "${GREEN}Recent Activity:${NC}"
        extract_activity "$output"
        
        # Check for errors
        local errors=$(echo "$output" | tail -30 | grep -i "error" | tail -3)
        if [ -n "$errors" ]; then
            echo -e "${RED}Recent Errors:${NC}"
            echo "$errors"
        fi
    else
        echo "Could not capture activity from this window"
    fi
}

# Process each session
for session in $SESSIONS; do
    echo -e "\n${BLUE}📁 Session: $session${NC}"
    echo "============================================="
    
    # Get all Claude windows in this session
    windows=$(python3 "$PROJECT_ROOT/claude_control.py" status detailed 2>/dev/null | sed -n "/📁 $session/,/📁/p" | grep "Window" | grep -E "Claude-Agent|Project-Manager")
    
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            # Parse window information
            window_num=$(echo "$line" | awk -F: '{print $1}' | awk '{print $NF}')
            window_type=$(echo "$line" | awk -F: '{print $2}' | awk '{print $1}')
            status=$(echo "$line" | grep -o '\[.*\]' | tr -d '[]')
            
            get_agent_summary "$session:$window_num" "$window_type" "$status"
        fi
    done <<< "$windows"
done

echo -e "\n${BLUE}=================================================${NC}"
echo -e "${GREEN}✅ Activity summary complete${NC}"

# Optional: Save to file
if [ "$1" == "--save" ]; then
    SUMMARY_FILE="$PROJECT_ROOT/registry/activity_summary_$(date +%Y%m%d_%H%M%S).txt"
    echo -e "\nSaving summary to: $SUMMARY_FILE"
    # Re-run without colors for file output
    "$0" | sed 's/\x1B\[[0-9;]*[a-zA-Z]//g' > "$SUMMARY_FILE"
fi