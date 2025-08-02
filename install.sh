#!/bin/bash
# Tmux Orchestrator Installation Script

set -e

echo "🎯 Installing Tmux Orchestrator..."

# Check dependencies
check_dependency() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ Error: $1 is required but not installed"
        return 1
    fi
    echo "✅ $1 found"
    return 0
}

echo "Checking dependencies..."
DEPS_OK=true
check_dependency "tmux" || DEPS_OK=false
check_dependency "python3" || DEPS_OK=false
check_dependency "git" || DEPS_OK=false
check_dependency "bc" || DEPS_OK=false

if [ "$DEPS_OK" = false ]; then
    echo "Please install missing dependencies and try again"
    exit 1
fi

# Install Python requirements
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p registry/logs
mkdir -p registry/sessions

# Set up PATH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Setting up PATH..."

# Add to .bashrc/.zshrc
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "Tmux Orchestrator" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "# Tmux Orchestrator" >> "$SHELL_RC"
        echo "export PATH=\"$SCRIPT_DIR:\$PATH\"" >> "$SHELL_RC"
        echo "✅ Added to $SHELL_RC"
        echo "Run 'source $SHELL_RC' to update your current shell"
    fi
fi

# Create symlink for global access
if [ -d "$HOME/.local/bin" ]; then
    ln -sf "$SCRIPT_DIR/orchestrator" "$HOME/.local/bin/orchestrator" 2>/dev/null || true
    echo "✅ Created symlink in ~/.local/bin"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Run 'source $SHELL_RC' to update your PATH"
echo "2. Run 'orchestrator help' to see available commands"
echo "3. Edit config.json to customize settings"
echo ""
echo "Happy orchestrating! 🎉"