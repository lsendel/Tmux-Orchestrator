#!/usr/bin/env python3
"""
Tmux Utilities - Refactored for Clean Code
Provides safe tmux operations with input validation
"""

import subprocess
import shlex
import re
import logging
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class WindowType(Enum):
    """Types of windows in a project"""
    CLAUDE = "claude"
    SHELL = "shell"
    SERVER = "server"
    OTHER = "other"


@dataclass
class TmuxWindow:
    """Data class representing a tmux window"""
    index: int
    name: str
    type: WindowType
    current_command: str = ""
    pane_count: int = 1


@dataclass
class TmuxSession:
    """Data class representing a tmux session"""
    name: str
    windows: List[TmuxWindow]
    attached: bool = False
    created_time: Optional[str] = None


class InputValidator:
    """Validates input for security"""
    
    # Regex patterns for validation
    SESSION_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    WINDOW_INDEX_PATTERN = re.compile(r'^\d+$')
    
    @classmethod
    def validate_session_name(cls, session_name: str) -> str:
        """Validate and sanitize session name"""
        if not session_name:
            raise ValueError("Session name cannot be empty")
        
        if not cls.SESSION_NAME_PATTERN.match(session_name):
            raise ValueError(f"Invalid session name format: {session_name}")
        
        return session_name
    
    @classmethod
    def validate_window_index(cls, window_index: str) -> str:
        """Validate window index"""
        if not cls.WINDOW_INDEX_PATTERN.match(str(window_index)):
            raise ValueError(f"Invalid window index: {window_index}")
        
        return str(window_index)
    
    @classmethod
    def sanitize_keys(cls, keys: str) -> str:
        """Sanitize keys for safe sending"""
        # Use shlex.quote for shell escaping
        return shlex.quote(keys)


class TmuxCommandBuilder:
    """Builds tmux commands safely"""
    
    @staticmethod
    def build_list_sessions() -> List[str]:
        """Build command to list sessions"""
        return ["tmux", "list-sessions", "-F", 
                "#{session_name}:#{session_attached}:#{session_created}"]
    
    @staticmethod
    def build_list_windows(session: str) -> List[str]:
        """Build command to list windows"""
        return ["tmux", "list-windows", "-t", session, "-F",
                "#{window_index}:#{window_name}:#{pane_current_command}:#{window_panes}"]
    
    @staticmethod
    def build_send_keys(session: str, window: str, keys: str) -> List[str]:
        """Build command to send keys"""
        target = f"{session}:{window}"
        return ["tmux", "send-keys", "-t", target, keys]
    
    @staticmethod
    def build_capture_pane(session: str, window: str, lines: int) -> List[str]:
        """Build command to capture pane"""
        target = f"{session}:{window}"
        return ["tmux", "capture-pane", "-t", target, "-p", "-S", f"-{lines}"]
    
    @staticmethod
    def build_new_session(name: str, path: str) -> List[str]:
        """Build command to create new session"""
        return ["tmux", "new-session", "-d", "-s", name, "-c", path]
    
    @staticmethod
    def build_new_window(session: str, name: str, path: str) -> List[str]:
        """Build command to create new window"""
        return ["tmux", "new-window", "-t", session, "-n", name, "-c", path]


class TmuxCommandExecutor:
    """Executes tmux commands with error handling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def execute(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute a tmux command"""
        try:
            self.logger.debug(f"Executing: {' '.join(command)}")
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check
            )
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {e}")
            if check:
                raise
            return e
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise


class SessionDiscovery:
    """Discovers and analyzes tmux sessions"""
    
    def __init__(self, executor: TmuxCommandExecutor):
        self.executor = executor
        self.logger = logging.getLogger(__name__)
    
    def get_all_sessions(self) -> List[TmuxSession]:
        """Get all tmux sessions"""
        command = TmuxCommandBuilder.build_list_sessions()
        result = self.executor.execute(command, check=False)
        
        if result.returncode != 0:
            return []
        
        sessions = []
        for line in result.stdout.strip().split('\n'):
            if line:
                session = self._parse_session_line(line)
                if session:
                    sessions.append(session)
        
        return sessions
    
    def _parse_session_line(self, line: str) -> Optional[TmuxSession]:
        """Parse a session line from tmux output"""
        parts = line.split(':', 2)
        if len(parts) >= 2:
            name = parts[0]
            attached = parts[1] == '1'
            created = parts[2] if len(parts) > 2 else None
            
            windows = self._get_session_windows(name)
            return TmuxSession(
                name=name,
                windows=windows,
                attached=attached,
                created_time=created
            )
        return None
    
    def _get_session_windows(self, session_name: str) -> List[TmuxWindow]:
        """Get windows for a session"""
        command = TmuxCommandBuilder.build_list_windows(session_name)
        result = self.executor.execute(command, check=False)
        
        if result.returncode != 0:
            return []
        
        windows = []
        for line in result.stdout.strip().split('\n'):
            if line:
                window = self._parse_window_line(line)
                if window:
                    windows.append(window)
        
        return windows
    
    def _parse_window_line(self, line: str) -> Optional[TmuxWindow]:
        """Parse a window line from tmux output"""
        parts = line.split(':', 3)
        if len(parts) >= 3:
            return TmuxWindow(
                index=int(parts[0]),
                name=parts[1],
                type=self._determine_window_type(parts[1], parts[2]),
                current_command=parts[2],
                pane_count=int(parts[3]) if len(parts) > 3 else 1
            )
        return None
    
    def _determine_window_type(self, name: str, command: str) -> WindowType:
        """Determine the type of window"""
        combined = f"{name} {command}".lower()
        
        if any(term in combined for term in ["claude", "node"]):
            return WindowType.CLAUDE
        elif any(term in combined for term in ["shell", "bash", "zsh"]):
            return WindowType.SHELL
        elif any(term in combined for term in ["server", "dev", "npm", "yarn"]):
            return WindowType.SERVER
        else:
            return WindowType.OTHER


