#!/usr/bin/env python3
"""
Example of simplified claude_control.py
This shows the target architecture after simplification
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Simple constants instead of enum
class AgentStatus:
    READY = "ready"
    BUSY = "busy" 
    ERROR = "error"
    UNKNOWN = "unknown"


class TmuxClient:
    """Handles all tmux command execution and parsing"""
    
    @staticmethod
    def run_command(command: List[str]) -> subprocess.CompletedProcess:
        """Execute a tmux command safely"""
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            logging.debug(f"Command failed: {' '.join(command)}")
            raise
    
    @classmethod
    def get_sessions(cls) -> List[Dict[str, Any]]:
        """Get all tmux sessions"""
        try:
            result = cls.run_command([
                "tmux", "list-sessions", "-F",
                "#{session_name}:#{session_created}:#{session_windows}"
            ])
            
            sessions = []
            for line in result.stdout.strip().split('\n'):
                if line and ':' in line:
                    parts = line.split(':', 2)
                    sessions.append({
                        'name': parts[0],
                        'created': parts[1] if len(parts) > 1 else '',
                        'windows': int(parts[2]) if len(parts) > 2 else 0
                    })
            return sessions
            
        except subprocess.CalledProcessError:
            return []  # No sessions is valid
    
    @classmethod
    def get_windows(cls, session: str) -> List[Dict[str, Any]]:
        """Get windows for a session"""
        try:
            result = cls.run_command([
                "tmux", "list-windows", "-t", session, "-F",
                "#{window_index}:#{window_name}:#{pane_current_command}"
            ])
            
            windows = []
            for line in result.stdout.strip().split('\n'):
                if line and ':' in line:
                    parts = line.split(':', 2)
                    windows.append({
                        'index': int(parts[0]),
                        'name': parts[1] if len(parts) > 1 else '',
                        'command': parts[2] if len(parts) > 2 else ''
                    })
            return windows
            
        except subprocess.CalledProcessError:
            return []
    
    @classmethod
    def capture_pane(cls, session: str, window: int, lines: int = 5) -> str:
        """Capture output from a pane"""
        try:
            result = cls.run_command([
                "tmux", "capture-pane", "-t", f"{session}:{window}",
                "-p", "-S", f"-{lines}"
            ])
            return result.stdout
        except subprocess.CalledProcessError:
            return ""


class ClaudeMonitor:
    """Monitor and manage Claude agents in tmux sessions"""
    
    # Health check patterns
    HEALTH_PATTERNS = {
        AgentStatus.READY: ["Human:", "> ", "Ready", "I'll help", "I can help"],
        AgentStatus.ERROR: ["Error:", "error:", "ERROR", "Failed", "failed"],
        AgentStatus.BUSY: ["Processing", "Working on", "Let me", "I'm currently", "..."]
    }
    
    # Claude detection patterns
    CLAUDE_INDICATORS = ["claude", "Claude", "node"]
    
    def __init__(self, registry_path: Optional[Path] = None):
        self.tmux = TmuxClient()
        self.registry_path = registry_path or Path("./registry/sessions.json")
        self.logger = logging.getLogger(__name__)
    
    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Find all Claude agents across all sessions"""
        agents = []
        
        for session in self.tmux.get_sessions():
            session_agents = self._find_agents_in_session(session)
            agents.extend(session_agents)
        
        return agents
    
    def _find_agents_in_session(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find Claude agents in a specific session"""
        agents = []
        windows = self.tmux.get_windows(session['name'])
        
        for window in windows:
            if self._is_claude_window(window):
                output = self.tmux.capture_pane(session['name'], window['index'])
                
                agents.append({
                    'session': session['name'],
                    'session_created': session.get('created', ''),
                    'window': window['index'],
                    'name': window['name'],
                    'status': self._check_health(output),
                    'process': window.get('command', '')
                })
        
        return agents
    
    def _is_claude_window(self, window: Dict[str, Any]) -> bool:
        """Check if a window contains a Claude agent"""
        search_text = f"{window.get('name', '')} {window.get('command', '')}".lower()
        return any(indicator.lower() in search_text for indicator in self.CLAUDE_INDICATORS)
    
    def _check_health(self, output: str) -> str:
        """Determine agent health from output"""
        if not output:
            return AgentStatus.UNKNOWN
        
        # Check each status type (order matters - check error first)
        for status, patterns in self.HEALTH_PATTERNS.items():
            if any(pattern in output for pattern in patterns):
                return status
        
        return AgentStatus.BUSY
    
    def save_status(self, agents: List[Dict[str, Any]]) -> None:
        """Save current status to registry"""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Group agents by session
        sessions = {}
        for agent in agents:
            session_name = agent['session']
            if session_name not in sessions:
                sessions[session_name] = {
                    'name': session_name,
                    'created': agent.get('session_created', ''),
                    'agents': []
                }
            sessions[session_name]['agents'].append(agent)
        
        data = {
            'updated': datetime.now().isoformat(),
            'sessions': list(sessions.values()),
            'total_agents': len(agents)
        }
        
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def health_check(self) -> Dict[str, Any]:
        """System health check"""
        # Check tmux
        try:
            self.tmux.run_command(["tmux", "-V"])
            tmux_ok = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            tmux_ok = False
        
        # Check claude
        claude_ok = self._check_claude_available()
        
        # Get current status
        agents = self.get_all_agents()
        sessions = {agent['session'] for agent in agents}
        
        issues = []
        if not tmux_ok:
            issues.append("tmux not found")
        if not claude_ok:
            issues.append("claude command not found")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'tmux_available': tmux_ok,
            'claude_available': claude_ok,
            'active_sessions': len(sessions),
            'total_agents': len(agents),
            'agents_by_status': self._count_by_status(agents),
            'issues': issues
        }
    
    def _check_claude_available(self) -> bool:
        """Check if Claude CLI is available"""
        # First try the helper script
        script_path = Path(__file__).parent / "get_claude_command.sh"
        if script_path.exists():
            try:
                result = subprocess.run(
                    [str(script_path)],
                    capture_output=True,
                    check=False
                )
                if result.returncode == 0:
                    return True
            except Exception:
                pass
        
        # Fallback to direct check
        try:
            subprocess.run(["claude", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _count_by_status(self, agents: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count agents by status"""
        counts = {
            AgentStatus.READY: 0,
            AgentStatus.BUSY: 0,
            AgentStatus.ERROR: 0,
            AgentStatus.UNKNOWN: 0
        }
        
        for agent in agents:
            status = agent.get('status', AgentStatus.UNKNOWN)
            counts[status] = counts.get(status, 0) + 1
        
        return counts


# Simple formatting functions instead of class
def format_status(agents: List[Dict[str, Any]], detailed: bool = False) -> None:
    """Format and print status information"""
    if not agents:
        print("\033[1;33mNo active Claude agents found\033[0m")
        return
    
    # Group by session
    sessions = {}
    for agent in agents:
        session = agent['session']
        if session not in sessions:
            sessions[session] = []
        sessions[session].append(agent)
    
    # Print header
    print("\n\033[0;34m🎯 Tmux Orchestrator Status\033[0m")
    print("=" * 50)
    print(f"Active Sessions: {len(sessions)}")
    print(f"Total Agents: {len(agents)}\n")
    
    # Print each session
    for session, session_agents in sessions.items():
        print(f"\033[0;32m📁 {session}\033[0m")
        print(f"   Agents: {len(session_agents)}")
        
        if detailed:
            for agent in session_agents:
                status = agent['status']
                color = {
                    AgentStatus.READY: '\033[0;32m',   # green
                    AgentStatus.BUSY: '\033[1;33m',    # yellow
                    AgentStatus.ERROR: '\033[0;31m',   # red
                    AgentStatus.UNKNOWN: '\033[0;34m'  # blue
                }.get(status, '')
                
                print(f"   - Window {agent['window']}: {agent['name']} "
                      f"[{color}{status}\033[0m]")
        print()


def main():
    """Main entry point with simplified logic"""
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        monitor = ClaudeMonitor()
        
        # Parse simple commands
        command = sys.argv[1] if len(sys.argv) > 1 else "status"
        
        if command == "status":
            detailed = len(sys.argv) > 2 and sys.argv[2] == "detailed"
            agents = monitor.get_all_agents()
            format_status(agents, detailed)
            monitor.save_status(agents)
            
        elif command == "health":
            health = monitor.health_check()
            print(json.dumps(health, indent=2))
            
        else:
            print(f"Unknown command: {command}")
            print("Usage: claude_control.py [status [detailed]|health]")
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


# Compatibility layer (temporary during migration)
# This allows old imports to work
class ClaudeOrchestrator:
    """Backward compatibility wrapper"""
    def __init__(self):
        self.monitor = ClaudeMonitor()
    
    def get_active_sessions(self):
        # Convert new format to old format
        agents = self.monitor.get_all_agents()
        # ... conversion logic
    
    def status(self, detailed=False):
        agents = self.monitor.get_all_agents()
        format_status(agents, detailed)
        self.monitor.save_status(agents)
    
    def health_check(self):
        return self.monitor.health_check()