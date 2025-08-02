#!/usr/bin/env python3
"""Unit tests for refactored tmux_utils.py"""

import unittest
from unittest.mock import patch, MagicMock, call
import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tmux_utils_refactored import (
    InputValidator, TmuxCommandBuilder, TmuxCommandExecutor,
    SessionDiscovery, WindowOperations, SessionOperations,
    TmuxOrchestrator, TmuxWindow, TmuxSession, WindowType
)


class TestInputValidator(unittest.TestCase):
    """Test the InputValidator class"""
    
    def test_validate_session_name_valid(self):
        """Test valid session names"""
        valid_names = ["test-session", "my_project", "Session123", "a", "A-B_C"]
        for name in valid_names:
            result = InputValidator.validate_session_name(name)
            self.assertEqual(result, name)
    
    def test_validate_session_name_invalid(self):
        """Test invalid session names"""
        invalid_names = ["test session", "my@project", "Session#123", "", "a/b", "a\\b"]
        for name in invalid_names:
            with self.assertRaises(ValueError):
                InputValidator.validate_session_name(name)
    
    def test_validate_session_name_empty(self):
        """Test empty session name"""
        with self.assertRaises(ValueError) as context:
            InputValidator.validate_session_name("")
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_validate_window_index_valid(self):
        """Test valid window indices"""
        valid_indices = ["0", "1", "10", "999"]
        for idx in valid_indices:
            result = InputValidator.validate_window_index(idx)
            self.assertEqual(result, idx)
    
    def test_validate_window_index_invalid(self):
        """Test invalid window indices"""
        invalid_indices = ["a", "1a", "-1", "1.5", ""]
        for idx in invalid_indices:
            with self.assertRaises(ValueError):
                InputValidator.validate_window_index(idx)
    
    def test_sanitize_keys(self):
        """Test key sanitization"""
        # Simple text - shlex.quote doesn't add quotes if not needed
        self.assertEqual(InputValidator.sanitize_keys("hello"), "hello")
        
        # Text with spaces - shlex.quote adds quotes
        self.assertEqual(InputValidator.sanitize_keys("hello world"), "'hello world'")
        
        # Special characters that need escaping
        result = InputValidator.sanitize_keys("echo $HOME")
        self.assertEqual(result, "'echo $HOME'")  # shlex.quote adds quotes for special chars


class TestTmuxCommandBuilder(unittest.TestCase):
    """Test the TmuxCommandBuilder class"""
    
    def test_build_list_sessions(self):
        """Test building list sessions command"""
        cmd = TmuxCommandBuilder.build_list_sessions()
        self.assertEqual(cmd[0], "tmux")
        self.assertEqual(cmd[1], "list-sessions")
        self.assertIn("session_name", cmd[3])
    
    def test_build_list_windows(self):
        """Test building list windows command"""
        cmd = TmuxCommandBuilder.build_list_windows("test-session")
        self.assertEqual(cmd[0], "tmux")
        self.assertEqual(cmd[1], "list-windows")
        self.assertEqual(cmd[3], "test-session")
        self.assertIn("window_index", cmd[5])
    
    def test_build_send_keys(self):
        """Test building send keys command"""
        cmd = TmuxCommandBuilder.build_send_keys("session", "0", "hello")
        self.assertEqual(cmd[0], "tmux")
        self.assertEqual(cmd[1], "send-keys")
        self.assertEqual(cmd[3], "session:0")
        self.assertEqual(cmd[4], "hello")
    
    def test_build_capture_pane(self):
        """Test building capture pane command"""
        cmd = TmuxCommandBuilder.build_capture_pane("session", "1", 50)
        self.assertEqual(cmd[0], "tmux")
        self.assertEqual(cmd[1], "capture-pane")
        self.assertEqual(cmd[3], "session:1")
        self.assertIn("-50", cmd)
    
    def test_build_new_session(self):
        """Test building new session command"""
        cmd = TmuxCommandBuilder.build_new_session("mysession", "/path/to/project")
        self.assertIn("new-session", cmd)
        self.assertIn("-s", cmd)
        self.assertIn("mysession", cmd)
        self.assertIn("/path/to/project", cmd)
    
    def test_build_new_window(self):
        """Test building new window command"""
        cmd = TmuxCommandBuilder.build_new_window("session", "Shell", "/path")
        self.assertIn("new-window", cmd)
        self.assertIn("session", cmd)
        self.assertIn("Shell", cmd)
        self.assertIn("/path", cmd)