class WindowOperations:
    """High-level window operations"""
    
    def __init__(self, executor: TmuxCommandExecutor, validator: InputValidator):
        self.executor = executor
        self.validator = validator
        self.logger = logging.getLogger(__name__)
    
    def send_keys_to_window(self, session: str, window: str, keys: str) -> bool:
        """Send keys to a specific window"""
        try:
            # Validate inputs
            session = self.validator.validate_session_name(session)
            window = self.validator.validate_window_index(window)
            safe_keys = self.validator.sanitize_keys(keys)
            
            # Build and execute command
            command = TmuxCommandBuilder.build_send_keys(session, window, safe_keys)
            result = self.executor.execute(command)
            
            return result.returncode == 0
        
        except ValueError as e:
            self.logger.error(f"Validation error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to send keys: {e}")
            return False
    
    def capture_window_output(self, session: str, window: str, lines: int = 50) -> str:
        """Capture output from a window"""
        try:
            # Validate inputs
            session = self.validator.validate_session_name(session)
            window = self.validator.validate_window_index(window)
            
            # Limit lines to reasonable range
            lines = max(1, min(lines, 1000))
            
            # Build and execute command
            command = TmuxCommandBuilder.build_capture_pane(session, window, lines)
            result = self.executor.execute(command)
            
            return result.stdout if result.returncode == 0 else ""
        
        except ValueError as e:
            self.logger.error(f"Validation error: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Failed to capture output: {e}")
            return ""


class SessionOperations:
    """High-level session operations"""
    
    def __init__(self, executor: TmuxCommandExecutor, validator: InputValidator):
        self.executor = executor
        self.validator = validator
        self.logger = logging.getLogger(__name__)
    
    def create_session(self, name: str, path: str) -> bool:
        """Create a new tmux session"""
        try:
            # Validate session name
            name = self.validator.validate_session_name(name)
            
            # Build and execute command
            command = TmuxCommandBuilder.build_new_session(name, path)
            result = self.executor.execute(command)
            
            return result.returncode == 0
        
        except ValueError as e:
            self.logger.error(f"Validation error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            return False
    
    def add_window(self, session: str, window_name: str, path: str) -> bool:
        """Add a window to existing session"""
        try:
            # Validate session name
            session = self.validator.validate_session_name(session)
            
            # Build and execute command
            command = TmuxCommandBuilder.build_new_window(session, window_name, path)
            result = self.executor.execute(command)
            
            return result.returncode == 0
        
        except ValueError as e:
            self.logger.error(f"Validation error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to add window: {e}")
            return False


class TmuxOrchestrator:
    """Main orchestrator class combining all functionality"""
    
    def __init__(self):
        # Initialize components
        self.validator = InputValidator()
        self.executor = TmuxCommandExecutor()
        self.discovery = SessionDiscovery(self.executor)
        self.window_ops = WindowOperations(self.executor, self.validator)
        self.session_ops = SessionOperations(self.executor, self.validator)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_all_sessions(self) -> List[TmuxSession]:
        """Get all tmux sessions"""
        return self.discovery.get_all_sessions()
    
    def send_message(self, session: str, window: str, message: str) -> bool:
        """Send a message to a Claude agent"""
        return self.window_ops.send_keys_to_window(session, window, message)
    
    def get_window_output(self, session: str, window: str, lines: int = 50) -> str:
        """Get recent output from a window"""
        return self.window_ops.capture_window_output(session, window, lines)
    
    def create_project_session(self, project_name: str, project_path: str) -> bool:
        """Create a new project session"""
        return self.session_ops.create_session(project_name, project_path)
    
    def add_window_to_session(self, session: str, window_name: str, path: str) -> bool:
        """Add a window to an existing session"""
        return self.session_ops.add_window(session, window_name, path)


def main():
    """Main entry point for testing"""
    orchestrator = TmuxOrchestrator()
    
    # List all sessions
    sessions = orchestrator.get_all_sessions()
    
    print(f"Found {len(sessions)} sessions:")
    for session in sessions:
        print(f"\n📁 {session.name}")
        print(f"   Attached: {session.attached}")
        print(f"   Windows: {len(session.windows)}")
        
        for window in session.windows:
            print(f"   - Window {window.index}: {window.name} "
                  f"[{window.type.value}] ({window.current_command})")


if __name__ == "__main__":
    main()