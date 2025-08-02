#!/usr/bin/env python3
"""Unit tests for refactored claude_control.py"""

import unittest
from unittest.mock import patch, MagicMock, call
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_control_refactored import (
    ClaudeOrchestrator, TmuxCommandExecutor, ClaudeHealthChecker,
    SessionAnalyzer, RegistryManager, SystemHealthChecker,
    StatusFormatter, Agent, Session, AgentStatus
)


class TestTmuxCommandExecutor(unittest.TestCase):
    """Test the TmuxCommandExecutor class"""
    
    def setUp(self):
        self.executor = TmuxCommandExecutor()
    
    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test successful command execution"""
        mock_run.return_value = MagicMock(stdout="output", returncode=0)
        
        result = self.executor.run_command(["tmux", "list-sessions"])
        
        self.assertEqual(result.stdout, "output")
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_run_command_failure(self, mock_run):
        """Test command execution failure"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        with self.assertRaises(subprocess.CalledProcessError):
            self.executor.run_command(["tmux", "invalid"])
    
    @patch('subprocess.run')
    def test_get_sessions(self, mock_run):
        """Test getting tmux sessions"""
        mock_run.return_value = MagicMock(
            stdout="session1:1234567890:3\nsession2:1234567891:2\n",
            returncode=0
        )
        
        sessions = self.executor.get_sessions()
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0], ("session1", "1234567890", 3))
        self.assertEqual(sessions[1], ("session2", "1234567891", 2))


class TestClaudeHealthChecker(unittest.TestCase):
    """Test the ClaudeHealthChecker class"""
    
    def test_check_health_ready(self):
        """Test detecting ready status"""
        output = "Some output\n> Ready for input\n"
        status = ClaudeHealthChecker.check_health(output)
        self.assertEqual(status, AgentStatus.READY)
    
    def test_check_health_error(self):
        """Test detecting error status"""
        output = "Error: Something went wrong\n"
        status = ClaudeHealthChecker.check_health(output)
        self.assertEqual(status, AgentStatus.ERROR)
    
    def test_check_health_busy(self):
        """Test detecting busy status"""
        output = "Processing request...\n"
        status = ClaudeHealthChecker.check_health(output)
        self.assertEqual(status, AgentStatus.BUSY)
    
    def test_check_health_unknown(self):
        """Test unknown status for empty output"""
        status = ClaudeHealthChecker.check_health("")
        self.assertEqual(status, AgentStatus.UNKNOWN)


class TestSessionAnalyzer(unittest.TestCase):
    """Test the SessionAnalyzer class"""
    
    def setUp(self):
        self.mock_executor = MagicMock()
        self.mock_health_checker = MagicMock()
        self.analyzer = SessionAnalyzer(self.mock_executor, self.mock_health_checker)
    
    def test_analyze_session(self):
        """Test analyzing a session"""
        # Mock window data
        self.mock_executor.get_windows.return_value = [
            (0, "Claude-Agent", "node"),
            (1, "Shell", "bash"),
            (2, "Claude-PM", "node")
        ]
        
        # Mock health check results
        self.mock_health_checker.check_health.side_effect = [
            AgentStatus.READY,
            AgentStatus.BUSY
        ]
        
        # Mock pane capture
        self.mock_executor.capture_pane.return_value = "test output"
        
        session = self.analyzer.analyze_session("test-session", "123456", 3)
        
        self.assertEqual(session.name, "test-session")
        self.assertEqual(session.windows, 3)
        self.assertEqual(len(session.agents), 2)
        self.assertEqual(session.agents[0].name, "Claude-Agent")
        self.assertEqual(session.agents[0].status, AgentStatus.READY)
    
    def test_is_claude_window(self):
        """Test Claude window detection"""
        self.assertTrue(self.analyzer._is_claude_window("Claude-Agent", "node"))
        self.assertTrue(self.analyzer._is_claude_window("Random", "claude"))
        self.assertFalse(self.analyzer._is_claude_window("Shell", "bash"))


class TestRegistryManager(unittest.TestCase):
    """Test the RegistryManager class"""
    
    def setUp(self):
        self.temp_path = Path("/tmp/test_registry.json")
        self.registry = RegistryManager(self.temp_path)
    
    def tearDown(self):
        if self.temp_path.exists():
            self.temp_path.unlink()
    
    @patch('builtins.open', create=True)
    @patch('json.dump')
    def test_save_sessions(self, mock_json_dump, mock_open):
        """Test saving sessions to registry"""
        sessions = [
            Session(
                name="test",
                created="123456",
                windows=2,
                agents=[
                    Agent(window=0, name="Claude", status=AgentStatus.READY)
                ]
            )
        ]
        
        self.registry.save_sessions(sessions)
        
        mock_json_dump.assert_called_once()
        saved_data = mock_json_dump.call_args[0][0]
        self.assertIn('updated', saved_data)
        self.assertEqual(len(saved_data['sessions']), 1)
        self.assertEqual(saved_data['sessions'][0]['name'], 'test')


class TestSystemHealthChecker(unittest.TestCase):
    """Test the SystemHealthChecker class"""
    
    @patch('subprocess.run')
    def test_check_tmux_available(self, mock_run):
        """Test checking tmux availability"""
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(SystemHealthChecker.check_tmux())
        
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        self.assertFalse(SystemHealthChecker.check_tmux())
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_check_claude_available(self, mock_exists, mock_run):
        """Test checking Claude availability"""
        mock_exists.return_value = False  # No script exists
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(SystemHealthChecker.check_claude())
        
        mock_run.side_effect = FileNotFoundError()
        self.assertFalse(SystemHealthChecker.check_claude())


class TestStatusFormatter(unittest.TestCase):
    """Test the StatusFormatter class"""
    
    @patch('builtins.print')
    def test_format_status_no_sessions(self, mock_print):
        """Test formatting when no sessions exist"""
        StatusFormatter.format_status([])
        
        # Check that "No active sessions" was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any('No active sessions' in str(call) for call in print_calls))
    
    @patch('builtins.print')
    def test_format_status_with_sessions(self, mock_print):
        """Test formatting with active sessions"""
        sessions = [
            Session(
                name="test-session",
                created="123456",
                windows=2,
                agents=[
                    Agent(window=0, name="Claude", status=AgentStatus.READY)
                ]
            )
        ]
        
        StatusFormatter.format_status(sessions, detailed=True)
        
        # Check that session info was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any('test-session' in str(call) for call in print_calls))
        self.assertTrue(any('Claude' in str(call) for call in print_calls))


class TestClaudeOrchestratorIntegration(unittest.TestCase):
    """Integration tests for ClaudeOrchestrator"""
    
    @patch('pathlib.Path.exists', return_value=True)
    @patch.object(TmuxCommandExecutor, 'get_sessions')
    @patch.object(SessionAnalyzer, 'analyze_session')
    def test_get_active_sessions(self, mock_analyze, mock_get_sessions, mock_exists):
        """Test getting active sessions"""
        mock_get_sessions.return_value = [("test", "123", 2)]
        mock_analyze.return_value = Session(
            name="test",
            created="123",
            windows=2,
            agents=[]
        )
        
        orchestrator = ClaudeOrchestrator()
        sessions = orchestrator.get_active_sessions()
        
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].name, "test")


if __name__ == '__main__':
    unittest.main()