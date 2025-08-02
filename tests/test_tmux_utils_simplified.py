#!/usr/bin/env python3
"""Tests for simplified tmux_utils module"""

import unittest
from unittest.mock import patch, MagicMock, call
import subprocess
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tmux_utils import (
    WindowType, TmuxWindow, TmuxSession, TmuxManager
)


class TestDataClasses(unittest.TestCase):
    """Test data classes"""
    
    def test_window_type_constants(self):
        """Test WindowType constants"""
        self.assertEqual(WindowType.CLAUDE, "claude")
        self.assertEqual(WindowType.SERVER, "server")
        self.assertEqual(WindowType.SHELL, "shell")
        self.assertEqual(WindowType.OTHER, "other")
    
    def test_tmux_window_creation(self):
        """Test TmuxWindow dataclass"""
        window = TmuxWindow(0, "Test", "bash", WindowType.SHELL)
        self.assertEqual(window.index, 0)
        self.assertEqual(window.name, "Test")
        self.assertEqual(window.command, "bash")
        self.assertEqual(window.type, WindowType.SHELL)
    
    def test_tmux_session_creation(self):
        """Test TmuxSession dataclass"""
        window = TmuxWindow(0, "Test", "bash")
        session = TmuxSession("test-session", "123456", [window])
        self.assertEqual(session.name, "test-session")
        self.assertEqual(session.created, "123456")
        self.assertEqual(len(session.windows), 1)


