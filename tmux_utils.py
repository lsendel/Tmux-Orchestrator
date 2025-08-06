#!/usr/bin/env python3
"""
Optimized Tmux Utils - Eliminates duplicate code by inheriting from tmux_core
Focuses on high-level operations while using shared base functionality
"""

import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

# Import shared components
from tmux_core import (
    TmuxCommand, TmuxPatterns, TmuxValidation,
    TmuxCommandError, WindowInfo, SessionInfo
)


# Keep existing dataclasses for compatibility
@dataclass
class TmuxWindow:
    """Window information"""
    index: int
    name: str
    active: bool
    panes: int
    layout: str


@dataclass  
class TmuxSession:
    """Session information"""
    name: str
    windows: int
    created: str
    attached: bool


class TmuxManager(TmuxCommand):
    """
    High-level tmux management operations
    Inherits from TmuxCommand to eliminate duplicate code
    """
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def create_session(self, name: str, start_directory: Optional[str] = None) -> bool:
        """Create a new tmux session"""
        # Use shared validation
        if not TmuxValidation.validate_session_name(name):
            self.logger.error(f"Invalid session name: {name}")
            return False
        
        cmd = ["tmux", "new-session", "-d", "-s", name]
        if start_directory and Path(start_directory).exists():
            cmd.extend(["-c", start_directory])
        
        try:
            self.execute_command(cmd)
            self.logger.info(f"Created session: {name}")
            return True
        except TmuxCommandError as e:
            self.logger.error(f"Failed to create session: {e}")
            return False
    
    def add_window(self, session_name: str, window_name: str,
                   start_directory: Optional[str] = None) -> Optional[int]:
        """Add a new window to a session"""
        if not TmuxValidation.validate_session_name(session_name):
            self.logger.error(f"Invalid session name: {session_name}")
            return None
        
        cmd = ["tmux", "new-window", "-t", session_name, "-n", window_name, "-P", "-F", "#{window_index}"]
        if start_directory and Path(start_directory).exists():
            cmd.extend(["-c", start_directory])
        
        try:
            result = self.execute_command(cmd)
            window_index = int(result.stdout.strip())
            self.logger.info(f"Created window {window_index} in session {session_name}")
            return window_index
        except (TmuxCommandError, ValueError) as e:
            self.logger.error(f"Failed to create window: {e}")
            return None
    
    def send_keys_to_window(self, session_name: str, window_index: int, keys: str) -> bool:
        """Send keys to a specific window"""
        if not TmuxValidation.validate_session_name(session_name):
            self.logger.error(f"Invalid session name: {session_name}")
            return False
            
        if not TmuxValidation.validate_window_index(window_index):
            self.logger.error(f"Invalid window index: {window_index}")
            return False
        
        # Use shared key sanitization
        sanitized_keys = TmuxValidation.sanitize_keys(keys)
        target = f"{session_name}:{window_index}"
        
        try:
            self.execute_command(["tmux", "send-keys", "-t", target, sanitized_keys])
            return True
        except TmuxCommandError as e:
            self.logger.error(f"Failed to send keys to {target}: {e}")
            return False
    
    def send_message(self, session_name: str, window_index: int, message: str,
                    enter: bool = True) -> bool:
        """Send a message to a window with optional Enter key"""
        # First send the message
        if not self.send_keys_to_window(session_name, window_index, message):
            return False
        
        # Then send Enter if requested
        if enter:
            target = f"{session_name}:{window_index}"
            try:
                self.execute_command(["tmux", "send-keys", "-t", target, "Enter"])
                return True
            except TmuxCommandError:
                return False
        
        return True
    
    def get_all_sessions(self) -> List[TmuxSession]:
        """
        Get all sessions using optimized batch command
        Returns compatible TmuxSession objects
        """
        data = self.batch_get_all_sessions_and_windows()
        
        # Convert to legacy format for compatibility
        return [
            TmuxSession(
                name=session.name,
                windows=session.windows,
                created=session.created,
                attached=session.attached
            )
            for session in data['sessions'].values()
        ]
    
    def get_session_windows(self, session_name: str) -> List[TmuxWindow]:
        """
        Get windows for a session using batch data
        Returns compatible TmuxWindow objects
        """
        data = self.batch_get_all_sessions_and_windows()
        
        if session_name not in data['windows']:
            return []
        
        # Convert to legacy format
        return [
            TmuxWindow(
                index=window.index,
                name=window.name,
                active=window.active,
                panes=window.panes,
                layout=window.layout
            )
            for window in data['windows'][session_name]
        ]
    
    def capture_window_output(self, session_name: str, window_index: int,
                             lines: int = 50) -> str:
        """Capture output from a window"""
        if not TmuxValidation.validate_session_name(session_name):
            return ""
            
        if not TmuxValidation.validate_window_index(window_index):
            return ""
        
        # Use batch capture for single target
        results = self.batch_capture_panes([(session_name, window_index)], lines)
        target = f"{session_name}:{window_index}"
        
        return results.get(target, "")
    
    def get_window_output(self, session_name: str, window_index: int,
                         lines: int = 50) -> List[str]:
        """Get window output as list of lines"""
        output = self.capture_window_output(session_name, window_index, lines)
        return output.split('\n') if output else []
    
    def determine_window_type(self, window_name: str) -> str:
        """
        Determine window type using shared patterns
        Delegates to TmuxPatterns for consistency
        """
        return TmuxPatterns.detect_window_type(window_name)
    
    def create_project_session(self, project_name: str, project_path: str) -> bool:
        """Create a project session with standard windows"""
        # Validate inputs
        if not TmuxValidation.validate_session_name(project_name):
            self.logger.error(f"Invalid project name: {project_name}")
            return False
        
        if not Path(project_path).exists():
            self.logger.error(f"Project path does not exist: {project_path}")
            return False
        
        try:
            # Create session
            if not self.create_session(project_name, project_path):
                return False
            
            # Rename first window
            self.execute_command([
                "tmux", "rename-window", "-t", f"{project_name}:0", "Claude-Agent"
            ])
            
            # Add standard windows
            self.add_window(project_name, "Shell", project_path)
            self.add_window(project_name, "Dev-Server", project_path)
            
            self.logger.info(f"Created project session: {project_name}")
            return True
            
        except TmuxCommandError as e:
            self.logger.error(f"Failed to create project session: {e}")
            return False


