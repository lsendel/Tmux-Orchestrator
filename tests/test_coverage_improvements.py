#!/usr/bin/env python3
"""Tests to improve coverage for main() and error paths"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_control import main as claude_main, ClaudeMonitor, TmuxClient
from tmux_utils import main as tmux_main, TmuxManager


class TestClaudeControlMain(unittest.TestCase):
    """Test main() function and CLI of claude_control"""
    
    @patch('sys.argv', ['claude_control.py'])
    @patch('claude_control.ClaudeMonitor')
    @patch('claude_control.format_status')
    def test_main_default_status(self, mock_format, mock_monitor_class):
        """Test main with no arguments defaults to status"""
        mock_monitor = MagicMock()
        mock_monitor.get_all_agents.return_value = [{'test': 'agent'}]
        mock_monitor_class.return_value = mock_monitor
        
        try:
            claude_main()
        except SystemExit:
            pass
        
        mock_monitor.get_all_agents.assert_called_once()
        mock_format.assert_called_once_with([{'test': 'agent'}], False)
        mock_monitor.save_status.assert_called_once()
    
    @patch('sys.argv', ['claude_control.py', 'status', 'detailed'])
    @patch('claude_control.ClaudeMonitor')
    @patch('claude_control.format_status')
    def test_main_status_detailed(self, mock_format, mock_monitor_class):
        """Test main with detailed status"""
        mock_monitor = MagicMock()
        mock_monitor.get_all_agents.return_value = []
        mock_monitor_class.return_value = mock_monitor
        
        try:
            claude_main()
        except SystemExit:
            pass
        
        mock_format.assert_called_once_with([], True)
    
    @patch('sys.argv', ['claude_control.py', 'health'])
    @patch('claude_control.ClaudeMonitor')
    @patch('builtins.print')
    def test_main_health_command(self, mock_print, mock_monitor_class):
        """Test main with health command"""
        mock_monitor = MagicMock()
        mock_monitor.health_check.return_value = {'status': 'healthy'}
        mock_monitor_class.return_value = mock_monitor
        
        try:
            claude_main()
        except SystemExit:
            pass
        
        mock_monitor.health_check.assert_called_once()
        # Check JSON was printed
        printed = mock_print.call_args[0][0]
        parsed = json.loads(printed)
        self.assertEqual(parsed['status'], 'healthy')
    
    @patch('sys.argv', ['claude_control.py', 'invalid'])
    @patch('builtins.print')
    def test_main_invalid_command(self, mock_print):
        """Test main with invalid command"""
        with self.assertRaises(SystemExit) as cm:
            claude_main()
        
        self.assertEqual(cm.exception.code, 1)
        # Check error message was printed
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('Unknown command: invalid' in call for call in calls))
    
    @patch('sys.argv', ['claude_control.py'])
    @patch('claude_control.ClaudeMonitor')
    @patch('logging.error')
    def test_main_exception_handling(self, mock_log, mock_monitor_class):
        """Test main handles exceptions properly"""
        mock_monitor_class.side_effect = Exception("Test error")
        
        with self.assertRaises(SystemExit) as cm:
            claude_main()
        
        self.assertEqual(cm.exception.code, 1)
        mock_log.assert_called_once()
        self.assertIn("Test error", str(mock_log.call_args))


class TestClaudeControlErrorPaths(unittest.TestCase):
    """Test error handling paths in claude_control"""
    
    @patch('subprocess.run')
    def test_capture_pane_no_output(self, mock_run):
        """Test capture_pane with empty output"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        
        result = TmuxClient.capture_pane("session", 0)
        self.assertEqual(result, "")
    
    @patch('subprocess.run')
    def test_get_windows_empty_output(self, mock_run):
        """Test get_windows with empty output"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        
        windows = TmuxClient.get_windows("test")
        self.assertEqual(windows, [])
    
    @patch('subprocess.run')
    def test_get_windows_malformed_line(self, mock_run):
        """Test get_windows with malformed line"""
        mock_run.return_value = MagicMock(
            stdout="0:Window1:bash\nmalformed_line\n2:Window2:zsh\n",
            returncode=0
        )
        
        windows = TmuxClient.get_windows("test")
        self.assertEqual(len(windows), 2)  # Only valid lines parsed
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=False)
    def test_check_claude_no_script(self, mock_exists, mock_run):
        """Test _check_claude_available when script doesn't exist"""
        mock_run.side_effect = FileNotFoundError()
        
        monitor = ClaudeMonitor()
        result = monitor._check_claude_available()
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    def test_check_claude_script_fails(self, mock_exists, mock_run):
        """Test _check_claude_available when script fails"""
        # First call is for script, returns non-zero
        # Second call is for direct claude check, fails
        mock_run.side_effect = [
            MagicMock(returncode=1),
            subprocess.CalledProcessError(1, 'claude')
        ]
        
        monitor = ClaudeMonitor()
        result = monitor._check_claude_available()
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    def test_check_claude_script_exception(self, mock_exists, mock_run):
        """Test _check_claude_available when script throws exception"""
        # Script throws exception, fallback to direct check succeeds
        mock_run.side_effect = [
            Exception("Script error"),
            MagicMock(returncode=0)
        ]
        
        monitor = ClaudeMonitor()
        result = monitor._check_claude_available()
        
        self.assertTrue(result)


