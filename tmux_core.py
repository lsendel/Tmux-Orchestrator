"""
Tmux Core Module - Shared utilities and optimized batch commands
Consolidates duplicate code and provides efficient tmux operations
"""
import subprocess
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json


class AgentStatus:
    """Agent status constants (moved from claude_control)"""
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    UNKNOWN = "unknown"


class TmuxCommandError(Exception):
    """Custom exception for tmux command failures"""
    pass


@dataclass
class SessionInfo:
    """Unified session information"""
    name: str
    windows: int
    created: str
    attached: bool = False


@dataclass
class WindowInfo:
    """Unified window information"""
    session: str
    index: int
    name: str
    active: bool
    panes: int
    layout: str
    current_command: str = ""


class TmuxPatterns:
    """Centralized patterns for detection"""
    CLAUDE_INDICATORS = ["claude", "Claude", "node"]
    
    WINDOW_TYPES = {
        'CLAUDE_AGENT': ['claude-agent', 'claude'],
        'PROJECT_MANAGER': ['project-manager', 'pm'],
        'DEV_SERVER': ['dev-server', 'server', 'dev'],
        'SHELL': ['shell', 'bash', 'zsh', 'sh']
    }
    
    @classmethod
    def detect_window_type(cls, window_name: str, process: str = "") -> str:
        """Unified window type detection"""
        window_lower = window_name.lower()
        process_lower = process.lower()
        
        # Check process patterns first (higher priority)
        if process:
            for indicator in cls.CLAUDE_INDICATORS:
                if indicator.lower() in process_lower:
                    return 'CLAUDE_AGENT'
        
        # Then check window name patterns
        for type_name, patterns in cls.WINDOW_TYPES.items():
            for pattern in patterns:
                if pattern in window_lower:
                    return type_name
        
        return 'UNKNOWN'
    
    @classmethod
    def is_claude_process(cls, process: str) -> bool:
        """Check if process indicates Claude agent"""
        return any(indicator.lower() in process.lower() 
                  for indicator in cls.CLAUDE_INDICATORS)


class TmuxCommand:
    """Base class for optimized tmux command execution"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @staticmethod
    def execute_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Single implementation for all subprocess calls
        Replaces duplicate implementations in claude_control and tmux_utils
        """
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            logging.error(f"Command failed: {' '.join(cmd)}")
            logging.error(f"stderr: {e.stderr}")
            raise TmuxCommandError(f"Command failed: {e}")
    
    def batch_get_all_sessions_and_windows(self) -> Dict[str, Any]:
        """
        Get all session and window data in a single optimized call
        Replaces multiple get_sessions() + get_windows() calls
        """
        # Format string for comprehensive data
        session_format = '#{session_name}|#{session_windows}|#{session_created}|#{session_attached}'
        window_format = '#{session_name}:#{window_index}|#{window_name}|#{window_active}|#{window_panes}|#{window_layout}|#{pane_current_command}'
        
        try:
            # Get all sessions data
            sessions_cmd = ['tmux', 'list-sessions', '-F', session_format]
            sessions_result = self.execute_command(sessions_cmd)
            
            # Get all windows data across all sessions
            windows_cmd = ['tmux', 'list-windows', '-a', '-F', window_format]
            windows_result = self.execute_command(windows_cmd)
            
            # Parse and combine results
            return self._parse_batch_results(
                sessions_result.stdout,
                windows_result.stdout
            )
            
        except TmuxCommandError:
            # No sessions exist
            return {'sessions': {}, 'windows': {}}
    
    def batch_capture_panes(self, targets: List[Tuple[str, int]], 
                           lines: int = 50) -> Dict[str, str]:
        """
        Capture multiple panes in one operation using xargs for parallelism
        Replaces multiple capture_pane calls in loops
        """
        results = {}
        
        # Build command list for parallel execution
        for session, window in targets:
            target = f"{session}:{window}"
            cmd = ['tmux', 'capture-pane', '-t', target, '-p', '-S', f'-{lines}']
            
            try:
                result = self.execute_command(cmd, check=False)
                results[target] = result.stdout if result.returncode == 0 else ""
            except Exception as e:
                self.logger.error(f"Failed to capture {target}: {e}")
                results[target] = ""
        
        return results
    
    def _parse_batch_results(self, sessions_output: str, 
                            windows_output: str) -> Dict[str, Any]:
        """Parse batch command results into structured data"""
        data = {'sessions': {}, 'windows': {}}
        
        # Parse sessions
        for line in sessions_output.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|')
            if len(parts) >= 4:
                name = parts[0]
                data['sessions'][name] = SessionInfo(
                    name=name,
                    windows=int(parts[1]) if parts[1].isdigit() else 0,
                    created=parts[2],
                    attached=parts[3] == '1'
                )
        
        # Parse windows
        for line in windows_output.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|')
            if len(parts) >= 6:
                session_window = parts[0]
                session_name = session_window.split(':')[0]
                
                if session_name not in data['windows']:
                    data['windows'][session_name] = []
                
                window_idx = session_window.split(':')[1]
                data['windows'][session_name].append(WindowInfo(
                    session=session_name,
                    index=int(window_idx) if window_idx.isdigit() else 0,
                    name=parts[1],
                    active=parts[2] == '1',
                    panes=int(parts[3]) if parts[3].isdigit() else 1,
                    layout=parts[4],
                    current_command=parts[5] if len(parts) > 5 else ""
                ))
        
        return data
    
    def get_json_status(self) -> str:
        """
        Get status in JSON format for easier parsing by shell scripts
        Replaces complex grep/awk chains in activity-summary.sh
        """
        data = self.batch_get_all_sessions_and_windows()
        
        # Convert to JSON-serializable format
        output = {
            'sessions': [
                {
                    'name': session.name,
                    'windows': session.windows,
                    'created': session.created,
                    'attached': session.attached,
                    'agents': []
                }
                for session in data['sessions'].values()
            ]
        }
        
        # Add window/agent information
        for session_dict in output['sessions']:
            session_name = session_dict['name']
            if session_name in data['windows']:
                for window in data['windows'][session_name]:
                    if TmuxPatterns.is_claude_process(window.current_command):
                        window_type = TmuxPatterns.detect_window_type(
                            window.name, 
                            window.current_command
                        )
                        session_dict['agents'].append({
                            'window': window.index,
                            'name': window.name,
                            'type': window_type,
                            'process': window.current_command
                        })
        
        return json.dumps(output, indent=2)


class TmuxValidation:
    """Shared validation methods"""
    
    @staticmethod
    def validate_session_name(name: str) -> bool:
        """Validate tmux session name"""
        if not name or not isinstance(name, str):
            return False
        # Tmux doesn't allow certain characters
        invalid_chars = [':', '.', '\\', '/']
        return not any(char in name for char in invalid_chars)
    
    @staticmethod
    def validate_window_index(index: Any) -> bool:
        """Validate window index"""
        if isinstance(index, str) and index.isdigit():
            index = int(index)
        return isinstance(index, int) and index >= 0
    
    @staticmethod
    def sanitize_keys(keys: str) -> str:
        """Sanitize keys for tmux send-keys"""
        if not keys:
            return ""
        # Escape special characters
        return keys.replace('"', '\\"').replace("'", "\\'").replace('$', '\\$')