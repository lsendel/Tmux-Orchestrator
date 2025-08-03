# Tmux Orchestrator Configuration Guide

## 🔧 Configuration Overview

All configuration for Tmux Orchestrator is now managed through the `.env` file. This provides a single, simple location for all settings.

## 📋 Quick Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` to customize your settings:
   ```bash
   # Edit with your preferred editor
   nano .env
   # or
   vim .env
   ```

## 🗂️ Key Configuration Options

### Project Directory
```bash
# Where your coding projects are located
CODING_DIR="$HOME/IdeaProjects"
```

### Claude Settings
```bash
# Startup delay for Claude (seconds)
CLAUDE_STARTUP_DELAY=5

# Delay between message and Enter key
MESSAGE_DELAY=0.5
```

### Scheduling
```bash
# Default check-in interval (minutes)
DEFAULT_SCHEDULE_MINUTES=3

# Default orchestrator window
DEFAULT_TARGET_WINDOW="tmux-orc:0"
```

### Git Configuration
```bash
# Auto-commit interval (minutes)
AUTO_COMMIT_INTERVAL=30

# Commit message prefix
COMMIT_MESSAGE_PREFIX="Auto-commit"

# Enable automatic push
ENABLE_AUTO_PUSH=false
```

## 🔄 Migration from config.json

If you were using `config.json`, all settings have been moved to `.env`:

| Old (config.json) | New (.env) |
|-------------------|------------|
| orchestrator.coding_directory | CODING_DIR |
| orchestrator.check_interval_minutes | DEFAULT_SCHEDULE_MINUTES |
| claude.startup_delay_seconds | CLAUDE_STARTUP_DELAY |
| claude.message_delay_seconds | MESSAGE_DELAY |
| git.auto_commit_interval_minutes | AUTO_COMMIT_INTERVAL |

## 📝 Environment Variable Priority

The system checks for values in this order:
1. Environment variables set in your shell
2. Values in `.env` file
3. Default values in the code

Example:
```bash
# Override for single command
CODING_DIR=/tmp/test ./orchestrator list

# Or export for session
export CODING_DIR=/tmp/test
./orchestrator list
```

## 🎯 Common Customizations

### Different Project Directory
```bash
# Default
CODING_DIR="$HOME/IdeaProjects"

# Alternative locations
CODING_DIR="$HOME/Projects"
CODING_DIR="$HOME/Development"
CODING_DIR="/opt/projects"
```

### Faster/Slower Claude Startup
```bash
# Faster (if Claude starts quickly)
CLAUDE_STARTUP_DELAY=2

# Slower (for slower systems)
CLAUDE_STARTUP_DELAY=10
```

### Different Schedule Intervals
```bash
# Check every 15 minutes
DEFAULT_SCHEDULE_MINUTES=15

# Check every hour
DEFAULT_SCHEDULE_MINUTES=60
```

## 🚀 Advanced Configuration

See `.env.example` for all available options including:
- Resource limits
- Notification settings
- Debug options
- Backup configuration
- Custom window names
- And more...

## ❓ Troubleshooting

1. **Settings not taking effect?**
   - Make sure `.env` is in the project root
   - Check file permissions: `chmod 600 .env`
   - Verify no syntax errors in `.env`

2. **Want to see current configuration?**
   ```bash
   # Show all environment variables
   source scripts/utils/load_env.sh && env | grep -E "CODING_DIR|CLAUDE|SCHEDULE"
   ```

3. **Need to reset to defaults?**
   ```bash
   # Start fresh
   cp .env.example .env
   ```