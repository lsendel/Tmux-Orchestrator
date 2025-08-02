# Quick Start Guide - Tmux Orchestrator

## Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/Tmux-Orchestrator.git
cd Tmux-Orchestrator

# Install dependencies
pip install -r requirements.txt
```

## Basic Usage

### 1. Start a New Project
```bash
./orchestrator start my-project
```
This creates:
- Window 0: Claude-Agent
- Window 1: Shell
- Window 2: Dev-Server

### 2. Check Status
```bash
# Simple status
./orchestrator status

# Detailed status with agent health
./orchestrator status detailed
```

### 3. Deploy a Project Manager
```bash
./orchestrator deploy my-project
```

### 4. Send Messages to Agents
```bash
./orchestrator message my-project:0 "What's your current progress?"
```

### 5. Schedule Check-ins
```bash
# Schedule a check-in after 30 minutes
./orchestrator schedule 30 "Review test results"
```

## Python API Examples

### Monitor Agents
```python
from claude_control import ClaudeMonitor

monitor = ClaudeMonitor()
agents = monitor.get_all_agents()

for agent in agents:
    print(f"{agent['session']}:{agent['window']} - {agent['status']}")
```

### Create Sessions
```python
from tmux_utils import TmuxManager

manager = TmuxManager()
manager.create_project_session("new-project", "/path/to/project")
```

### Send Messages
```python
manager.send_message("my-project", 0, "Please run the tests")
```

## Tips
- Always check `./orchestrator health` to verify system is ready
- Use meaningful session names for easy identification
- Schedule regular check-ins for long-running tasks
- Archive completed projects to keep the system clean

See [README.md](README.md) for full documentation.