def main():
    """Main entry point with JSON support"""
    import sys
    import json
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: tmux_utils.py <command> [args...]")
        print("Commands: list, create, send, json")
        sys.exit(1)
    
    manager = TmuxManager()
    command = sys.argv[1]
    
    try:
        if command == "list":
            sessions = manager.get_all_sessions()
            for session in sessions:
                print(f"{session.name}: {session.windows} windows, "
                      f"created {session.created}")
                
        elif command == "create":
            if len(sys.argv) < 4:
                print("Usage: tmux_utils.py create <name> <path>")
                sys.exit(1)
            success = manager.create_project_session(sys.argv[2], sys.argv[3])
            sys.exit(0 if success else 1)
            
        elif command == "send":
            if len(sys.argv) < 5:
                print("Usage: tmux_utils.py send <session> <window> <message>")
                sys.exit(1)
            success = manager.send_message(
                sys.argv[2], int(sys.argv[3]), sys.argv[4]
            )
            sys.exit(0 if success else 1)
            
        elif command == "json":
            # Output sessions in JSON format
            data = manager.batch_get_all_sessions_and_windows()
            print(json.dumps({
                'sessions': [
                    {
                        'name': s.name,
                        'windows': s.windows,
                        'created': s.created,
                        'attached': s.attached
                    }
                    for s in data['sessions'].values()
                ]
            }, indent=2))
            
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()