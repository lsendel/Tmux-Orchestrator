#!/bin/bash
# Update script for Tmux Orchestrator

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔄 Tmux Orchestrator Update Script${NC}"
echo "=================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Update Python dependencies
update_python_deps() {
    echo -e "\n${YELLOW}📦 Updating Python dependencies...${NC}"
    if [ -f "requirements.txt" ]; then
        pip install --upgrade -r requirements.txt
        echo -e "${GREEN}✅ Python dependencies updated${NC}"
    else
        echo -e "${RED}❌ requirements.txt not found${NC}"
    fi
}

# Update Claude CLI
update_claude() {
    echo -e "\n${YELLOW}🤖 Checking Claude CLI...${NC}"
    
    # Get current version
    CURRENT_VERSION=$("$SCRIPT_DIR/scripts/utils/get_claude_command.sh" | grep "Using" | grep -oE "v[0-9]+\.[0-9]+\.[0-9]+")
    echo "Current Claude version: $CURRENT_VERSION"
    
    # Check for updates
    if command_exists npm; then
        echo "Checking for Claude updates..."
        
        # Check global installation
        if npm list -g @anthropic-ai/claude-cli >/dev/null 2>&1; then
            echo "Updating global Claude installation..."
            npm update -g @anthropic-ai/claude-cli
        fi
        
        # Check local installation
        if [ -d "$HOME/.claude/local" ]; then
            echo "Updating local Claude installation..."
            cd "$HOME/.claude/local" && npm update
            cd "$SCRIPT_DIR"
        fi
        
        # Show new version
        NEW_VERSION=$("$SCRIPT_DIR/scripts/utils/get_claude_command.sh" | grep "Using" | grep -oE "v[0-9]+\.[0-9]+\.[0-9]+")
        if [ "$CURRENT_VERSION" != "$NEW_VERSION" ]; then
            echo -e "${GREEN}✅ Claude updated from $CURRENT_VERSION to $NEW_VERSION${NC}"
        else
            echo -e "${GREEN}✅ Claude is up to date${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  npm not found - cannot check for Claude updates${NC}"
    fi
}

# Update Git repository
update_git() {
    echo -e "\n${YELLOW}📥 Updating Git repository...${NC}"
    
    # Check if we're in a git repo
    if [ -d ".git" ]; then
        # Save current branch
        CURRENT_BRANCH=$(git branch --show-current)
        
        # Check for uncommitted changes
        if [ -n "$(git status --porcelain)" ]; then
            echo -e "${YELLOW}⚠️  You have uncommitted changes. Please commit or stash them first.${NC}"
            echo "Run: git stash"
            return 1
        fi
        
        # Fetch and show updates
        echo "Fetching updates..."
        git fetch origin
        
        # Check if we're behind
        BEHIND=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count)
        if [ "$BEHIND" -gt 0 ]; then
            echo "Found $BEHIND new commits"
            read -p "Do you want to pull these changes? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                git pull origin $CURRENT_BRANCH
                echo -e "${GREEN}✅ Repository updated${NC}"
            else
                echo -e "${YELLOW}⚠️  Skipped repository update${NC}"
            fi
        else
            echo -e "${GREEN}✅ Repository is up to date${NC}"
        fi
    else
        echo -e "${RED}❌ Not a git repository${NC}"
    fi
}

# Check configuration
check_config() {
    echo -e "\n${YELLOW}⚙️  Checking configuration...${NC}"
    
    # Check .env file
    if [ -f ".env.example" ] && [ -f ".env" ]; then
        # Check for new variables in .env.example
        NEW_VARS=$(comm -23 <(grep -E "^[A-Z_]+=" .env.example | cut -d= -f1 | sort) <(grep -E "^[A-Z_]+=" .env | cut -d= -f1 | sort))
        if [ -n "$NEW_VARS" ]; then
            echo -e "${YELLOW}⚠️  New configuration variables found in .env.example:${NC}"
            echo "$NEW_VARS"
            echo "Consider adding these to your .env file"
        else
            echo -e "${GREEN}✅ Configuration is up to date${NC}"
        fi
    fi
}

# Run tests
run_tests() {
    echo -e "\n${YELLOW}🧪 Running tests...${NC}"
    read -p "Do you want to run tests after update? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./run_tests.sh
    fi
}

# Main update sequence
main() {
    echo -e "\n${BLUE}Starting update process...${NC}\n"
    
    # Run updates
    update_git
    update_python_deps
    update_claude
    check_config
    
    echo -e "\n${BLUE}Update Summary${NC}"
    echo "=============="
    
    # Show current versions
    echo -e "\nCurrent versions:"
    echo "- Python: $(python3 --version)"
    echo "- Claude: $("$SCRIPT_DIR/scripts/utils/get_claude_command.sh" | grep "Using" | cut -d: -f2)"
    echo "- Git branch: $(git branch --show-current)"
    
    # Optional test run
    run_tests
    
    echo -e "\n${GREEN}✅ Update complete!${NC}"
}

# Handle command line arguments
case "$1" in
    python)
        update_python_deps
        ;;
    claude)
        update_claude
        ;;
    git)
        update_git
        ;;
    config)
        check_config
        ;;
    test)
        run_tests
        ;;
    *)
        main
        ;;
esac