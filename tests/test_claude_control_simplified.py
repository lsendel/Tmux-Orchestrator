#!/usr/bin/env python3
"""Tests for simplified claude_control module"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_control import (
    AgentStatus, TmuxClient, ClaudeMonitor, format_status
)


class TestTmuxClient(unittest.TestCase):
    """Test the simplified TmuxClient"""
    
    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test successful command execution"""
        mock_run.return_value = MagicMock(
            stdout="test output",
            returncode=0
        )
        
        result = TmuxClient.run_command(["tmux", "list-sessions"])
        
        self.assertEqual(result.stdout, "test output")
        mock_run.assert_called_once_with(
            ["tmux", "list-sessions"],
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('subprocess.run')
    def test_run_command_failure(self, mock_run):
        """Test command failure handling"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        with self.assertRaises(subprocess.CalledProcessError):
            TmuxClient.run_command(["tmux", "invalid"])
    
    @patch('subprocess.run')
    def test_get_sessions_empty(self, mock_run):
        """Test getting sessions when none exist"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        sessions = TmuxClient.get_sessions()
        self.assertEqual(sessions, [])
    
    @patch('subprocess.run')
    def test_get_sessions_multiple(self, mock_run):
        """Test getting multiple sessions"""
        mock_run.return_value = MagicMock(
            stdout="session1:123:2\nsession2:456:3\n",
            returncode=0
        )
        
        sessions = TmuxClient.get_sessions()
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]['name'], 'session1')
        self.assertEqual(sessions[0]['windows'], 2)
        self.assertEqual(sessions[1]['name'], 'session2')
        self.assertEqual(sessions[1]['windows'], 3)
    
    @patch('subprocess.run')
    def test_get_windows(self, mock_run):
        """Test getting windows for a session"""
        mock_run.return_value = MagicMock(
            stdout="0:Claude:node\n1:Shell:bash\n2:Server:npm\n",
            returncode=0
        )
        
        windows = TmuxClient.get_windows("test-session")
        
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0]['index'], 0)
        self.assertEqual(windows[0]['name'], 'Claude')
        self.assertEqual(windows[1]['command'], 'bash')
    
    @patch('subprocess.run')
    def test_capture_pane(self, mock_run):
        """Test capturing pane output"""
        mock_run.return_value = MagicMock(
            stdout="Line 1\nLine 2\nLine 3",
            returncode=0
        )
        
        output = TmuxClient.capture_pane("session", 0, 3)
        
        self.assertEqual(output, "Line 1\nLine 2\nLine 3")
        mock_run.assert_called_once_with(
            ["tmux", "capture-pane", "-t", "session:0", "-p", "-S", "-3"],
            capture_output=True,
            text=True,
            check=True
        )


