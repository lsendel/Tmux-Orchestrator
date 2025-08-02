#!/usr/bin/env python3
"""Extended unit tests for refactored claude_control.py to improve coverage"""

import unittest
from unittest.mock import patch, MagicMock, call, mock_open
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_control_refactored import (
    ClaudeOrchestrator, TmuxCommandExecutor, ClaudeHealthChecker,
    SessionAnalyzer, RegistryManager, SystemHealthChecker,
    StatusFormatter, Agent, Session, AgentStatus, main
)


class TestTmuxCommandExecutorExtended(unittest.TestCase):
    """Extended tests for TmuxCommandExecutor"""
    
    @patch('subprocess.run')
    def test_run_command_unexpected_error(self, mock_run):
        """Test handling of unexpected errors"""
        mock_run.side_effect = Exception("Unexpected error")
        
        with self.assertRaises(Exception):
            TmuxCommandExecutor.run_command(["tmux", "test"])
    
    @patch('subprocess.run')
    def test_get_sessions_empty_output(self, mock_run):
        """Test get_sessions with empty output"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        
        sessions = TmuxCommandExecutor.get_sessions()
        self.assertEqual(sessions, [])
    
    @patch('subprocess.run')
    def test_get_sessions_malformed_output(self, mock_run):
        """Test get_sessions with malformed output"""
        mock_run.return_value = MagicMock(
            stdout="incomplete:line\nvalid:123:3\n",
            returncode=0
        )
        
        sessions = TmuxCommandExecutor.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0][0], "valid")
    
    @patch('subprocess.run')
    def test_get_windows_empty_output(self, mock_run):
        """Test get_windows with empty output"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        
        windows = TmuxCommandExecutor.get_windows("session")
        self.assertEqual(windows, [])
    
    @patch('subprocess.run')
    def test_get_windows_malformed_output(self, mock_run):
        """Test get_windows with malformed output"""
        mock_run.return_value = MagicMock(
            stdout="incomplete\n0:valid:bash\n",
            returncode=0
        )
        
        windows = TmuxCommandExecutor.get_windows("session")
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0][1], "valid")
    
    @patch('subprocess.run')
    def test_capture_pane_empty(self, mock_run):
        """Test capture_pane with empty output"""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        
        output = TmuxCommandExecutor.capture_pane("session", "0")
        self.assertEqual(output, "")


class TestClaudeHealthCheckerExtended(unittest.TestCase):
    """Extended tests for ClaudeHealthChecker"""
    
    def test_check_health_multiple_indicators(self):
        """Test health check with multiple indicators"""
        # Ready indicator takes precedence
        output = "Error: something\n> Ready\n"
        status = ClaudeHealthChecker.check_health(output)
        self.assertEqual(status, AgentStatus.READY)
        
        # Error without ready
        output = "Error: critical failure\nProcessing..."
        status = ClaudeHealthChecker.check_health(output)
        self.assertEqual(status, AgentStatus.ERROR)
    
    def test_check_health_human_prompt(self):
        """Test detecting Human: prompt as ready"""
        output = "Human: What can you help with?"
        status = ClaudeHealthChecker.check_health(output)
        self.assertEqual(status, AgentStatus.READY)
    
    def test_check_health_various_ready_states(self):
        """Test various ready state indicators"""
        ready_outputs = [
            "I'll help you with that",
            "I can help with your request",
            "Ready to assist"
        ]
        
        for output in ready_outputs:
            status = ClaudeHealthChecker.check_health(output)
            self.assertEqual(status, AgentStatus.READY)


class TestSystemHealthCheckerExtended(unittest.TestCase):
    """Extended tests for SystemHealthChecker"""
    
    @patch('subprocess.run')
    def test_check_tmux_file_not_found(self, mock_run):
        """Test tmux check with FileNotFoundError"""
        mock_run.side_effect = FileNotFoundError()
        self.assertFalse(SystemHealthChecker.check_tmux())
    
    @patch('pathlib.Path.exists')
    @patch('subprocess.run')
    def test_check_claude_with_script(self, mock_run, mock_exists):
        """Test claude check using script"""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        
        self.assertTrue(SystemHealthChecker.check_claude())
        
        # Verify script was called
        call_args = mock_run.call_args[0][0]
        self.assertTrue(any('get_claude_command.sh' in str(arg) for arg in call_args))
    
    @patch('pathlib.Path.exists')
    @patch('subprocess.run')
    def test_check_claude_script_fails(self, mock_run, mock_exists):
        """Test claude check when script fails"""
        mock_exists.return_value = True
        
        # Script fails, direct check succeeds
        mock_run.side_effect = [
            Exception("Script error"),
            MagicMock(returncode=0)
        ]
        
        self.assertTrue(SystemHealthChecker.check_claude())
        self.assertEqual(mock_run.call_count, 2)