class TestTmuxCommandExecutor(unittest.TestCase):
    """Test the TmuxCommandExecutor class"""
    
    def setUp(self):
        self.executor = TmuxCommandExecutor()
    
    @patch('subprocess.run')
    def test_execute_success(self, mock_run):
        """Test successful command execution"""
        mock_run.return_value = MagicMock(
            stdout="output",
            stderr="",
            returncode=0
        )
        
        result = self.executor.execute(["tmux", "list-sessions"])
        
        self.assertEqual(result.stdout, "output")
        self.assertEqual(result.returncode, 0)
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_execute_failure_with_check(self, mock_run):
        """Test failed command execution with check=True"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        with self.assertRaises(subprocess.CalledProcessError):
            self.executor.execute(["tmux", "invalid"], check=True)
    
    @patch('subprocess.run')
    def test_execute_failure_without_check(self, mock_run):
        """Test failed command execution with check=False"""
        error = subprocess.CalledProcessError(1, 'cmd')
        error.stdout = ""
        error.stderr = "error"
        mock_run.side_effect = error
        
        result = self.executor.execute(["tmux", "invalid"], check=False)
        self.assertEqual(result.returncode, 1)
    
    @patch('subprocess.run')
    @patch('logging.Logger.error')
    def test_execute_unexpected_error(self, mock_log, mock_run):
        """Test unexpected error during execution"""
        mock_run.side_effect = Exception("Unexpected")
        
        with self.assertRaises(Exception):
            self.executor.execute(["tmux", "test"])
        
        mock_log.assert_called()


class TestSessionDiscovery(unittest.TestCase):
    """Test the SessionDiscovery class"""
    
    def setUp(self):
        self.mock_executor = MagicMock()
        self.discovery = SessionDiscovery(self.mock_executor)
    
    def test_get_all_sessions_success(self):
        """Test getting all sessions successfully"""
        # Mock session list output
        self.mock_executor.execute.side_effect = [
            MagicMock(stdout="session1:0:123456\nsession2:1:123457\n", returncode=0),
            MagicMock(stdout="0:Window1:bash:1\n", returncode=0),
            MagicMock(stdout="0:Claude:node:1\n1:Shell:zsh:1\n", returncode=0)
        ]
        
        sessions = self.discovery.get_all_sessions()
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].name, "session1")
        self.assertFalse(sessions[0].attached)
        self.assertEqual(sessions[1].name, "session2")
        self.assertTrue(sessions[1].attached)
    
    def test_get_all_sessions_no_sessions(self):
        """Test when no sessions exist"""
        self.mock_executor.execute.return_value = MagicMock(returncode=1)
        
        sessions = self.discovery.get_all_sessions()
        self.assertEqual(sessions, [])
    
    def test_parse_session_line(self):
        """Test parsing session line"""
        self.mock_executor.execute.return_value = MagicMock(stdout="", returncode=0)
        
        session = self.discovery._parse_session_line("test:1:12345")
        self.assertEqual(session.name, "test")
        self.assertTrue(session.attached)
        self.assertEqual(session.created_time, "12345")
    
    def test_parse_window_line(self):
        """Test parsing window line"""
        window = self.discovery._parse_window_line("0:Claude-Agent:node:2")
        self.assertEqual(window.index, 0)
        self.assertEqual(window.name, "Claude-Agent")
        self.assertEqual(window.type, WindowType.CLAUDE)
        self.assertEqual(window.pane_count, 2)
    
    def test_determine_window_type(self):
        """Test window type determination"""
        # Claude windows
        self.assertEqual(
            self.discovery._determine_window_type("Claude", "node"),
            WindowType.CLAUDE
        )
        self.assertEqual(
            self.discovery._determine_window_type("Agent", "claude"),
            WindowType.CLAUDE
        )
        
        # Shell windows
        self.assertEqual(
            self.discovery._determine_window_type("Shell", "bash"),
            WindowType.SHELL
        )
        
        # Server windows
        self.assertEqual(
            self.discovery._determine_window_type("Dev", "npm"),
            WindowType.SERVER
        )
        
        # Other windows
        self.assertEqual(
            self.discovery._determine_window_type("Random", "vim"),
            WindowType.OTHER
        )


class TestWindowOperations(unittest.TestCase):
    """Test the WindowOperations class"""
    
    def setUp(self):
        self.mock_executor = MagicMock()
        self.mock_validator = InputValidator()
        self.window_ops = WindowOperations(self.mock_executor, self.mock_validator)
    
    def test_send_keys_to_window_success(self):
        """Test successful key sending"""
        self.mock_executor.execute.return_value = MagicMock(returncode=0)
        
        result = self.window_ops.send_keys_to_window("session", "0", "hello")
        
        self.assertTrue(result)
        self.mock_executor.execute.assert_called_once()
    
    def test_send_keys_to_window_invalid_session(self):
        """Test sending keys with invalid session name"""
        result = self.window_ops.send_keys_to_window("invalid session", "0", "hello")
        self.assertFalse(result)
    
    def test_send_keys_to_window_invalid_window(self):
        """Test sending keys with invalid window index"""
        result = self.window_ops.send_keys_to_window("session", "abc", "hello")
        self.assertFalse(result)
    
    @patch('logging.Logger.error')
    def test_send_keys_to_window_execution_error(self, mock_log):
        """Test handling execution errors"""
        self.mock_executor.execute.side_effect = Exception("Error")
        
        result = self.window_ops.send_keys_to_window("session", "0", "hello")
        
        self.assertFalse(result)
        mock_log.assert_called()
    
    def test_capture_window_output_success(self):
        """Test successful output capture"""
        self.mock_executor.execute.return_value = MagicMock(
            stdout="captured output",
            returncode=0
        )
        
        result = self.window_ops.capture_window_output("session", "0", 30)
        
        self.assertEqual(result, "captured output")
    
    def test_capture_window_output_lines_limit(self):
        """Test lines limit enforcement"""
        self.mock_executor.execute.return_value = MagicMock(stdout="", returncode=0)
        
        # Test max limit
        self.window_ops.capture_window_output("session", "0", 5000)
        call_args = self.mock_executor.execute.call_args[0][0]
        self.assertIn("-1000", call_args)  # Should be capped at 1000
        
        # Test min limit
        self.window_ops.capture_window_output("session", "0", 0)
        call_args = self.mock_executor.execute.call_args[0][0]
        self.assertIn("-1", call_args)  # Should be at least 1


class TestSessionOperations(unittest.TestCase):
    """Test the SessionOperations class"""
    
    def setUp(self):
        self.mock_executor = MagicMock()
        self.mock_validator = InputValidator()
        self.session_ops = SessionOperations(self.mock_executor, self.mock_validator)
    
    def test_create_session_success(self):
        """Test successful session creation"""
        self.mock_executor.execute.return_value = MagicMock(returncode=0)
        
        result = self.session_ops.create_session("my-project", "/path/to/project")
        
        self.assertTrue(result)
        self.mock_executor.execute.assert_called_once()
    
    def test_create_session_invalid_name(self):
        """Test session creation with invalid name"""
        result = self.session_ops.create_session("invalid name!", "/path")
        self.assertFalse(result)
    
    @patch('logging.Logger.error')
    def test_create_session_execution_error(self, mock_log):
        """Test handling execution errors during session creation"""
        self.mock_executor.execute.side_effect = Exception("Error")
        
        result = self.session_ops.create_session("valid", "/path")
        
        self.assertFalse(result)
        mock_log.assert_called()
    
    def test_add_window_success(self):
        """Test successful window addition"""
        self.mock_executor.execute.return_value = MagicMock(returncode=0)
        
        result = self.session_ops.add_window("session", "Shell", "/path")
        
        self.assertTrue(result)
        self.mock_executor.execute.assert_called_once()


class TestTmuxOrchestratorIntegration(unittest.TestCase):
    """Integration tests for TmuxOrchestrator"""
    
    def setUp(self):
        self.orchestrator = TmuxOrchestrator()
    
    @patch.object(SessionDiscovery, 'get_all_sessions')
    def test_get_all_sessions(self, mock_get_sessions):
        """Test getting all sessions through orchestrator"""
        mock_sessions = [
            TmuxSession(name="test", windows=[], attached=False)
        ]
        mock_get_sessions.return_value = mock_sessions
        
        sessions = self.orchestrator.get_all_sessions()
        
        self.assertEqual(sessions, mock_sessions)
    
    @patch.object(WindowOperations, 'send_keys_to_window')
    def test_send_message(self, mock_send_keys):
        """Test sending message through orchestrator"""
        mock_send_keys.return_value = True
        
        result = self.orchestrator.send_message("session", "0", "hello")
        
        self.assertTrue(result)
        mock_send_keys.assert_called_once_with("session", "0", "hello")
    
    @patch.object(WindowOperations, 'capture_window_output')
    def test_get_window_output(self, mock_capture):
        """Test getting window output through orchestrator"""
        mock_capture.return_value = "output"
        
        result = self.orchestrator.get_window_output("session", "0", 25)
        
        self.assertEqual(result, "output")
        mock_capture.assert_called_once_with("session", "0", 25)
    
    @patch.object(SessionOperations, 'create_session')
    def test_create_project_session(self, mock_create):
        """Test creating project session through orchestrator"""
        mock_create.return_value = True
        
        result = self.orchestrator.create_project_session("project", "/path")
        
        self.assertTrue(result)
        mock_create.assert_called_once_with("project", "/path")
    
    @patch.object(SessionOperations, 'add_window')
    def test_add_window_to_session(self, mock_add_window):
        """Test adding window through orchestrator"""
        mock_add_window.return_value = True
        
        result = self.orchestrator.add_window_to_session("session", "Window", "/path")
        
        self.assertTrue(result)
        mock_add_window.assert_called_once_with("session", "Window", "/path")


class TestDataClasses(unittest.TestCase):
    """Test data classes"""
    
    def test_tmux_window_creation(self):
        """Test TmuxWindow dataclass"""
        window = TmuxWindow(
            index=0,
            name="Test",
            type=WindowType.CLAUDE,
            current_command="node",
            pane_count=2
        )
        
        self.assertEqual(window.index, 0)
        self.assertEqual(window.name, "Test")
        self.assertEqual(window.type, WindowType.CLAUDE)
        self.assertEqual(window.current_command, "node")
        self.assertEqual(window.pane_count, 2)
    
    def test_tmux_session_creation(self):
        """Test TmuxSession dataclass"""
        windows = [
            TmuxWindow(0, "Claude", WindowType.CLAUDE),
            TmuxWindow(1, "Shell", WindowType.SHELL)
        ]
        
        session = TmuxSession(
            name="test-session",
            windows=windows,
            attached=True,
            created_time="12345"
        )
        
        self.assertEqual(session.name, "test-session")
        self.assertEqual(len(session.windows), 2)
        self.assertTrue(session.attached)
        self.assertEqual(session.created_time, "12345")
    
    def test_window_type_enum(self):
        """Test WindowType enum"""
        self.assertEqual(WindowType.CLAUDE.value, "claude")
        self.assertEqual(WindowType.SHELL.value, "shell")
        self.assertEqual(WindowType.SERVER.value, "server")
        self.assertEqual(WindowType.OTHER.value, "other")


if __name__ == '__main__':
    unittest.main()