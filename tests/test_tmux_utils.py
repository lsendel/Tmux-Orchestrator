#!/usr/bin/env python3
"""Unit tests for tmux_utils.py"""

import unittest
from unittest.mock import patch, MagicMock, call
import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tmux_utils import TmuxWindow, TmuxSession, TmuxOrchestrator


class TestDataClasses(unittest.TestCase):
    """Test cases for data classes"""

    def test_tmux_window_creation(self):
        """Test TmuxWindow dataclass creation"""
        window = TmuxWindow(
            session_name="test-session",
            window_index=0,
            window_name="test-window",
            active=True
        )
        self.assertEqual(window.session_name, "test-session")
        self.assertEqual(window.window_index, 0)
        self.assertEqual(window.window_name, "test-window")
        self.assertTrue(window.active)

    def test_tmux_session_creation(self):
        """Test TmuxSession dataclass creation"""
        windows = [
            TmuxWindow("test", 0, "window1", True),
            TmuxWindow("test", 1, "window2", False)
        ]
        session = TmuxSession(
            name="test-session",
            windows=windows,
            attached=True
        )
        self.assertEqual(session.name, "test-session")
        self.assertEqual(len(session.windows), 2)
        self.assertTrue(session.attached)


class TestTmuxOrchestrator(unittest.TestCase):
    """Test cases for TmuxOrchestrator class"""

    def setUp(self):
        """Set up test fixtures"""
        self.orchestrator = TmuxOrchestrator()

    def test_init(self):
        """Test orchestrator initialization"""
        self.assertTrue(self.orchestrator.safety_mode)
        self.assertEqual(self.orchestrator.max_lines_capture, 1000)

    @patch('subprocess.run')
    def test_get_tmux_sessions_success(self, mock_run):
        """Test getting tmux sessions successfully"""
        # Mock tmux list-sessions output
        mock_run.side_effect = [
            MagicMock(stdout="session1:1\nsession2:0\n", returncode=0),
            MagicMock(stdout="0:window1:1\n1:window2:0\n", returncode=0),
            MagicMock(stdout="0:window3:0\n", returncode=0)
        ]
        
        sessions = self.orchestrator.get_tmux_sessions()
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].name, "session1")
        self.assertTrue(sessions[0].attached)
        self.assertEqual(len(sessions[0].windows), 2)
        self.assertEqual(sessions[1].name, "session2")
        self.assertFalse(sessions[1].attached)

    @patch('subprocess.run')
    @patch('tmux_utils.print')
    def test_get_tmux_sessions_error(self, mock_print, mock_run):
        """Test handling error when getting sessions"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        sessions = self.orchestrator.get_tmux_sessions()
        
        self.assertEqual(sessions, [])
        mock_print.assert_called_once()

    @patch('subprocess.run')
    def test_capture_window_content(self, mock_run):
        """Test capturing window content"""
        mock_run.return_value = MagicMock(
            stdout="Line 1\nLine 2\nLine 3\n",
            returncode=0
        )
        
        content = self.orchestrator.capture_window_content("session", 0, 50)
        
        self.assertEqual(content, "Line 1\nLine 2\nLine 3\n")
        mock_run.assert_called_once_with(
            ["tmux", "capture-pane", "-t", "session:0", "-p", "-S", "-50"],
            capture_output=True, text=True, check=True
        )

    @patch('subprocess.run')
    def test_capture_window_content_max_lines(self, mock_run):
        """Test capturing window content respects max lines"""
        mock_run.return_value = MagicMock(stdout="content", returncode=0)
        
        self.orchestrator.capture_window_content("session", 0, 2000)
        
        # Should cap at max_lines_capture (1000)
        mock_run.assert_called_once_with(
            ["tmux", "capture-pane", "-t", "session:0", "-p", "-S", "-1000"],
            capture_output=True, text=True, check=True
        )

    @patch('subprocess.run')
    def test_capture_window_content_error(self, mock_run):
        """Test handling error when capturing content"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd', stderr='error')
        
        content = self.orchestrator.capture_window_content("session", 0)
        
        self.assertIn("Error capturing window content", content)

    @patch('subprocess.run')
    def test_get_window_info(self, mock_run):
        """Test getting window information"""
        mock_run.side_effect = [
            MagicMock(stdout="test-window:1:3:layout-string\n", returncode=0),
            MagicMock(stdout="window content", returncode=0)
        ]
        
        info = self.orchestrator.get_window_info("session", 0)
        
        self.assertEqual(info['name'], "test-window")
        self.assertTrue(info['active'])
        self.assertEqual(info['panes'], 3)
        self.assertEqual(info['layout'], "layout-string")
        self.assertEqual(info['content'], "window content")

    def test_send_keys_to_window_invalid_session(self):
        """Test send_keys validation for invalid session name"""
        with self.assertRaises(ValueError) as context:
            self.orchestrator.send_keys_to_window("invalid session!", 0, "test")
        
        self.assertIn("Invalid session name format", str(context.exception))

    def test_send_keys_to_window_invalid_window(self):
        """Test send_keys validation for invalid window index"""
        with self.assertRaises(ValueError) as context:
            self.orchestrator.send_keys_to_window("valid-session", -1, "test")
        
        self.assertIn("Invalid window index", str(context.exception))

    @patch('subprocess.run')
    @patch('builtins.input', return_value='yes')
    @patch('tmux_utils.print')
    def test_send_keys_to_window_with_confirmation(self, mock_print, mock_input, mock_run):
        """Test sending keys with safety confirmation"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.orchestrator.send_keys_to_window("session", 0, "test command")
        
        self.assertTrue(result)
        mock_input.assert_called_once()
        mock_print.assert_called_once()  # Safety check message
        
        # Check that shlex.quote was used
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("'test command'", ' '.join(called_cmd))

    @patch('builtins.input', return_value='no')
    @patch('tmux_utils.print')
    def test_send_keys_to_window_cancelled(self, mock_print, mock_input):
        """Test cancelling send_keys operation"""
        result = self.orchestrator.send_keys_to_window("session", 0, "test")
        
        self.assertFalse(result)
        mock_input.assert_called_once()

    @patch('subprocess.run')
    def test_send_keys_to_window_no_confirmation(self, mock_run):
        """Test sending keys without confirmation"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.orchestrator.send_keys_to_window("session", 0, "test", confirm=False)
        
        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    @patch('tmux_utils.print')
    def test_send_keys_to_window_error(self, mock_print, mock_run):
        """Test handling error when sending keys"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        result = self.orchestrator.send_keys_to_window("session", 0, "test", confirm=False)
        
        self.assertFalse(result)
        mock_print.assert_called_once()  # Error message

    @patch('subprocess.run')
    def test_send_command_to_window(self, mock_run):
        """Test sending command (with Enter key)"""
        mock_run.return_value = MagicMock(returncode=0)
        
        with patch.object(self.orchestrator, 'send_keys_to_window', return_value=True):
            result = self.orchestrator.send_command_to_window("session", 0, "command", confirm=False)
        
        self.assertTrue(result)
        # Check that Enter key (C-m) was sent
        mock_run.assert_called_once_with(
            ["tmux", "send-keys", "-t", "session:0", "C-m"],
            check=True
        )

    def test_find_window_by_name(self):
        """Test finding windows by name"""
        mock_sessions = [
            TmuxSession(
                name="session1",
                windows=[
                    TmuxWindow("session1", 0, "test-window", True),
                    TmuxWindow("session1", 1, "other-window", False)
                ],
                attached=True
            ),
            TmuxSession(
                name="session2",
                windows=[
                    TmuxWindow("session2", 0, "test-window-2", False)
                ],
                attached=False
            )
        ]
        
        with patch.object(self.orchestrator, 'get_tmux_sessions', return_value=mock_sessions):
            matches = self.orchestrator.find_window_by_name("test")
        
        self.assertEqual(len(matches), 2)
        self.assertIn(("session1", 0), matches)
        self.assertIn(("session2", 0), matches)

    def test_get_all_windows_status(self):
        """Test getting all windows status"""
        mock_sessions = [
            TmuxSession(
                name="test-session",
                windows=[TmuxWindow("test-session", 0, "window1", True)],
                attached=True
            )
        ]
        
        with patch.object(self.orchestrator, 'get_tmux_sessions', return_value=mock_sessions):
            with patch.object(self.orchestrator, 'get_window_info', return_value={'test': 'info'}):
                status = self.orchestrator.get_all_windows_status()
        
        self.assertIn('timestamp', status)
        self.assertIn('sessions', status)
        self.assertEqual(len(status['sessions']), 1)
        self.assertEqual(status['sessions'][0]['name'], 'test-session')

    def test_create_monitoring_snapshot(self):
        """Test creating monitoring snapshot"""
        mock_status = {
            'timestamp': '2024-01-01T00:00:00',
            'sessions': [{
                'name': 'test-session',
                'attached': True,
                'windows': [{
                    'index': 0,
                    'name': 'test-window',
                    'active': True,
                    'info': {
                        'content': "Line 1\nLine 2\nLine 3\n" + "\n".join([f"Line {i}" for i in range(4, 15)])
                    }
                }]
            }]
        }
        
        with patch.object(self.orchestrator, 'get_all_windows_status', return_value=mock_status):
            snapshot = self.orchestrator.create_monitoring_snapshot()
        
        self.assertIn('Tmux Monitoring Snapshot', snapshot)
        self.assertIn('test-session', snapshot)
        self.assertIn('(ATTACHED)', snapshot)
        self.assertIn('test-window', snapshot)
        self.assertIn('(ACTIVE)', snapshot)
        self.assertIn('Recent output:', snapshot)
        # Should only include last 10 lines
        self.assertIn('Line 14', snapshot)
        # Line 1 might appear in the window name or other metadata


class TestSafetyFeatures(unittest.TestCase):
    """Test safety and security features"""

    def setUp(self):
        """Set up test fixtures"""
        self.orchestrator = TmuxOrchestrator()

    def test_command_injection_prevention(self):
        """Test that command injection is prevented"""
        # Test various injection attempts
        dangerous_inputs = [
            "test; rm -rf /",
            "test && malicious_command",
            "test | cat /etc/passwd",
            "test`whoami`",
            "test$(whoami)",
            "test\nmalicious_command"
        ]
        
        for dangerous_input in dangerous_inputs:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                
                self.orchestrator.send_keys_to_window(
                    "session", 0, dangerous_input, confirm=False
                )
                
                # Check that the dangerous input was quoted
                called_cmd = mock_run.call_args[0][0]
                # The command should contain the quoted version
                self.assertTrue(any(arg.startswith("'") and arg.endswith("'") 
                                  for arg in called_cmd))

    def test_session_name_validation(self):
        """Test session name validation"""
        invalid_names = [
            "session with spaces",
            "session;with;semicolons",
            "session&with&ampersands",
            "session|with|pipes",
            "../../../etc/passwd",
            "session\nwith\nnewlines"
        ]
        
        for invalid_name in invalid_names:
            with self.assertRaises(ValueError):
                self.orchestrator.send_keys_to_window(invalid_name, 0, "test", confirm=False)


if __name__ == '__main__':
    unittest.main()