class TestSessionAnalyzerExtended(unittest.TestCase):
    """Extended tests for SessionAnalyzer"""
    
    def setUp(self):
        self.mock_executor = MagicMock()
        self.mock_health_checker = MagicMock()
        self.analyzer = SessionAnalyzer(self.mock_executor, self.mock_health_checker)
    
    def test_find_agents_no_claude_windows(self):
        """Test finding agents when no Claude windows exist"""
        self.mock_executor.get_windows.return_value = [
            (0, "Shell", "bash"),
            (1, "Server", "npm")
        ]
        
        agents = self.analyzer._find_agents_in_session("test")
        self.assertEqual(len(agents), 0)
    
    def test_is_claude_window_edge_cases(self):
        """Test Claude window detection edge cases"""
        # The function is case-sensitive, so these should be False
        self.assertFalse(self.analyzer._is_claude_window("CLAUDE", "bash"))
        self.assertFalse(self.analyzer._is_claude_window("test", "NODE"))
        
        # But these should match
        self.assertTrue(self.analyzer._is_claude_window("Claude-Agent", "bash"))
        self.assertTrue(self.analyzer._is_claude_window("Test", "node"))


class TestRegistryManagerExtended(unittest.TestCase):
    """Extended tests for RegistryManager"""
    
    def setUp(self):
        self.temp_path = Path("/tmp/test_registry_extended.json")
        self.registry = RegistryManager(self.temp_path)
    
    def tearDown(self):
        if self.temp_path.exists():
            self.temp_path.unlink()
    
    def test_registry_creates_parent_directory(self):
        """Test that registry creates parent directory if needed"""
        non_existent_path = Path("/tmp/test_new_dir/registry.json")
        registry = RegistryManager(non_existent_path)
        self.assertTrue(non_existent_path.parent.exists())
        # Cleanup
        if non_existent_path.parent.exists():
            non_existent_path.parent.rmdir()
    
    def test_session_to_dict_multiple_agents(self):
        """Test converting session with multiple agents to dict"""
        session = Session(
            name="test",
            created="12345",
            windows=3,
            agents=[
                Agent(0, "Claude1", AgentStatus.READY, "node"),
                Agent(2, "Claude2", AgentStatus.BUSY, "node")
            ]
        )
        
        result = self.registry._session_to_dict(session)
        
        self.assertEqual(result['name'], 'test')
        self.assertEqual(len(result['agents']), 2)
        self.assertEqual(result['agents'][0]['status'], 'ready')
        self.assertEqual(result['agents'][1]['status'], 'busy')


class TestStatusFormatterExtended(unittest.TestCase):
    """Extended tests for StatusFormatter"""
    
    @patch('builtins.print')
    def test_format_status_detailed_no_agents(self, mock_print):
        """Test detailed status with session but no agents"""
        sessions = [
            Session(name="empty", created="123", windows=2, agents=[])
        ]
        
        StatusFormatter.format_status(sessions, detailed=True)
        
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any('empty' in str(call) for call in print_calls))
        self.assertTrue(any('Agents: 0' in str(call) for call in print_calls))
    
    @patch('builtins.print')
    def test_format_session_all_statuses(self, mock_print):
        """Test formatting session with all agent statuses"""
        sessions = [
            Session(
                name="test",
                created="123",
                windows=4,
                agents=[
                    Agent(0, "Ready", AgentStatus.READY),
                    Agent(1, "Busy", AgentStatus.BUSY),
                    Agent(2, "Error", AgentStatus.ERROR),
                    Agent(3, "Unknown", AgentStatus.UNKNOWN)
                ]
            )
        ]
        
        StatusFormatter.format_status(sessions, detailed=True)
        
        # Check all statuses are displayed
        print_calls = [str(call) for call in mock_print.call_args_list]
        all_output = ' '.join(str(call) for call in print_calls)
        
        self.assertIn('ready', all_output)
        self.assertIn('busy', all_output)
        self.assertIn('error', all_output)
        self.assertIn('unknown', all_output)


