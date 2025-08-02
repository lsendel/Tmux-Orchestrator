#!/usr/bin/env python3
"""
Simplified Tmux Utils - Phase 2 Implementation
Consolidates 10 classes into 1 main component
"""

import subprocess
import logging
from typing import List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


# Simple window type constants instead of enum
class WindowType:
    """Window type constants"""
    CLAUDE = "claude"
    SERVER = "server"
    SHELL = "shell"
    OTHER = "other"


# Keep dataclasses - they're not over-engineered
@dataclass
class TmuxWindow:
    """Represents a tmux window"""
    index: int
    name: str
    command: str
    type: str = WindowType.OTHER


@dataclass
class TmuxSession:
    """Represents a tmux session"""
    name: str
    created: str
    windows: List[TmuxWindow]


class TmuxManager:
    """Consolidated tmux operations manager"""

    # Merge InputValidator constants
    INVALID_CHARS = ["'", '"', ";", "&", "|", "$", "`", "\\", "(", ")", "<", ">", "*", "?", "[", "]", "{", "}", "!", "#"]

    # Window type patterns (from SessionDiscovery)
    WINDOW_PATTERNS = {
        WindowType.CLAUDE: ["claude", "Claude", "node"],
        WindowType.SERVER: ["dev", "server", "run", "npm", "yarn", "uvicorn", "django"],
        WindowType.SHELL: ["zsh", "bash", "sh", "fish"]
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # === Validation methods (from InputValidator) ===

    def validate_session_name(self, name: str) -> bool:
        """Validate session name is safe"""
        if not name or not name.strip():
            return False
        return not any(char in name for char in self.INVALID_CHARS)

    def validate_window_index(self, index: Any) -> bool:
        """Validate window index"""
        try:
            idx = int(index)
            return idx >= 0
        except (ValueError, TypeError):
            return False

    def sanitize_keys(self, keys: str) -> str:
        """Sanitize keys to send"""
        # Simple validation - just escape quotes
        return keys.replace("'", "'\"'\"'")

    # === Command execution (from TmuxCommandExecutor) ===

    def execute_command(self, command: List[str], check: bool = True) -> Optional[subprocess.CompletedProcess]:
        """Execute a tmux command"""
        try:
            self.logger.debug(f"Executing: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            if check:
                self.logger.error(f"Command failed: {e}")
                raise
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise

    # === Session discovery (from SessionDiscovery) ===

    def get_all_sessions(self) -> List[TmuxSession]:
        """Get all tmux sessions with their windows"""
        sessions = []

        # Get sessions
        result = self.execute_command(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_created}"]
        )

        if not result or not result.stdout:
            return sessions

        for line in result.stdout.strip().split('\n'):
            if not line or ':' not in line:
                continue

            parts = line.split(':', 1)
            session_name = parts[0]
            created = parts[1] if len(parts) > 1 else ""

            # Get windows for this session
            windows = self._get_session_windows(session_name)

            sessions.append(TmuxSession(
                name=session_name,
                created=created,
                windows=windows
            ))

        return sessions

    def _get_session_windows(self, session_name: str) -> List[TmuxWindow]:
        """Get windows for a specific session"""
        windows = []

        result = self.execute_command(
            ["tmux", "list-windows", "-t", session_name, "-F",
             "#{window_index}:#{window_name}:#{pane_current_command}"],
            check=False
        )

        if not result or result.returncode != 0 or not result.stdout:
            return windows

        for line in result.stdout.strip().split('\n'):
            if not line or ':' not in line:
                continue

            parts = line.split(':', 2)
            if len(parts) >= 2:
                try:
                    index = int(parts[0])
                    name = parts[1]
                    command = parts[2] if len(parts) > 2 else ""
                    window_type = self._determine_window_type(name, command)

                    windows.append(TmuxWindow(
                        index=index,
                        name=name,
                        command=command,
                        type=window_type
                    ))
                except ValueError:
                    self.logger.warning(f"Invalid window format: {line}")

        return windows

    def _determine_window_type(self, name: str, command: str) -> str:
        """Determine the type of window"""
        search_text = f"{name} {command}".lower()

        for window_type, patterns in self.WINDOW_PATTERNS.items():
            if any(pattern.lower() in search_text for pattern in patterns):
                return window_type

        return WindowType.OTHER

    # === Window operations (from WindowOperations) ===

    def send_keys_to_window(self, session: str, window: int, keys: str) -> bool:
        """Send keys to a specific window"""
        # Validate inputs
        if not self.validate_session_name(session):
            self.logger.error(f"Invalid session name: {session}")
            return False

        if not self.validate_window_index(window):
            self.logger.error(f"Invalid window index: {window}")
            return False

        # Sanitize and send keys
        safe_keys = self.sanitize_keys(keys)
        result = self.execute_command(
            ["tmux", "send-keys", "-t", f"{session}:{window}", safe_keys],
            check=False
        )

        return result is not None and result.returncode == 0

    def capture_window_output(self, session: str, window: int, lines: int = 50) -> Optional[str]:
        """Capture output from a window"""
        if not self.validate_session_name(session) or not self.validate_window_index(window):
            return None

        # Limit lines to reasonable amount
        lines = min(lines, 1000)

        result = self.execute_command(
            ["tmux", "capture-pane", "-t", f"{session}:{window}", "-p", "-S", f"-{lines}"],
            check=False
        )

        if result and result.returncode == 0:
            return result.stdout
        return None

    # === Session operations (from SessionOperations) ===

    def create_session(self, name: str, start_dir: Optional[str] = None) -> bool:
        """Create a new tmux session"""
        if not self.validate_session_name(name):
            self.logger.error(f"Invalid session name: {name}")
            return False

        command = ["tmux", "new-session", "-d", "-s", name]
        if start_dir and Path(start_dir).exists():
            command.extend(["-c", start_dir])

        result = self.execute_command(command, check=False)
        return result is not None and result.returncode == 0

    def add_window(self, session: str, name: str, start_dir: Optional[str] = None) -> bool:
        """Add a window to a session"""
        if not self.validate_session_name(session):
            return False

        command = ["tmux", "new-window", "-t", session, "-n", name]
        if start_dir and Path(start_dir).exists():
            command.extend(["-c", start_dir])

        result = self.execute_command(command, check=False)
        return result is not None and result.returncode == 0

    # === High-level orchestration methods ===

    def create_project_session(self, project_name: str, project_path: str) -> bool:
        """Create a complete project session with standard windows"""
        # Validate inputs
        if not self.validate_session_name(project_name):
            self.logger.error(f"Invalid project name: {project_name}")
            return False

        project_dir = Path(project_path)
        if not project_dir.exists():
            self.logger.error(f"Project path does not exist: {project_path}")
            return False

        try:
            # Create session
            if not self.create_session(project_name, str(project_dir)):
                return False

            # Rename first window
            self.execute_command(
                ["tmux", "rename-window", "-t", f"{project_name}:0", "Claude-Agent"]
            )

            # Add standard windows
            self.add_window(project_name, "Shell", str(project_dir))
            self.add_window(project_name, "Server", str(project_dir))

            self.logger.info(f"Created project session: {project_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create project session: {e}")
            return False

    def send_message(self, session: str, window: int, message: str) -> bool:
        """Send a message to a window (convenience method)"""
        # Send the message
        if not self.send_keys_to_window(session, window, message):
            return False

        # Send Enter key
        return self.send_keys_to_window(session, window, "Enter")

    def get_window_output(self, session: str, window: int, lines: int = 50) -> Optional[str]:
        """Get recent output from a window (convenience method)"""
        return self.capture_window_output(session, window, lines)


def main():
    """Simple CLI interface"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    manager = TmuxManager()

    if len(sys.argv) < 2:
        print("Usage: tmux_utils.py [list|create|send] [args...]")
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "list":
            sessions = manager.get_all_sessions()
            for session in sessions:
                print(f"\n📁 {session.name}")
                print(f"   Created: {session.created}")
                print(f"   Windows: {len(session.windows)}")
                for window in session.windows:
                    print(f"   - [{window.index}] {window.name} ({window.type})")

        elif command == "create" and len(sys.argv) >= 4:
            project_name = sys.argv[2]
            project_path = sys.argv[3]
            success = manager.create_project_session(project_name, project_path)
            if success:
                print(f"✅ Created session: {project_name}")
            else:
                print("❌ Failed to create session")
                sys.exit(1)

        elif command == "send" and len(sys.argv) >= 5:
            session = sys.argv[2]
            window = int(sys.argv[3])
            message = sys.argv[4]
            success = manager.send_message(session, window, message)
            if success:
                print(f"✅ Sent message to {session}:{window}")
            else:
                print("❌ Failed to send message")
                sys.exit(1)

        else:
            print("Invalid command or arguments")
            print("Usage:")
            print("  tmux_utils.py list")
            print("  tmux_utils.py create <session> <path>")
            print("  tmux_utils.py send <session> <window> <message>")
            sys.exit(1)

    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