class TestTmuxManager(unittest.TestCase):
    """Test the consolidated TmuxManager"""
    
    def setUp(self):
        """Set up test manager"""
        self.manager = TmuxManager()
    
    def test_validate_session_name(self):
        """Test session name validation"""
        # Valid names
        self.assertTrue(self.manager.validate_session_name("valid-name"))
        self.assertTrue(self.manager.validate_session_name("test_123"))
        
        # Invalid names
        self.assertFalse(self.manager.validate_session_name(""))
        self.assertFalse(self.manager.validate_session_name("name;with;semicolon"))
        self.assertFalse(self.manager.validate_session_name("name'with'quotes"))
        self.assertFalse(self.manager.validate_session_name("name$with$dollar"))
    
    def test_validate_window_index(self):
        """Test window index validation"""
        self.assertTrue(self.manager.validate_window_index(0))
        self.assertTrue(self.manager.validate_window_index(10))
        self.assertTrue(self.manager.validate_window_index("5"))
        
        self.assertFalse(self.manager.validate_window_index(-1))
        self.assertFalse(self.manager.validate_window_index("abc"))
        self.assertFalse(self.manager.validate_window_index(None))
    
    def test_sanitize_keys(self):
        """Test key sanitization"""
        self.assertEqual(
            self.manager.sanitize_keys("test"),
            "test"
        )
        self.assertEqual(
            self.manager.sanitize_keys("test'with'quotes"),
            "test'\"'\"'with'\"'\"'quotes"
        )
    
    @patch('subprocess.run')
    def test_execute_command_success(self, mock_run):
        """Test successful command execution"""
        mock_run.return_value = MagicMock(
            stdout="output",
            returncode=0
        )
        
        result = self.manager.execute_command(["tmux", "list"])
        
        self.assertIsNotNone(result)
        self.assertEqual(result.stdout, "output")
    
    @patch('subprocess.run')
    def test_execute_command_failure_with_check(self, mock_run):
        """Test command failure with check=True"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        with self.assertRaises(subprocess.CalledProcessError):
            self.manager.execute_command(["tmux", "fail"], check=True)
    
    @patch('subprocess.run')
    def test_execute_command_failure_without_check(self, mock_run):
        """Test command failure with check=False"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        result = self.manager.execute_command(["tmux", "fail"], check=False)
        self.assertIsNone(result)
    
    def test_determine_window_type(self):
        """Test window type determination"""
        self.assertEqual(
            self.manager._determine_window_type("Claude-Agent", "node"),
            WindowType.CLAUDE
        )
        self.assertEqual(
            self.manager._determine_window_type("Dev-Server", "npm"),
            WindowType.SERVER
        )
        self.assertEqual(
            self.manager._determine_window_type("Shell", "bash"),
            WindowType.SHELL
        )
        self.assertEqual(
            self.manager._determine_window_type("Random", "unknown"),
            WindowType.OTHER
        )
    
    @patch('subprocess.run')
    def test_get_all_sessions(self, mock_run):
        """Test getting all sessions with windows"""
        # Mock session list
        mock_run.side_effect = [
            MagicMock(stdout="test-session:123456\n", returncode=0),
            MagicMock(stdout="0:Claude:node\n1:Shell:bash\n", returncode=0)
        ]
        
        sessions = self.manager.get_all_sessions()
        
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].name, "test-session")
        self.assertEqual(len(sessions[0].windows), 2)
        self.assertEqual(sessions[0].windows[0].type, WindowType.CLAUDE)
    
    @patch('subprocess.run')
    def test_send_keys_to_window(self, mock_run):
        """Test sending keys to window"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.send_keys_to_window("session", 0, "test message")
        
        self.assertTrue(result)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("send-keys", args)
        self.assertIn("session:0", args)
    
    @patch('subprocess.run')
    def test_send_keys_invalid_session(self, mock_run):
        """Test sending keys with invalid session"""
        result = self.manager.send_keys_to_window("invalid;session", 0, "test")
        self.assertFalse(result)
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    def test_capture_window_output(self, mock_run):
        """Test capturing window output"""
        mock_run.return_value = MagicMock(
            stdout="Line 1\nLine 2\nLine 3",
            returncode=0
        )
        
        output = self.manager.capture_window_output("session", 0, 3)
        
        self.assertEqual(output, "Line 1\nLine 2\nLine 3")
        args = mock_run.call_args[0][0]
        self.assertIn("capture-pane", args)
        self.assertIn("-3", args)
    
    @patch('subprocess.run')
    def test_create_session(self, mock_run):
        """Test creating a new session"""
        mock_run.return_value = MagicMock(returncode=0)
        
        with patch('pathlib.Path.exists', return_value=True):
            result = self.manager.create_session("test-project", "/path/to/project")
        
        self.assertTrue(result)
        args = mock_run.call_args[0][0]
        self.assertIn("new-session", args)
        self.assertIn("test-project", args)
        self.assertIn("/path/to/project", args)
    
    @patch('subprocess.run')
    def test_add_window(self, mock_run):
        """Test adding window to session"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.add_window("session", "New-Window")
        
        self.assertTrue(result)
        args = mock_run.call_args[0][0]
        self.assertIn("new-window", args)
        self.assertIn("New-Window", args)
    
    @patch('subprocess.run')
    def test_create_project_session(self, mock_run):
        """Test creating complete project session"""
        mock_run.return_value = MagicMock(returncode=0)
        
        with patch('pathlib.Path.exists', return_value=True):
            result = self.manager.create_project_session("my-project", "/path/to/project")
        
        self.assertTrue(result)
        # Should have multiple calls for session, rename, and windows
        self.assertTrue(mock_run.call_count >= 4)
    
    @patch('subprocess.run')
    def test_send_message(self, mock_run):
        """Test send_message convenience method"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.send_message("session", 0, "Hello")
        
        self.assertTrue(result)
        # Should be called twice (message + Enter)
        self.assertEqual(mock_run.call_count, 2)
        
        # Check both calls
        first_call = mock_run.call_args_list[0][0][0]
        second_call = mock_run.call_args_list[1][0][0]
        
        self.assertIn("Hello", first_call)
        self.assertIn("Enter", second_call)
    
    @patch('subprocess.run')
    def test_get_window_output(self, mock_run):
        """Test get_window_output convenience method"""
        mock_run.return_value = MagicMock(
            stdout="test output",
            returncode=0
        )
        
        output = self.manager.get_window_output("session", 0, 10)
        
        self.assertEqual(output, "test output")


class TestErrorHandling(unittest.TestCase):
    """Test error handling in TmuxManager"""
    
    def setUp(self):
        self.manager = TmuxManager()
    
    @patch('subprocess.run')
    def test_execute_command_unexpected_error(self, mock_run):
        """Test handling of unexpected errors"""
        mock_run.side_effect = Exception("Unexpected error")
        
        with self.assertRaises(Exception):
            self.manager.execute_command(["tmux", "test"])
    
    @patch('subprocess.run')
    def test_get_all_sessions_empty_response(self, mock_run):
        """Test handling empty session list"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        
        sessions = self.manager.get_all_sessions()
        self.assertEqual(sessions, [])
    
    @patch('subprocess.run')
    def test_create_session_invalid_name(self, mock_run):
        """Test creating session with invalid name"""
        result = self.manager.create_session("invalid;name")
        
        self.assertFalse(result)
        mock_run.assert_not_called()
    
    def test_create_project_session_nonexistent_path(self):
        """Test creating project with non-existent path"""
        with patch('pathlib.Path.exists', return_value=False):
            result = self.manager.create_project_session("test", "/nonexistent")
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()