#!/usr/bin/env python3
"""Tests for edge cases and formatting functions"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_control import format_status, AgentStatus
from tmux_utils import TmuxManager, WindowType


class TestFormatStatusEdgeCases(unittest.TestCase):
    """Test edge cases in format_status function"""
    
    @patch('builtins.print')
    def test_format_status_single_agent_detailed(self, mock_print):
        """Test format_status with single agent in detailed mode"""
        agents = [{
            'session': 'single-session',
            'session_windows': 1,
            'window': 0,
            'name': 'Solo-Agent',
            'status': AgentStatus.ERROR,
            'process': 'node'
        }]
        
        format_status(agents, detailed=True)
        
        # Verify output contains expected elements
        printed_lines = []
        for call in mock_print.call_args_list:
            if call[0]:
                printed_lines.append(str(call[0][0]))
        
        output = '\n'.join(printed_lines)
        self.assertIn('single-session', output)
        self.assertIn('Solo-Agent', output)
        self.assertIn('error', output.lower())
        self.assertIn('\033[0;31m', output)  # Red color for error
    
    @patch('builtins.print')
    def test_format_status_unknown_status(self, mock_print):
        """Test format_status with unknown status"""
        agents = [{
            'session': 'test',
            'session_windows': 2,
            'window': 1,
            'name': 'Mystery-Agent',
            'status': AgentStatus.UNKNOWN
        }]
        
        format_status(agents, detailed=True)
        
        printed_lines = []
        for call in mock_print.call_args_list:
            if call[0]:
                printed_lines.append(str(call[0][0]))
        
        output = '\n'.join(printed_lines)
        self.assertIn('unknown', output.lower())
        self.assertIn('\033[0;34m', output)  # Blue color for unknown
    
    @patch('builtins.print')
    def test_format_status_multiple_sessions_no_detail(self, mock_print):
        """Test format_status with multiple sessions without detail"""
        agents = [
            {
                'session': 'project-a',
                'session_windows': 3,
                'window': 0,
                'name': 'Agent-A',
                'status': AgentStatus.READY
            },
            {
                'session': 'project-b',
                'session_windows': 2,
                'window': 1,
                'name': 'Agent-B',
                'status': AgentStatus.BUSY
            }
        ]
        
        format_status(agents, detailed=False)
        
        printed_lines = []
        for call in mock_print.call_args_list:
            if call[0]:
                printed_lines.append(str(call[0][0]))
        
        output = '\n'.join(printed_lines)
        self.assertIn('project-a', output)
        self.assertIn('project-b', output)
        self.assertIn('Active Sessions: 2', output)
        self.assertIn('Total Agents: 2', output)
        # Should not contain individual agent details
        self.assertNotIn('Agent-A', output)
        self.assertNotIn('Agent-B', output)
    
    @patch('builtins.print')
    def test_format_status_missing_session_windows(self, mock_print):
        """Test format_status with missing session_windows"""
        agents = [{
            'session': 'incomplete',
            'window': 0,
            'name': 'Test-Agent',
            'status': AgentStatus.READY
        }]
        
        format_status(agents, detailed=False)
        
        printed_lines = []
        for call in mock_print.call_args_list:
            if call[0]:
                printed_lines.append(str(call[0][0]))
        
        output = '\n'.join(printed_lines)
        self.assertIn('Windows: unknown', output)
    
    @patch('builtins.print')
    def test_format_status_custom_status(self, mock_print):
        """Test format_status with non-standard status"""
        agents = [{
            'session': 'test',
            'session_windows': 1,
            'window': 0,
            'name': 'Custom-Agent',
            'status': 'custom_status'  # Not in AgentStatus
        }]
        
        format_status(agents, detailed=True)
        
        printed_lines = []
        for call in mock_print.call_args_list:
            if call[0]:
                printed_lines.append(str(call[0][0]))
        
        output = '\n'.join(printed_lines)
        self.assertIn('custom_status', output)
        # Should not have color code (uses default)


class TestTmuxManagerEdgeCases(unittest.TestCase):
    """Test edge cases in TmuxManager"""
    
    def setUp(self):
        self.manager = TmuxManager()
    
    def test_validate_session_name_whitespace_only(self):
        """Test validate_session_name with whitespace only"""
        self.assertFalse(self.manager.validate_session_name("   "))
        self.assertFalse(self.manager.validate_session_name("\t"))
        self.assertFalse(self.manager.validate_session_name("\n"))
    
    def test_validate_session_name_special_chars(self):
        """Test validate_session_name with each special character"""
        for char in self.manager.INVALID_CHARS:
            self.assertFalse(
                self.manager.validate_session_name(f"test{char}session"),
                f"Failed to reject character: {char}"
            )
    
    def test_validate_window_index_string_numbers(self):
        """Test validate_window_index with string numbers"""
        self.assertTrue(self.manager.validate_window_index("0"))
        self.assertTrue(self.manager.validate_window_index("42"))
        self.assertFalse(self.manager.validate_window_index("0.5"))
        self.assertFalse(self.manager.validate_window_index("1e10"))
    
    def test_sanitize_keys_multiple_quotes(self):
        """Test sanitize_keys with multiple quotes"""
        result = self.manager.sanitize_keys("echo 'test' && echo 'another'")
        self.assertEqual(result, "echo '\"'\"'test'\"'\"' && echo '\"'\"'another'\"'\"'")
    
    def test_sanitize_keys_empty_string(self):
        """Test sanitize_keys with empty string"""
        result = self.manager.sanitize_keys("")
        self.assertEqual(result, "")
    
    def test_determine_window_type_mixed_case(self):
        """Test _determine_window_type with mixed case"""
        # Claude indicator
        self.assertEqual(
            self.manager._determine_window_type("CLAUDE-AGENT", "NODE"),
            WindowType.CLAUDE
        )
        
        # Server indicator
        self.assertEqual(
            self.manager._determine_window_type("Dev-Server", "NPM run dev"),
            WindowType.SERVER
        )
        
        # Shell indicator
        self.assertEqual(
            self.manager._determine_window_type("Terminal", "BASH"),
            WindowType.SHELL
        )
    
    def test_determine_window_type_partial_match(self):
        """Test _determine_window_type with partial matches"""
        # Contains 'run' which matches server patterns
        self.assertEqual(
            self.manager._determine_window_type("Runtime", "python"),
            WindowType.SERVER  # 'run' in window patterns matches server
        )
        
        # Contains 'sh' which matches shell patterns
        self.assertEqual(
            self.manager._determine_window_type("Dashboard", "app"),
            WindowType.SHELL  # 'sh' in window name matches shell
        )
    
    @patch('subprocess.run')
    def test_capture_window_output_max_lines(self, mock_run):
        """Test capture_window_output with lines > 1000"""
        mock_run.return_value = MagicMock(stdout="test", returncode=0)
        
        self.manager.capture_window_output("session", 0, lines=5000)
        
        # Should cap at 1000
        cmd = mock_run.call_args[0][0]
        self.assertIn("-1000", cmd)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_session_with_nonexistent_dir(self, mock_exists, mock_run):
        """Test create_session with start_dir that doesn't exist"""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.create_session("test", "/nonexistent")
        
        # Should still create session but without -c flag
        self.assertTrue(result)
        cmd = mock_run.call_args[0][0]
        self.assertNotIn("-c", cmd)
        self.assertNotIn("/nonexistent", cmd)
    
    @patch('subprocess.run')
    def test_execute_command_logs_on_debug(self, mock_run):
        """Test execute_command logs command in debug mode"""
        mock_run.return_value = MagicMock(returncode=0)
        
        with patch.object(self.manager.logger, 'debug') as mock_debug:
            self.manager.execute_command(["test", "command"])
            
        mock_debug.assert_called_once()
        self.assertIn("test command", str(mock_debug.call_args))
    
    @patch('subprocess.run')
    def test_execute_command_unexpected_error(self, mock_run):
        """Test execute_command with unexpected error type"""
        mock_run.side_effect = ValueError("Unexpected error type")
        
        with patch.object(self.manager.logger, 'error') as mock_error:
            with self.assertRaises(ValueError):
                self.manager.execute_command(["test"])
            
        mock_error.assert_called_once()
        self.assertIn("Unexpected error", str(mock_error.call_args))
    
    @patch('subprocess.run')
    def test_get_session_windows_invalid_window_format(self, mock_run):
        """Test _get_session_windows with invalid window format"""
        mock_run.return_value = MagicMock(
            stdout="not_a_number:Window:bash\n1:Valid:zsh\n",
            returncode=0
        )
        
        with patch.object(self.manager.logger, 'warning') as mock_warning:
            windows = self.manager._get_session_windows("test")
        
        self.assertEqual(len(windows), 1)  # Only valid window
        mock_warning.assert_called_once()
        self.assertIn("Invalid window format", str(mock_warning.call_args))


if __name__ == '__main__':
    unittest.main()