class TestTmuxUtilsMain(unittest.TestCase):
    """Test main() function and CLI of tmux_utils"""
    
    @patch('sys.argv', ['tmux_utils.py'])
    @patch('builtins.print')
    def test_main_no_args(self, mock_print):
        """Test main with no arguments"""
        with self.assertRaises(SystemExit) as cm:
            tmux_main()
        
        self.assertEqual(cm.exception.code, 1)
        # Check usage was printed
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('Usage:' in call for call in calls))
    
    @patch('sys.argv', ['tmux_utils.py', 'list'])
    @patch('tmux_utils.TmuxManager')
    @patch('builtins.print')
    def test_main_list_command(self, mock_print, mock_manager_class):
        """Test main with list command"""
        mock_manager = MagicMock()
        mock_window = MagicMock(index=0, name='test', type='shell')
        mock_session = MagicMock(name='session1', created='123', windows=[mock_window])
        mock_manager.get_all_sessions.return_value = [mock_session]
        mock_manager_class.return_value = mock_manager
        
        try:
            tmux_main()
        except SystemExit:
            pass
        
        mock_manager.get_all_sessions.assert_called_once()
        # Check session was printed
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('session1' in call for call in calls))
    
    @patch('sys.argv', ['tmux_utils.py', 'create'])
    @patch('builtins.print')
    def test_main_create_missing_args(self, mock_print):
        """Test main create command with missing args"""
        with self.assertRaises(SystemExit) as cm:
            tmux_main()
        
        self.assertEqual(cm.exception.code, 1)
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('Invalid command' in call for call in calls))
    
    @patch('sys.argv', ['tmux_utils.py', 'create', 'test-session', '/tmp/test'])
    @patch('tmux_utils.TmuxManager')
    @patch('builtins.print')
    def test_main_create_success(self, mock_print, mock_manager_class):
        """Test main create command success"""
        mock_manager = MagicMock()
        mock_manager.create_project_session.return_value = True
        mock_manager_class.return_value = mock_manager
        
        try:
            tmux_main()
        except SystemExit:
            pass
        
        mock_manager.create_project_session.assert_called_once_with('test-session', '/tmp/test')
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('✅' in call for call in calls))
    
    @patch('sys.argv', ['tmux_utils.py', 'create', 'test-session', '/tmp/test'])
    @patch('tmux_utils.TmuxManager')
    @patch('builtins.print')
    def test_main_create_failure(self, mock_print, mock_manager_class):
        """Test main create command failure"""
        mock_manager = MagicMock()
        mock_manager.create_project_session.return_value = False
        mock_manager_class.return_value = mock_manager
        
        with self.assertRaises(SystemExit) as cm:
            tmux_main()
        
        self.assertEqual(cm.exception.code, 1)
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('❌' in call for call in calls))
    
    @patch('sys.argv', ['tmux_utils.py', 'send', 'session', '0', 'test message'])
    @patch('tmux_utils.TmuxManager')
    @patch('builtins.print')
    def test_main_send_success(self, mock_print, mock_manager_class):
        """Test main send command success"""
        mock_manager = MagicMock()
        mock_manager.send_message.return_value = True
        mock_manager_class.return_value = mock_manager
        
        try:
            tmux_main()
        except SystemExit:
            pass
        
        mock_manager.send_message.assert_called_once_with('session', 0, 'test message')
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('✅' in call for call in calls))
    
    @patch('sys.argv', ['tmux_utils.py', 'send', 'session', '0', 'test message'])
    @patch('tmux_utils.TmuxManager')
    @patch('builtins.print')
    def test_main_send_failure(self, mock_print, mock_manager_class):
        """Test main send command failure"""
        mock_manager = MagicMock()
        mock_manager.send_message.return_value = False
        mock_manager_class.return_value = mock_manager
        
        with self.assertRaises(SystemExit) as cm:
            tmux_main()
        
        self.assertEqual(cm.exception.code, 1)
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('❌' in call for call in calls))
    
    @patch('sys.argv', ['tmux_utils.py', 'invalid'])
    @patch('builtins.print')
    def test_main_invalid_command(self, mock_print):
        """Test main with invalid command"""
        with self.assertRaises(SystemExit) as cm:
            tmux_main()
        
        self.assertEqual(cm.exception.code, 1)
        calls = [str(call[0][0]) for call in mock_print.call_args_list]
        self.assertTrue(any('Invalid command' in call for call in calls))
    
    @patch('sys.argv', ['tmux_utils.py', 'list'])
    @patch('logging.error')
    def test_main_exception_handling(self, mock_log):
        """Test main handles exceptions"""
        with patch('tmux_utils.TmuxManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.get_all_sessions.side_effect = Exception("Test error")
            mock_manager_class.return_value = mock_manager
            
            with self.assertRaises(SystemExit) as cm:
                tmux_main()
            
            self.assertEqual(cm.exception.code, 1)
            mock_log.assert_called_once()
            self.assertIn("Test error", str(mock_log.call_args))


class TestTmuxUtilsErrorPaths(unittest.TestCase):
    """Test error handling paths in tmux_utils"""
    
    def setUp(self):
        self.manager = TmuxManager()
    
    @patch('subprocess.run')
    def test_get_all_sessions_empty_stdout(self, mock_run):
        """Test get_all_sessions with empty stdout"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        
        sessions = self.manager.get_all_sessions()
        self.assertEqual(sessions, [])
    
    @patch('subprocess.run')
    def test_get_all_sessions_line_without_colon(self, mock_run):
        """Test get_all_sessions with line missing colon"""
        mock_run.side_effect = [
            MagicMock(stdout="session1:123\nno_colon_line\nsession2:456\n", returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0)
        ]
        
        sessions = self.manager.get_all_sessions()
        self.assertEqual(len(sessions), 2)  # Only valid lines
    
    @patch('subprocess.run')
    def test_get_session_windows_empty_line(self, mock_run):
        """Test _get_session_windows with empty lines"""
        mock_run.return_value = MagicMock(
            stdout="0:Window1:bash\n\n2:Window2:zsh\n",
            returncode=0
        )
        
        windows = self.manager._get_session_windows("test")
        self.assertEqual(len(windows), 2)
    
    @patch('subprocess.run')
    @patch('tmux_utils.TmuxManager.validate_window_index', return_value=False)
    def test_send_keys_invalid_window(self, mock_validate, mock_run):
        """Test send_keys_to_window with invalid window"""
        result = self.manager.send_keys_to_window("session", -1, "test")
        
        self.assertFalse(result)
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    @patch('tmux_utils.TmuxManager.validate_session_name', return_value=False)
    def test_capture_window_invalid_session(self, mock_validate, mock_run):
        """Test capture_window_output with invalid session"""
        result = self.manager.capture_window_output("bad;session", 0)
        
        self.assertIsNone(result)
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    def test_capture_window_command_fails(self, mock_run):
        """Test capture_window_output when command fails"""
        mock_run.return_value = MagicMock(returncode=1)
        
        result = self.manager.capture_window_output("session", 0)
        
        self.assertIsNone(result)
    
    @patch('subprocess.run')
    @patch('tmux_utils.TmuxManager.validate_session_name', return_value=False)
    def test_add_window_invalid_session(self, mock_validate, mock_run):
        """Test add_window with invalid session"""
        result = self.manager.add_window("bad;session", "window")
        
        self.assertFalse(result)
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    @patch('tmux_utils.TmuxManager.validate_session_name', return_value=False)
    def test_create_project_invalid_name(self, mock_validate, mock_run):
        """Test create_project_session with invalid name"""
        result = self.manager.create_project_session("bad;name", "/tmp")
        
        self.assertFalse(result)
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=False)
    def test_create_project_nonexistent_path(self, mock_exists, mock_run):
        """Test create_project_session with non-existent path"""
        result = self.manager.create_project_session("test", "/nonexistent")
        
        self.assertFalse(result)
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('tmux_utils.TmuxManager.create_session', return_value=False)
    def test_create_project_session_fails(self, mock_create, mock_exists, mock_run):
        """Test create_project_session when session creation fails"""
        result = self.manager.create_project_session("test", "/tmp")
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    def test_create_project_exception(self, mock_exists, mock_run):
        """Test create_project_session exception handling"""
        mock_run.side_effect = Exception("Test error")
        
        result = self.manager.create_project_session("test", "/tmp")
        
        self.assertFalse(result)
    
    @patch('tmux_utils.TmuxManager.send_keys_to_window')
    def test_send_message_first_send_fails(self, mock_send):
        """Test send_message when first send fails"""
        mock_send.return_value = False
        
        result = self.manager.send_message("session", 0, "test")
        
        self.assertFalse(result)
        mock_send.assert_called_once()  # Only called once, not twice


if __name__ == '__main__':
    unittest.main()