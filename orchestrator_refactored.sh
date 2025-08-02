#!/bin/bash
# Tmux Orchestrator CLI - Refactored for Clean Code
# Main entry point for orchestrator management

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source environment and utilities
# shellcheck disable=SC1091
source "$SCRIPT_DIR/load_env.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Constants
readonly DEFAULT_CLAUDE_STARTUP_DELAY=5
readonly DEFAULT_CODING_DIR="$HOME/IdeaProjects"

# ============================================================
# Utility Functions (Single Responsibility)
# ============================================================

# Print colored message
print_message() {
    local color="$1"
    local message="$2"
    echo -e "${color}${message}${NC}"
}

print_error() {
    print_message "$RED" "Error: $1"
}

print_success() {
    print_message "$GREEN" "✅ $1"
}

print_warning() {
    print_message "$YELLOW" "Warning: $1"
}

print_info() {
    print_message "$BLUE" "$1"
}

# Get coding directory from config or environment
get_coding_directory() {
    local config_dir="$DEFAULT_CODING_DIR"
    if [ -f "$SCRIPT_DIR/config.json" ]; then
        config_dir=$(python3 -c "
import json
with open('$SCRIPT_DIR/config.json') as f:
    config = json.load(f)
    print(config['orchestrator']['coding_directory'].replace('~', '$HOME'))
" 2>/dev/null) || config_dir="$DEFAULT_CODING_DIR"
    fi
    echo "${CODING_DIR:-$config_dir}"
}

# Validate directory exists
validate_directory() {
    local dir="$1"
    local error_msg="$2"
    
    if [ ! -d "$dir" ]; then
        print_error "$error_msg"
        return 1
    fi
    return 0
}

# Check if tmux session exists
session_exists() {
    local session="$1"
    tmux has-session -t "$session" 2>/dev/null
}

# ============================================================
# Core Business Functions (Single Responsibility)
# ============================================================

# Show help message
show_help() {
    cat << EOF
🎯 Tmux Orchestrator - AI Agent Coordination System

Usage: orchestrator <command> [options]

Commands:
  start <project>     Start a new project with Claude agent
  status              Show status of all active sessions
  status detailed     Show detailed status with agent health
  stop <session>      Stop a tmux session
  deploy <session>    Deploy a project manager to a session
  message <target>    Send a message to a Claude agent
  schedule <min>      Schedule a check-in after N minutes
  list                List all projects in coding directory
  health              Run system health checks
  help                Show this help message

Examples:
  orchestrator start task-templates
  orchestrator deploy my-project
  orchestrator message my-project:0 "What's your status?"
  orchestrator schedule 30 "Check test results"

Configuration:
  Projects directory: $(get_coding_directory)
  Registry location: $SCRIPT_DIR/registry/

For more information, see README.md
EOF
}

# List all projects in coding directory
list_projects() {
    local coding_dir
    coding_dir=$(get_coding_directory)
    
    if ! validate_directory "$coding_dir" "Coding directory not found at $coding_dir"; then
        echo "Set CODING_DIR environment variable to override"
        return 1
    fi
    
    print_info "Projects in $coding_dir:"
    find "$coding_dir" -maxdepth 1 -type d -not -path "$coding_dir" -exec basename {} \; | sort
}

# ============================================================
# Tmux Session Management (Extracted Functions)
# ============================================================

# Create tmux session with standard windows
create_project_session() {
    local project_name="$1"
    local project_path="$2"
    
    tmux new-session -d -s "$project_name" -c "$project_path" -n "Claude-Agent"
    tmux new-window -t "$project_name" -n "Shell" -c "$project_path"
    tmux new-window -t "$project_name" -n "Dev-Server" -c "$project_path"
}

# Start Claude in specified window
start_claude_in_window() {
    local target="$1"
    "$SCRIPT_DIR/start_claude.sh" "$target"
}

# Send initial briefing to Claude agent
brief_claude_agent() {
    local target="$1"
    local project_name="$2"
    
    sleep "${CLAUDE_STARTUP_DELAY:-$DEFAULT_CLAUDE_STARTUP_DELAY}"
    
    "$SCRIPT_DIR/send-claude-message.sh" "$target" \
"You are responsible for the $project_name codebase. Your duties include:
1. Getting the application running
2. Checking GitHub issues for priorities  
3. Working on highest priority tasks
4. Keeping the orchestrator informed of progress

First, analyze the project to understand what type it is and how to start the dev server."
}

# Brief project manager
brief_project_manager() {
    local target="$1"
    
    sleep "${PM_STARTUP_DELAY:-$DEFAULT_CLAUDE_STARTUP_DELAY}"
    
    "$SCRIPT_DIR/send-claude-message.sh" "$target" \
"You are the Project Manager for this project. Your responsibilities:
1. Quality Standards: Maintain exceptionally high standards
2. Verification: Test everything thoroughly
3. Team Coordination: Manage communication efficiently
4. Progress Tracking: Monitor velocity and report to orchestrator
5. Risk Management: Identify issues early

Please introduce yourself to the developer in window 0."
}

# ============================================================
# Command Implementations (Orchestration Layer)
# ============================================================

# Start a new project
cmd_start_project() {
    local project_name="$1"
    
    # Validate input
    if [ -z "$project_name" ]; then
        print_error "Project name required"
        echo "Usage: orchestrator start <project-name>"
        return 1
    fi
    
    # Get project path
    local coding_dir
    coding_dir=$(get_coding_directory)
    local project_path="$coding_dir/$project_name"
    
    # Validate project exists
    if ! validate_directory "$project_path" "Project not found at $project_path"; then
        echo "Available projects:"
        list_projects
        return 1
    fi
    
    # Check if session already exists
    if session_exists "$project_name"; then
        print_warning "Session $project_name already exists"
        return 1
    fi
    
    print_info "Starting project: $project_name"
    
    # Create session and setup
    create_project_session "$project_name" "$project_path"
    start_claude_in_window "$project_name:0"
    brief_claude_agent "$project_name:0" "$project_name"
    
    print_success "Project $project_name started successfully"
    echo "Windows created:"
    echo "  - Claude-Agent (window 0)"
    echo "  - Shell (window 1)"
    echo "  - Dev-Server (window 2)"
}

# Deploy a project manager
cmd_deploy_pm() {
    local session="$1"
    
    # Validate input
    if [ -z "$session" ]; then
        print_error "Session name required"
        echo "Usage: orchestrator deploy <session>"
        return 1
    fi
    
    # Validate session exists
    if ! session_exists "$session"; then
        print_error "Session $session not found"
        return 1
    fi
    
    print_info "Deploying Project Manager to $session"
    
    # Get project path and window count
    local project_path
    project_path=$(tmux display-message -t "$session:0" -p '#{pane_current_path}')
    
    local window_count
    window_count=$(tmux list-windows -t "$session" -F "#{window_index}" | wc -l)
    
    # Create PM window and setup
    tmux new-window -t "$session" -n "Project-Manager" -c "$project_path"
    start_claude_in_window "$session:$window_count"
    brief_project_manager "$session:$window_count"
    
    print_success "Project Manager deployed to window $window_count"
}

# Stop a tmux session
cmd_stop_session() {
    local session="$1"
    
    if [ -z "$session" ]; then
        print_error "Session name required"
        echo "Usage: orchestrator stop <session>"
        return 1
    fi
    
    if ! session_exists "$session"; then
        print_error "Session $session not found"
        return 1
    fi
    
    tmux kill-session -t "$session"
    print_success "Session $session stopped"
}

# Send message to Claude agent
cmd_send_message() {
    local target="$1"
    local message="$2"
    
    if [ -z "$target" ] || [ -z "$message" ]; then
        print_error "Target and message required"
        echo "Usage: orchestrator message <target> <message>"
        return 1
    fi
    
    "$SCRIPT_DIR/send-claude-message.sh" "$target" "$message"
}

# ============================================================
# Main Command Dispatcher
# ============================================================

main() {
    local command="$1"
    shift
    
    case "$command" in
        start)
            cmd_start_project "$@"
            ;;
        status)
            python3 "$SCRIPT_DIR/claude_control.py" status "$@"
            ;;
        stop)
            cmd_stop_session "$@"
            ;;
        deploy)
            cmd_deploy_pm "$@"
            ;;
        message)
            cmd_send_message "$@"
            ;;
        schedule)
            "$SCRIPT_DIR/schedule_with_note.sh" "$@"
            ;;
        list)
            list_projects
            ;;
        health)
            python3 "$SCRIPT_DIR/claude_control.py" health
            ;;
        help|--help|-h|"")
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"