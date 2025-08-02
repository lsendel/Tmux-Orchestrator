#!/bin/bash
# Auto-fix common linting issues in Tmux Orchestrator

echo "🔧 Starting automatic linting fixes..."

# Fix Python whitespace issues
echo "Fixing Python whitespace..."
for file in *.py; do
    if [ -f "$file" ]; then
        # Remove trailing whitespace
        sed -i.bak 's/[[:space:]]*$//' "$file"
        # Fix missing newline at end of file
        if [ -n "$(tail -c 1 "$file")" ]; then
            echo >> "$file"
        fi
        echo "  ✓ Fixed $file"
    fi
done

# Fix shell script quote issues
echo "Fixing shell script quotes..."
for file in *.sh; do
    if [ -f "$file" ]; then
        # Fix unquoted MESSAGE_DELAY
        sed -i.bak 's/sleep "${MESSAGE_DELAY:-0.5}"/sleep "${MESSAGE_DELAY:-0.5}"/g' "$file"
        # Fix unquoted MINUTES in date command
        sed -i.bak 's/date -v +"${MINUTES}"M/date -v +"${MINUTES}"M/g' "$file"
        echo "  ✓ Fixed $file"
    fi
done

# Add shellcheck disable for source commands
echo "Adding shellcheck pragmas..."
for file in *.sh; do
    if [ -f "$file" ] && grep -q "source.*load_env.sh" "$file"; then
        # Check if pragma already exists
        if ! grep -q "shellcheck disable=SC1091" "$file"; then
            # Add after shebang
            sed -i.bak '1a\
# shellcheck disable=SC1091' "$file"
            echo "  ✓ Added SC1091 disable to $file"
        fi
    fi
done

# Fix the orchestrator script separately
if [ -f "orchestrator" ]; then
    echo "Fixing orchestrator script..."
    # Fix the declare and assign issue
    sed -i.bak 's/local window_count=\$(tmux/local window_count\
    window_count=$(tmux/g' orchestrator
    sed -i.bak 's/local project_path=\$(tmux/local project_path\
    project_path=$(tmux/g' orchestrator
    echo "  ✓ Fixed orchestrator"
fi

# Clean up backup files
echo "Cleaning up..."
rm -f *.bak

echo ""
echo "✅ Automatic fixes complete!"
echo ""
echo "⚠️  Manual fixes still required:"
echo "  1. Security issues in tmux_utils.py (command injection)"
echo "  2. Bare except clauses in Python files"
echo "  3. Path validation in claude_control.py"
echo "  4. Complex shell command quoting in schedule_with_note.sh"
echo ""
echo "Run 'shellcheck *.sh' and 'python3 -m flake8 *.py' to verify"