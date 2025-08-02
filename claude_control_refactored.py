#!/usr/bin/env python3
"""
Claude Orchestrator Control System - Refactored for Clean Code
Manages Claude AI agents across tmux sessions
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re


class AgentStatus(Enum):
    """Enumeration for agent health status"""
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class Agent:
    """Data class representing a Claude agent"""
    window: int
    name: str
    status: AgentStatus
    process: str = ""


@dataclass
class Session:
    """Data class representing a tmux session"""
    name: str
    created: str
    windows: int
    agents: List[Agent]


class TmuxCommandExecutor:
    """Handles all tmux command execution with proper error handling"""
    
    @staticmethod
    def run_command(command: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
        """Execute a command with consistent error handling"""
        try:
            return subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError:
            # Re-raise to be handled by caller
            raise
        except Exception as e:
            logging.error(f"Unexpected error running command {' '.join(command)}: {e}")
            raise
    
    @staticmethod
    def get_sessions() -> List[Tuple[str, str, int]]:
        """Get list of tmux sessions"""
        try:
            result = TmuxCommandExecutor.run_command(
                ["tmux", "list-sessions", "-F", "#{session_name}:#{session_created}:#{session_windows}"]
            )
            sessions = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        sessions.append((parts[0], parts[1], int(parts[2])))
            return sessions
        except subprocess.CalledProcessError:
            return []
    
    @staticmethod
    def get_windows(session: str) -> List[Tuple[int, str, str]]:
        """Get list of windows in a session"""
        try:
            result = TmuxCommandExecutor.run_command(
                ["tmux", "list-windows", "-t", session, "-F", "#{window_index}:#{window_name}:#{pane_current_command}"]
            )
            windows = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        windows.append((int(parts[0]), parts[1], parts[2]))
            return windows
        except subprocess.CalledProcessError:
            return []
    
    @staticmethod
    def capture_pane(session: str, window: str, lines: int = 5) -> str:
        """Capture output from a tmux pane"""
        try:
            result = TmuxCommandExecutor.run_command(
                ["tmux", "capture-pane", "-t", f"{session}:{window}", "-p", "-S", f"-{lines}"]
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""


class ClaudeHealthChecker:
    """Handles Claude agent health checking logic"""
    
    HEALTH_INDICATORS = {
        "ready": ["Human:", "> ", "Ready", "I'll help", "I can help"],
        "error": ["Error:", "error:", "ERROR", "Failed", "failed"],
        "busy": ["Processing", "Working on", "Let me", "I'm currently", "..."]
    }
    
    @classmethod
    def check_health(cls, output: str) -> AgentStatus:
        """Determine agent health from output"""
        if not output:
            return AgentStatus.UNKNOWN
        
        # Check for each status type
        for status, indicators in cls.HEALTH_INDICATORS.items():
            if any(indicator in output for indicator in indicators):
                return AgentStatus[status.upper()]
        
        return AgentStatus.BUSY


class SessionAnalyzer:
    """Analyzes tmux sessions to find Claude agents"""
    
    CLAUDE_INDICATORS = ["claude", "Claude", "node"]
    
    def __init__(self, tmux_executor: TmuxCommandExecutor, health_checker: ClaudeHealthChecker):
        self.tmux = tmux_executor
        self.health_checker = health_checker
    
    def analyze_session(self, session_name: str, created: str, window_count: int) -> Session:
        """Analyze a single session and find its agents"""
        agents = self._find_agents_in_session(session_name)
        return Session(
            name=session_name,
            created=created,
            windows=window_count,
            agents=agents
        )
    
    def _find_agents_in_session(self, session_name: str) -> List[Agent]:
        """Find all Claude agents in a session"""
        agents = []
        windows = self.tmux.get_windows(session_name)
        
        for window_idx, window_name, process in windows:
            if self._is_claude_window(window_name, process):
                output = self.tmux.capture_pane(session_name, str(window_idx))
                status = self.health_checker.check_health(output)
                
                agents.append(Agent(
                    window=window_idx,
                    name=window_name,
                    status=status,
                    process=process
                ))
        
        return agents
    
    def _is_claude_window(self, window_name: str, process: str) -> bool:
        """Check if a window contains a Claude agent"""
        combined = f"{window_name} {process}"
        return any(indicator in combined for indicator in self.CLAUDE_INDICATORS)


class RegistryManager:
    """Manages the session registry persistence"""
    
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
    
    def save_sessions(self, sessions: List[Session]) -> None:
        """Save sessions to registry file"""
        data = {
            "updated": datetime.now().isoformat(),
            "sessions": [self._session_to_dict(s) for s in sessions]
        }
        
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _session_to_dict(self, session: Session) -> Dict:
        """Convert session object to dictionary"""
        return {
            "name": session.name,
            "created": session.created,
            "windows": session.windows,
            "agents": [
                {
                    "window": agent.window,
                    "name": agent.name,
                    "status": agent.status.value,
                    "process": agent.process
                }
                for agent in session.agents
            ]
        }


class SystemHealthChecker:
    """Checks system dependencies and health"""
    
    @staticmethod
    def check_tmux() -> bool:
        """Check if tmux is available"""
        try:
            TmuxCommandExecutor.run_command(["tmux", "-V"])
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @staticmethod
    def check_claude() -> bool:
        """Check if Claude is available"""
        # Try to find Claude using the get_claude_command.sh script
        script_dir = Path(__file__).parent
        claude_script = script_dir / "get_claude_command.sh"
        
        if claude_script.exists():
            try:
                result = subprocess.run(
                    [str(claude_script)],
                    capture_output=True,
                    text=True,
                    check=False
                )
                return result.returncode == 0
            except Exception:
                pass
        
        # Fallback to direct check
        try:
            subprocess.run(["claude", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


class StatusFormatter:
    """Formats status output for display"""
    
    COLORS = {
        "red": "\033[0;31m",
        "green": "\033[0;32m",
        "yellow": "\033[1;33m",
        "blue": "\033[0;34m",
        "reset": "\033[0m"
    }
    
    STATUS_COLORS = {
        AgentStatus.READY: "green",
        AgentStatus.BUSY: "yellow",
        AgentStatus.ERROR: "red",
        AgentStatus.UNKNOWN: "blue"
    }
    
    @classmethod
    def format_status(cls, sessions: List[Session], detailed: bool = False) -> None:
        """Format and print status information"""
        if not sessions:
            print(f"{cls.COLORS['yellow']}No active sessions found{cls.COLORS['reset']}")
            return
        
        print(f"\n{cls.COLORS['blue']}🎯 Tmux Orchestrator Status{cls.COLORS['reset']}")
        print(f"{'='*50}")
        
        total_agents = sum(len(s.agents) for s in sessions)
        print(f"Active Sessions: {len(sessions)}")
        print(f"Total Agents: {total_agents}\n")
        
        for session in sessions:
            cls._format_session(session, detailed)
    
    @classmethod
    def _format_session(cls, session: Session, detailed: bool) -> None:
        """Format a single session"""
        print(f"{cls.COLORS['green']}📁 {session.name}{cls.COLORS['reset']}")
        print(f"   Windows: {session.windows}")
        print(f"   Agents: {len(session.agents)}")
        
        if detailed and session.agents:
            for agent in session.agents:
                status_color = cls.COLORS[cls.STATUS_COLORS[agent.status]]
                print(f"   - Window {agent.window}: {agent.name} "
                      f"[{status_color}{agent.status.value}{cls.COLORS['reset']}]")
        print()


class ClaudeOrchestrator:
    """Main orchestrator class - coordinates all components"""
    
    def __init__(self):
        # Security check
        self.base_dir = Path(__file__).parent.resolve()
        if not (self.base_dir / "claude_control.py").exists():
            raise RuntimeError("Security check failed: claude_control.py not found in expected location")
        
        # Initialize components
        self.tmux = TmuxCommandExecutor()
        self.health_checker = ClaudeHealthChecker()
        self.analyzer = SessionAnalyzer(self.tmux, self.health_checker)
        self.registry = RegistryManager(self.base_dir / "registry" / "sessions.json")
        self.health = SystemHealthChecker()
        self.formatter = StatusFormatter()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_active_sessions(self) -> List[Session]:
        """Get all active tmux sessions with Claude agents"""
        sessions = []
        
        for session_name, created, windows in self.tmux.get_sessions():
            session = self.analyzer.analyze_session(session_name, created, windows)
            sessions.append(session)
        
        return sessions
    
    def status(self, detailed: bool = False) -> None:
        """Display current status"""
        sessions = self.get_active_sessions()
        self.formatter.format_status(sessions, detailed)
        self.registry.save_sessions(sessions)
    
    def health_check(self) -> Dict:
        """Run system health check"""
        sessions = self.get_active_sessions()
        tmux_ok = self.health.check_tmux()
        claude_ok = self.health.check_claude()
        
        issues = []
        if not tmux_ok:
            issues.append("tmux not found")
        if not claude_ok:
            issues.append("claude command not found")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "tmux_available": tmux_ok,
            "claude_available": claude_ok,
            "active_sessions": len(sessions),
            "total_agents": sum(len(s.agents) for s in sessions),
            "issues": issues
        }


def main():
    """Main entry point"""
    try:
        orchestrator = ClaudeOrchestrator()
        
        if len(sys.argv) == 1:
            orchestrator.status()
        elif sys.argv[1] == "status":
            detailed = len(sys.argv) > 2 and sys.argv[2] == "detailed"
            orchestrator.status(detailed)
        elif sys.argv[1] == "health":
            health = orchestrator.health_check()
            print(json.dumps(health, indent=2))
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Usage: claude_control.py [status [detailed]|health]")
            sys.exit(1)
    
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()