class TestClaudeMonitor(unittest.TestCase):
    """Test the simplified ClaudeMonitor"""
    
    @patch('pathlib.Path.mkdir')
    def setUp(self, mock_mkdir):
        """Set up test monitor"""
        self.monitor = ClaudeMonitor()
    
    def test_check_health_ready(self):
        """Test health check for ready status"""
        output = "Human: What can you help with?"
        status = self.monitor._check_health(output)
        self.assertEqual(status, AgentStatus.READY)
    
    def test_check_health_error(self):
        """Test health check for error status"""
        output = "Error: Connection failed"
        status = self.monitor._check_health(output)
        self.assertEqual(status, AgentStatus.ERROR)
    
    def test_check_health_busy(self):
        """Test health check for busy status"""
        output = "Processing your request..."
        status = self.monitor._check_health(output)
        self.assertEqual(status, AgentStatus.BUSY)
    
    def test_check_health_unknown(self):
        """Test health check for unknown status"""
        output = ""
        status = self.monitor._check_health(output)
        self.assertEqual(status, AgentStatus.UNKNOWN)
    
    def test_is_claude_window(self):
        """Test Claude window detection"""
        self.assertTrue(self.monitor._is_claude_window({
            'name': 'Claude-Agent',
            'command': 'bash'
        }))
        
        self.assertTrue(self.monitor._is_claude_window({
            'name': 'test',
            'command': 'node'
        }))
        
        self.assertFalse(self.monitor._is_claude_window({
            'name': 'Shell',
            'command': 'bash'
        }))
    
    @patch.object(TmuxClient, 'get_sessions')
    @patch.object(TmuxClient, 'get_windows')
    @patch.object(TmuxClient, 'capture_pane')
    def test_get_all_agents(self, mock_capture, mock_windows, mock_sessions):
        """Test getting all agents across sessions"""
        mock_sessions.return_value = [
            {'name': 'test1', 'created': '123', 'windows': 2}
        ]
        mock_windows.return_value = [
            {'index': 0, 'name': 'Claude', 'command': 'node'},
            {'index': 1, 'name': 'Shell', 'command': 'bash'}
        ]
        mock_capture.return_value = "> Ready"
        
        agents = self.monitor.get_all_agents()
        
        self.assertEqual(len(agents), 1)  # Only Claude window
        self.assertEqual(agents[0]['session'], 'test1')
        self.assertEqual(agents[0]['window'], 0)
        self.assertEqual(agents[0]['status'], AgentStatus.READY)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_status(self, mock_json, mock_file):
        """Test saving status to registry"""
        agents = [{
            'session': 'test',
            'session_created': '123',
            'session_windows': 2,
            'window': 0,
            'name': 'Claude',
            'status': AgentStatus.READY,
            'process': 'node'
        }]
        
        self.monitor.save_status(agents)
        
        mock_json.assert_called_once()
        saved_data = mock_json.call_args[0][0]
        self.assertIn('updated', saved_data)
        self.assertIn('sessions', saved_data)
        self.assertEqual(len(saved_data['sessions']), 1)
    
    @patch.object(TmuxClient, 'run_command')
    @patch('subprocess.run')
    def test_health_check(self, mock_run, mock_tmux):
        """Test system health check"""
        # Mock tmux check
        mock_tmux.return_value = MagicMock(returncode=0)
        
        # Mock claude check via script
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock get_all_agents
        with patch.object(self.monitor, 'get_all_agents', return_value=[]):
            health = self.monitor.health_check()
        
        self.assertTrue(health['tmux_available'])
        self.assertTrue(health['claude_available'])
        self.assertEqual(health['active_sessions'], 0)
        self.assertEqual(health['total_agents'], 0)
        self.assertEqual(health['issues'], [])


class TestFormatStatus(unittest.TestCase):
    """Test the format_status function"""
    
    @patch('builtins.print')
    def test_format_status_empty(self, mock_print):
        """Test formatting with no agents"""
        format_status([])
        
        # Check that "No active sessions" was printed
        printed = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
        self.assertIn("No active sessions", printed)
    
    @patch('builtins.print')
    def test_format_status_with_agents(self, mock_print):
        """Test formatting with agents"""
        agents = [{
            'session': 'test-session',
            'session_windows': 3,
            'window': 0,
            'name': 'Claude',
            'status': AgentStatus.READY
        }]
        
        format_status(agents, detailed=True)
        
        # Check that session info was printed
        printed_lines = []
        for call in mock_print.call_args_list:
            if call[0]:  # If there are positional args
                printed_lines.append(str(call[0][0]))
        
        printed = ' '.join(printed_lines)
        self.assertIn("test-session", printed)
        self.assertIn("Claude", printed)
        self.assertIn("ready", printed.lower())


class TestAgentStatus(unittest.TestCase):
    """Test AgentStatus constants"""
    
    def test_status_values(self):
        """Test status constant values"""
        self.assertEqual(AgentStatus.READY, "ready")
        self.assertEqual(AgentStatus.BUSY, "busy")
        self.assertEqual(AgentStatus.ERROR, "error")
        self.assertEqual(AgentStatus.UNKNOWN, "unknown")


if __name__ == '__main__':
    unittest.main()