#!/usr/bin/env python3
"""Unit tests for claude_control.py"""

import unittest
from unittest.mock import patch, MagicMock, call
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_control import ClaudeOrchestrator


class TestClaudeOrchestrator(unittest.TestCase):
    """Test cases for ClaudeOrchestrator class"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock the file existence check to avoid RuntimeError
        with patch('pathlib.Path.exists', return_value=True):
            self.orchestrator = ClaudeOrchestrator()

    @patch('pathlib.Path.exists')
    def test_init_security_check_fails(self, mock_exists):
        """Test that init fails when security check fails"""
        mock_exists.return_value = False
        with self.assertRaises(RuntimeError) as context:
            ClaudeOrchestrator()
        self.assertIn("Security check failed", str(context.exception))

    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.exists', return_value=True)
    def test_init_creates_directories(self, mock_exists, mock_mkdir):
        """Test that init creates necessary directories"""
        orchestrator = ClaudeOrchestrator()
        # Should create registry and logs directories
        self.assertEqual(mock_mkdir.call_count, 2)

    @patch('subprocess.run')
    def test_get_active_sessions_success(self, mock_run):
        """Test getting active sessions successfully"""
        mock_run.return_value = MagicMock(
            stdout="test-session:1234567890:3\nother-session:1234567891:2\n",
            returncode=0
        )
        
        with patch.object(self.orchestrator, '_get_session_agents', return_value=[]):
            sessions = self.orchestrator.get_active_sessions()
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]['name'], 'test-session')
        self.assertEqual(sessions[0]['windows'], 3)
        self.assertEqual(sessions[1]['name'], 'other-session')
        self.assertEqual(sessions[1]['windows'], 2)

    @patch('subprocess.run')
    def test_get_active_sessions_no_sessions(self, mock_run):
        """Test getting active sessions when none exist"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        sessions = self.orchestrator.get_active_sessions()
        self.assertEqual(sessions, [])

    @patch('subprocess.run')
    def test_get_session_agents(self, mock_run):
        """Test getting agents in a session"""
        mock_run.return_value = MagicMock(
            stdout="0:Claude-Agent:node\n1:Shell:zsh\n2:Claude-PM:node\n",
            returncode=0
        )
        
        with patch.object(self.orchestrator, '_check_agent_health', return_value='ready'):
            agents = self.orchestrator._get_session_agents('test-session')
        
        self.assertEqual(len(agents), 2)  # Only Claude windows
        self.assertEqual(agents[0]['name'], 'Claude-Agent')
        self.assertEqual(agents[1]['name'], 'Claude-PM')

    @patch('subprocess.run')
    def test_check_agent_health_ready(self, mock_run):
        """Test checking agent health - ready state"""
        mock_run.return_value = MagicMock(
            stdout="Some output\n> Ready for input\n",
            returncode=0
        )
        
        status = self.orchestrator._check_agent_health('session', '0')
        self.assertEqual(status, 'ready')

    @patch('subprocess.run')
    def test_check_agent_health_error(self, mock_run):
        """Test checking agent health - error state"""
        mock_run.return_value = MagicMock(
            stdout="Error: Something went wrong\n",
            returncode=0
        )
        
        status = self.orchestrator._check_agent_health('session', '0')
        self.assertEqual(status, 'error')

    @patch('subprocess.run')
    def test_check_agent_health_busy(self, mock_run):
        """Test checking agent health - busy state"""
        mock_run.return_value = MagicMock(
            stdout="Processing request...\n",
            returncode=0
        )
        
        status = self.orchestrator._check_agent_health('session', '0')
        self.assertEqual(status, 'busy')

    @patch('subprocess.run')
    def test_check_agent_health_exception(self, mock_run):
        """Test checking agent health - exception handling"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        
        with patch('logging.warning') as mock_log:
            status = self.orchestrator._check_agent_health('session', '0')
        
        self.assertEqual(status, 'unknown')
        mock_log.assert_called_once()

    @patch('claude_control.print')
    def test_status_no_sessions(self, mock_print):
        """Test status output when no sessions exist"""
        with patch.object(self.orchestrator, 'get_active_sessions', return_value=[]):
            self.orchestrator.status()
        
        # Check that "No active sessions" message was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any('No active sessions' in call for call in print_calls))

    @patch('claude_control.print')
    def test_status_with_sessions(self, mock_print):
        """Test status output with active sessions"""
        mock_sessions = [{
            'name': 'test-session',
            'windows': 3,
            'agents': [
                {'window': 0, 'name': 'Claude-Agent', 'status': 'ready'},
                {'window': 2, 'name': 'Claude-PM', 'status': 'busy'}
            ]
        }]
        
        with patch.object(self.orchestrator, 'get_active_sessions', return_value=mock_sessions):
            self.orchestrator.status(detailed=True)
        
        # Check that session info was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any('test-session' in call for call in print_calls))
        self.assertTrue(any('Claude-Agent' in call for call in print_calls))

    @patch('builtins.open', create=True)
    @patch('json.dump')
    def test_save_registry(self, mock_json_dump, mock_open):
        """Test saving registry to file"""
        mock_sessions = [{'name': 'test', 'windows': 1, 'agents': []}]
        
        with patch.object(self.orchestrator, 'get_active_sessions', return_value=mock_sessions):
            self.orchestrator.save_registry()
        
        # Check that json.dump was called with correct data
        mock_json_dump.assert_called_once()
        saved_data = mock_json_dump.call_args[0][0]
        self.assertIn('updated', saved_data)
        self.assertEqual(saved_data['sessions'], mock_sessions)

    @patch('subprocess.run')
    def test_check_tmux_available(self, mock_run):
        """Test checking if tmux is available"""
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.orchestrator._check_tmux())
        
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        self.assertFalse(self.orchestrator._check_tmux())

    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    def test_check_claude_available(self, mock_exists, mock_run):
        """Test checking if claude is available"""
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.orchestrator._check_claude())
        
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(self.orchestrator._check_claude())

    def test_health_check(self):
        """Test system health check"""
        with patch.object(self.orchestrator, '_check_tmux', return_value=True):
            with patch.object(self.orchestrator, '_check_claude', return_value=False):
                with patch.object(self.orchestrator, 'get_active_sessions', return_value=[]):
                    health = self.orchestrator.health_check()
        
        self.assertIn('timestamp', health)
        self.assertTrue(health['tmux_available'])
        self.assertFalse(health['claude_available'])
        self.assertEqual(health['active_sessions'], 0)
        self.assertIn('claude command not found', health['issues'])


class TestMainFunction(unittest.TestCase):
    """Test cases for main() function"""

    @patch('sys.argv', ['claude_control.py'])
    @patch('claude_control.ClaudeOrchestrator')
    def test_main_no_args(self, mock_orchestrator_class):
        """Test main with no arguments"""
        mock_orchestrator = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        from claude_control import main
        main()
        
        mock_orchestrator.status.assert_called_once_with()

    @patch('sys.argv', ['claude_control.py', 'status'])
    @patch('claude_control.ClaudeOrchestrator')
    def test_main_status(self, mock_orchestrator_class):
        """Test main with status command"""
        mock_orchestrator = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        from claude_control import main
        main()
        
        mock_orchestrator.status.assert_called_once_with(False)

    @patch('sys.argv', ['claude_control.py', 'status', 'detailed'])
    @patch('claude_control.ClaudeOrchestrator')
    def test_main_status_detailed(self, mock_orchestrator_class):
        """Test main with status detailed command"""
        mock_orchestrator = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        from claude_control import main
        main()
        
        mock_orchestrator.status.assert_called_once_with(True)

    @patch('sys.argv', ['claude_control.py', 'health'])
    @patch('claude_control.print')
    @patch('claude_control.ClaudeOrchestrator')
    def test_main_health(self, mock_orchestrator_class, mock_print):
        """Test main with health command"""
        mock_orchestrator = MagicMock()
        mock_orchestrator.health_check.return_value = {'test': 'data'}
        mock_orchestrator_class.return_value = mock_orchestrator
        
        from claude_control import main
        main()
        
        mock_orchestrator.health_check.assert_called_once()
        # Check that JSON was printed
        mock_print.assert_called_with('{\n  "test": "data"\n}')

    @patch('sys.argv', ['claude_control.py', 'invalid'])
    @patch('claude_control.print')
    def test_main_invalid_command(self, mock_print):
        """Test main with invalid command"""
        from claude_control import main
        
        with self.assertRaises(SystemExit) as context:
            main()
        
        self.assertEqual(context.exception.code, 1)
        # Check that error message was printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(any('Unknown command: invalid' in call for call in print_calls))


if __name__ == '__main__':
    unittest.main()