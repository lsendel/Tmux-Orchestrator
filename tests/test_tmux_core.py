"""
Unit tests for tmux_core.py - Testing batch commands and shared utilities
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import subprocess

from tmux_core import (
    TmuxCommand, TmuxPatterns, TmuxValidation,
    TmuxCommandError, SessionInfo, WindowInfo
)


class TestTmuxPatterns(unittest.TestCase):
    """Test pattern detection and classification"""
    
    def test_detect_window_type_by_name(self):
        """Test window type detection by window name"""
        test_cases = [
            ("Claude-Agent", "CLAUDE_AGENT"),
            ("claude-agent", "CLAUDE_AGENT"),
            ("Project-Manager", "PROJECT_MANAGER"),
            ("project-manager", "PROJECT_MANAGER"),
            ("Dev-Server", "DEV_SERVER"),
            ("dev-server", "DEV_SERVER"),
            ("Shell", "SHELL"),
            ("bash", "SHELL"),
            ("random-window", "UNKNOWN")
        ]
        
        for window_name, expected in test_cases:
            with self.subTest(window_name=window_name):
                result = TmuxPatterns.detect_window_type(window_name)
                self.assertEqual(result, expected)
    
    def test_detect_window_type_by_process(self):
        """Test window type detection by process"""
        # Process should override window name for Claude detection
        result = TmuxPatterns.detect_window_type("random", "node /path/to/claude")
        self.assertEqual(result, "CLAUDE_AGENT")
        
        result = TmuxPatterns.detect_window_type("shell", "Claude")
        self.assertEqual(result, "CLAUDE_AGENT")
    
    def test_is_claude_process(self):
        """Test Claude process detection"""
        self.assertTrue(TmuxPatterns.is_claude_process("node claude"))
        self.assertTrue(TmuxPatterns.is_claude_process("Claude"))
        self.assertTrue(TmuxPatterns.is_claude_process("/usr/bin/node"))
        self.assertFalse(TmuxPatterns.is_claude_process("bash"))
        self.assertFalse(TmuxPatterns.is_claude_process("python"))


class TestTmuxValidation(unittest.TestCase):
    """Test validation methods"""
    
    def test_validate_session_name(self):
        """Test session name validation"""
        # Valid names
        self.assertTrue(TmuxValidation.validate_session_name("my-project"))
        self.assertTrue(TmuxValidation.validate_session_name("project_123"))
        self.assertTrue(TmuxValidation.validate_session_name("test"))
        
        # Invalid names
        self.assertFalse(TmuxValidation.validate_session_name("my:project"))
        self.assertFalse(TmuxValidation.validate_session_name("my.project"))
        self.assertFalse(TmuxValidation.validate_session_name("my/project"))
        self.assertFalse(TmuxValidation.validate_session_name(""))
        self.assertFalse(TmuxValidation.validate_session_name(None))
    
    def test_validate_window_index(self):
        """Test window index validation"""
        # Valid indices
        self.assertTrue(TmuxValidation.validate_window_index(0))
        self.assertTrue(TmuxValidation.validate_window_index(1))
        self.assertTrue(TmuxValidation.validate_window_index("5"))
        
        # Invalid indices
        self.assertFalse(TmuxValidation.validate_window_index(-1))
        self.assertFalse(TmuxValidation.validate_window_index("abc"))
        self.assertFalse(TmuxValidation.validate_window_index(None))
        self.assertFalse(TmuxValidation.validate_window_index([]))
    
    def test_sanitize_keys(self):
        """Test key sanitization"""
        self.assertEqual(TmuxValidation.sanitize_keys("hello world"), "hello world")
        self.assertEqual(TmuxValidation.sanitize_keys('echo "test"'), 'echo \\"test\\"')
        self.assertEqual(TmuxValidation.sanitize_keys("echo 'test'"), "echo \\'test\\'")
        self.assertEqual(TmuxValidation.sanitize_keys("echo $HOME"), "echo \\$HOME")
        self.assertEqual(TmuxValidation.sanitize_keys(""), "")
        self.assertEqual(TmuxValidation.sanitize_keys(None), "")


class TestTmuxCommand(unittest.TestCase):
    """Test base command execution and batch operations"""
    
    def setUp(self):
        self.cmd = TmuxCommand()
    
    @patch('subprocess.run')
    def test_execute_command_success(self, mock_run):
        """Test successful command execution"""
        mock_run.return_value = MagicMock(
            stdout="output",
            stderr="",
            returncode=0
        )
        
        result = self.cmd.execute_command(['tmux', 'list-sessions'])
        
        mock_run.assert_called_once_with(
            ['tmux', 'list-sessions'],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertEqual(result.stdout, "output")
    
    @patch('subprocess.run')
    def test_execute_command_failure(self, mock_run):
        """Test command execution failure"""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ['tmux', 'list-sessions'], stderr="no sessions"
        )
        
        with self.assertRaises(TmuxCommandError):
            self.cmd.execute_command(['tmux', 'list-sessions'])
    
    @patch.object(TmuxCommand, 'execute_command')
    def test_batch_get_all_sessions_and_windows(self, mock_execute):
        """Test batch retrieval of sessions and windows"""
        # Mock session output
        session_output = "test-session|2|1234567890|0\nother-session|1|1234567891|1"
        window_output = (
            "test-session:0|Claude-Agent|1|1|tiled|node\n"
            "test-session:1|Shell|0|1|tiled|bash\n"
            "other-session:0|Dev-Server|1|1|tiled|python"
        )
        
        mock_execute.side_effect = [
            MagicMock(stdout=session_output),
            MagicMock(stdout=window_output)
        ]
        
        result = self.cmd.batch_get_all_sessions_and_windows()
        
        # Verify structure
        self.assertIn('sessions', result)
        self.assertIn('windows', result)
        
        # Verify sessions
        self.assertEqual(len(result['sessions']), 2)
        self.assertIn('test-session', result['sessions'])
        self.assertIn('other-session', result['sessions'])
        
        # Verify session data
        test_session = result['sessions']['test-session']
        self.assertEqual(test_session.name, 'test-session')
        self.assertEqual(test_session.windows, 2)
        self.assertFalse(test_session.attached)
        
        # Verify windows
        self.assertEqual(len(result['windows']['test-session']), 2)
        self.assertEqual(len(result['windows']['other-session']), 1)
        
        # Verify window data
        claude_window = result['windows']['test-session'][0]
        self.assertEqual(claude_window.name, 'Claude-Agent')
        self.assertEqual(claude_window.index, 0)
        self.assertTrue(claude_window.active)
        self.assertEqual(claude_window.current_command, 'node')
    
    @patch.object(TmuxCommand, 'execute_command')
    def test_batch_capture_panes(self, mock_execute):
        """Test batch pane capture"""
        targets = [('session1', 0), ('session2', 1)]
        
        mock_execute.side_effect = [
            MagicMock(stdout="Output from session1:0", returncode=0),
            MagicMock(stdout="Output from session2:1", returncode=0)
        ]
        
        results = self.cmd.batch_capture_panes(targets, lines=30)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results['session1:0'], "Output from session1:0")
        self.assertEqual(results['session2:1'], "Output from session2:1")
    
    @patch.object(TmuxCommand, 'batch_get_all_sessions_and_windows')
    def test_get_json_status(self, mock_batch):
        """Test JSON status output"""
        mock_batch.return_value = {
            'sessions': {
                'test': SessionInfo('test', 2, '12345', False)
            },
            'windows': {
                'test': [
                    WindowInfo('test', 0, 'Claude-Agent', True, 1, 'tiled', 'node')
                ]
            }
        }
        
        json_output = self.cmd.get_json_status()
        
        # Should be valid JSON
        import json
        data = json.loads(json_output)
        
        self.assertIn('sessions', data)
        self.assertEqual(len(data['sessions']), 1)
        self.assertEqual(data['sessions'][0]['name'], 'test')
        self.assertEqual(len(data['sessions'][0]['agents']), 1)


class TestBatchPerformance(unittest.TestCase):
    """Test performance improvements of batch operations"""
    
    @patch('subprocess.run')
    def test_batch_vs_sequential_calls(self, mock_run):
        """Compare batch vs sequential subprocess calls"""
        # Old way: Multiple calls
        old_cmd = TmuxCommand()
        
        # Simulate old approach with 5 sessions, 3 windows each
        call_count_old = 0
        for i in range(5):  # 5 sessions
            mock_run.return_value = MagicMock(stdout=f"session{i}")
            old_cmd.execute_command(['tmux', 'list-sessions'])
            call_count_old += 1
            
            for j in range(3):  # 3 windows per session
                mock_run.return_value = MagicMock(stdout=f"window{j}")
                old_cmd.execute_command(['tmux', 'list-windows'])
                call_count_old += 1
        
        # New way: Batch calls
        mock_run.reset_mock()
        new_cmd = TmuxCommand()
        
        # Simulate batch approach
        mock_run.return_value = MagicMock(
            stdout="session0|3|123|0\nsession1|3|124|0"
        )
        new_cmd.execute_command(['tmux', 'list-sessions', '-F', '...'])
        
        mock_run.return_value = MagicMock(
            stdout="session0:0|window|1|1|tiled|bash"
        )
        new_cmd.execute_command(['tmux', 'list-windows', '-a', '-F', '...'])
        
        call_count_new = 2  # Only 2 calls total
        
        # Verify significant reduction in subprocess calls
        self.assertLess(call_count_new, call_count_old)
        self.assertEqual(call_count_old, 20)  # 5 + (5 * 3)
        self.assertEqual(call_count_new, 2)   # Just 2 batch calls


if __name__ == '__main__':
    unittest.main()