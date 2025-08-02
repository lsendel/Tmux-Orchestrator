#!/usr/bin/env python3
"""Test tmux utils simplified version works with old test patterns"""

import unittest
from unittest.mock import patch, MagicMock
import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from tmux_utils directly
from tmux_utils import (
    TmuxManager, WindowType, TmuxWindow, TmuxSession
)


class TestTmuxUtilsSimplified(unittest.TestCase):
    """Test tmux utils simplified version"""
    
    def setUp(self):
        self.manager = TmuxManager()
    
    def test_window_type_constants(self):
        """Test WindowType constants"""
        self.assertEqual(WindowType.CLAUDE, "claude")
        self.assertEqual(WindowType.SERVER, "server")
        self.assertEqual(WindowType.SHELL, "shell")
        self.assertEqual(WindowType.OTHER, "other")
    
    def test_dataclasses_creation(self):
        """Test dataclasses can be created"""
        window = TmuxWindow(0, "test", "bash", WindowType.SHELL)
        self.assertEqual(window.index, 0)
        self.assertEqual(window.name, "test")
        self.assertEqual(window.command, "bash")
        self.assertEqual(window.type, WindowType.SHELL)
        
        session = TmuxSession("test-session", "123456", [window])
        self.assertEqual(session.name, "test-session")
        self.assertEqual(session.created, "123456")
        self.assertEqual(len(session.windows), 1)
    
    def test_input_validation(self):
        """Test input validation methods"""
        self.assertTrue(self.manager.validate_session_name("valid-name"))
        self.assertFalse(self.manager.validate_session_name("invalid;name"))
        self.assertTrue(self.manager.validate_window_index(0))
        self.assertFalse(self.manager.validate_window_index("abc"))
        self.assertEqual(self.manager.sanitize_keys("test"), "test")
    
    @patch('subprocess.run')
    def test_get_all_sessions(self, mock_run):
        """Test get_all_sessions"""
        mock_run.side_effect = [
            MagicMock(
                stdout="test-session:123456\n",
                returncode=0
            ),
            MagicMock(
                stdout="0:Claude:node\n1:Shell:bash\n",
                returncode=0
            )
        ]
        
        sessions = self.manager.get_all_sessions()
        
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].name, "test-session")
        self.assertEqual(len(sessions[0].windows), 2)
        self.assertEqual(sessions[0].windows[0].name, "Claude")
        self.assertEqual(sessions[0].windows[0].type, WindowType.CLAUDE)
    
    @patch('subprocess.run')
    def test_create_project_session(self, mock_run):
        """Test create_project_session"""
        mock_run.return_value = MagicMock(returncode=0)
        
        with patch('pathlib.Path.exists', return_value=True):
            result = self.manager.create_project_session("test-project", "/path/to/project")
            
        self.assertTrue(result)
        # Check tmux commands were called
        self.assertTrue(any(
            "new-session" in str(call) 
            for call in mock_run.call_args_list
        ))
    
    @patch('subprocess.run')
    def test_send_message(self, mock_run):
        """Test send_message"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.send_message("session", 0, "test message")
        
        self.assertTrue(result)
        # Should have been called twice (message + Enter)
        self.assertEqual(mock_run.call_count, 2)


if __name__ == '__main__':
    unittest.main()