class TestClaudeOrchestratorExtended(unittest.TestCase):
    """Extended tests for ClaudeOrchestrator"""
    
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.mkdir')
    @patch('logging.basicConfig')
    def test_init_logging_setup(self, mock_logging, mock_mkdir, mock_exists):
        """Test that init sets up logging correctly"""
        orchestrator = ClaudeOrchestrator()
        
        mock_logging.assert_called_once()
        self.assertIsNotNone(orchestrator.logger)
    
    @patch('pathlib.Path.exists', return_value=True)
    @patch.object(ClaudeOrchestrator, 'get_active_sessions')
    @patch.object(StatusFormatter, 'format_status')
    @patch.object(RegistryManager, 'save_sessions')
    def test_status_saves_registry(self, mock_save, mock_format, mock_get, mock_exists):
        """Test that status saves registry"""
        sessions = [Session("test", "123", 1, [])]
        mock_get.return_value = sessions
        
        orchestrator = ClaudeOrchestrator()
        orchestrator.status()
        
        mock_save.assert_called_once_with(sessions)
    
    @patch('pathlib.Path.exists', return_value=True)
    def test_health_check_all_issues(self, mock_exists):
        """Test health check with all components failing"""
        orchestrator = ClaudeOrchestrator()
        
        with patch.object(orchestrator, 'get_active_sessions', return_value=[]):
            with patch.object(orchestrator.health, 'check_tmux', return_value=False):
                with patch.object(orchestrator.health, 'check_claude', return_value=False):
                    health = orchestrator.health_check()
        
        self.assertFalse(health['tmux_available'])
        self.assertFalse(health['claude_available'])
        self.assertEqual(len(health['issues']), 2)
        self.assertIn('tmux not found', health['issues'])
        self.assertIn('claude command not found', health['issues'])


class TestMainFunction(unittest.TestCase):
    """Test the main function"""
    
    @patch('sys.argv', ['claude_control_refactored.py'])
    @patch('claude_control_refactored.ClaudeOrchestrator')
    def test_main_no_args_calls_status(self, mock_orchestrator_class):
        """Test main with no arguments calls status"""
        mock_orchestrator = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        main()
        
        mock_orchestrator.status.assert_called_once_with()
    
    @patch('sys.argv', ['claude_control_refactored.py', 'status'])
    @patch('claude_control_refactored.ClaudeOrchestrator')
    def test_main_status_not_detailed(self, mock_orchestrator_class):
        """Test main with status (not detailed)"""
        mock_orchestrator = MagicMock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        main()
        
        mock_orchestrator.status.assert_called_once_with(False)
    
    @patch('sys.argv', ['claude_control_refactored.py', 'health'])
    @patch('builtins.print')
    @patch('claude_control_refactored.ClaudeOrchestrator')
    def test_main_health(self, mock_orchestrator_class, mock_print):
        """Test main with health command"""
        mock_orchestrator = MagicMock()
        mock_orchestrator.health_check.return_value = {'test': 'data'}
        mock_orchestrator_class.return_value = mock_orchestrator
        
        main()
        
        mock_orchestrator.health_check.assert_called_once()
        # Check JSON output
        print_args = mock_print.call_args[0][0]
        parsed = json.loads(print_args)
        self.assertEqual(parsed['test'], 'data')
    
    @patch('sys.argv', ['claude_control_refactored.py', 'invalid'])
    @patch('builtins.print')
    def test_main_invalid_command(self, mock_print):
        """Test main with invalid command"""
        with self.assertRaises(SystemExit) as context:
            main()
        
        self.assertEqual(context.exception.code, 1)
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(any('Unknown command: invalid' in call for call in print_calls))
    
    @patch('sys.argv', ['claude_control_refactored.py'])
    @patch('claude_control_refactored.ClaudeOrchestrator')
    @patch('logging.error')
    def test_main_exception_handling(self, mock_log, mock_orchestrator_class):
        """Test main handles exceptions properly"""
        mock_orchestrator_class.side_effect = Exception("Test error")
        
        with self.assertRaises(SystemExit) as context:
            main()
        
        self.assertEqual(context.exception.code, 1)
        mock_log.assert_called_once()


class TestEnumAndDataclasses(unittest.TestCase):
    """Test enum and dataclass functionality"""
    
    def test_agent_status_enum_values(self):
        """Test AgentStatus enum values"""
        self.assertEqual(AgentStatus.READY.value, "ready")
        self.assertEqual(AgentStatus.BUSY.value, "busy")
        self.assertEqual(AgentStatus.ERROR.value, "error")
        self.assertEqual(AgentStatus.UNKNOWN.value, "unknown")
    
    def test_agent_dataclass_defaults(self):
        """Test Agent dataclass with defaults"""
        agent = Agent(window=0, name="Test", status=AgentStatus.READY)
        self.assertEqual(agent.process, "")
        
        agent_with_process = Agent(0, "Test", AgentStatus.READY, "node")
        self.assertEqual(agent_with_process.process, "node")
    
    def test_session_dataclass(self):
        """Test Session dataclass"""
        agents = [Agent(0, "Claude", AgentStatus.READY)]
        session = Session("test", "12345", 3, agents)
        
        self.assertEqual(session.name, "test")
        self.assertEqual(session.created, "12345")
        self.assertEqual(session.windows, 3)
        self.assertEqual(len(session.agents), 1)


if __name__ == '__main__':
    unittest.main()