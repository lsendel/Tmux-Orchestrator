#!/usr/bin/env python3
"""Integration tests for refactored modules"""

import unittest
from unittest.mock import patch, MagicMock, call, mock_open
import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_control_refactored import ClaudeOrchestrator, AgentStatus
from tmux_utils_refactored import TmuxOrchestrator


class TestClaudeAndTmuxIntegration(unittest.TestCase):
    """Integration tests between Claude and Tmux orchestrators"""
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    def test_full_session_discovery_flow(self, mock_exists, mock_run):
        """Test complete flow of discovering sessions with Claude agents"""
        # Setup mock responses for tmux commands
        mock_run.side_effect = [
            # List sessions
            MagicMock(
                stdout="ai-chat:1234567890:3\nbackend:1234567891:2\n",
                returncode=0
            ),
            # List windows for ai-chat
            MagicMock(
                stdout="0:Claude-Frontend:node\n1:Shell:bash\n2:Dev-Server:npm\n",
                returncode=0
            ),
            # Capture pane for Claude window
            MagicMock(
                stdout="Human: Ready to work\n> ",
                returncode=0
            ),
            # List windows for backend
            MagicMock(
                stdout="0:Claude-Backend:node\n1:Server:python\n",
                returncode=0
            ),
            # Capture pane for backend Claude
            MagicMock(
                stdout="Processing task...",
                returncode=0
            )
        ]
        
        # Test with ClaudeOrchestrator
        claude_orch = ClaudeOrchestrator()
        sessions = claude_orch.get_active_sessions()
        
        # Verify sessions were discovered
        self.assertEqual(len(sessions), 2)
        
        # Check first session
        self.assertEqual(sessions[0].name, "ai-chat")
        self.assertEqual(len(sessions[0].agents), 1)
        self.assertEqual(sessions[0].agents[0].name, "Claude-Frontend")
        self.assertEqual(sessions[0].agents[0].status, AgentStatus.READY)
        
        # Check second session
        self.assertEqual(sessions[1].name, "backend")
        self.assertEqual(len(sessions[1].agents), 1)
        self.assertEqual(sessions[1].agents[0].name, "Claude-Backend")
        self.assertEqual(sessions[1].agents[0].status, AgentStatus.BUSY)
    
    @patch('subprocess.run')
    def test_tmux_orchestrator_session_creation(self, mock_run):
        """Test creating a new project session through TmuxOrchestrator"""
        mock_run.return_value = MagicMock(returncode=0)
        
        tmux_orch = TmuxOrchestrator()
        
        # Create a new project session
        result = tmux_orch.create_project_session("test-project", "/path/to/project")
        self.assertTrue(result)
        
        # Add windows to the session
        result = tmux_orch.add_window_to_session("test-project", "Claude-Agent", "/path/to/project")
        self.assertTrue(result)
        
        result = tmux_orch.add_window_to_session("test-project", "Dev-Server", "/path/to/project")
        self.assertTrue(result)
        
        # Verify commands were called
        self.assertEqual(mock_run.call_count, 3)
        
        # Check session creation command
        session_cmd = mock_run.call_args_list[0][0][0]
        self.assertIn("new-session", session_cmd)
        self.assertIn("test-project", session_cmd)
    
    @patch('subprocess.run')
    def test_message_sending_integration(self, mock_run):
        """Test sending messages to Claude agents"""
        mock_run.return_value = MagicMock(returncode=0)
        
        tmux_orch = TmuxOrchestrator()
        
        # Send a message to a Claude agent
        result = tmux_orch.send_message("my-project", "0", "Hello Claude, what's your status?")
        self.assertTrue(result)
        
        # Verify the command
        cmd = mock_run.call_args[0][0]
        self.assertIn("send-keys", cmd)
        self.assertIn("my-project:0", cmd)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_health_check_integration(self, mock_exists, mock_run):
        """Test system health check across both orchestrators"""
        # Mock path exists for various checks
        mock_exists.return_value = True
        
        # Mock in the order health_check will call them:
        # 1. get_active_sessions (list-sessions, list-windows, capture-pane)
        # 2. check_tmux
        # 3. check_claude
        mock_run.side_effect = [
            # get_active_sessions calls
            MagicMock(stdout="session1:123:2\n", returncode=0),  # list-sessions
            MagicMock(stdout="0:Claude:node\n1:Shell:bash\n", returncode=0),  # list-windows
            MagicMock(stdout="> Ready", returncode=0),  # capture-pane
            # check_tmux call
            MagicMock(returncode=0),  # tmux -V
            # check_claude call (via get_claude_command.sh)
            MagicMock(returncode=0, stdout="claude 1.0.0")  # get_claude_command.sh
        ]
        
        claude_orch = ClaudeOrchestrator()
        health = claude_orch.health_check()
        
        self.assertTrue(health['tmux_available'])
        self.assertTrue(health['claude_available'])
        self.assertEqual(health['active_sessions'], 1)
        self.assertEqual(health['total_agents'], 1)
        self.assertEqual(len(health['issues']), 0)
    
    @patch('subprocess.run')
    def test_error_recovery_integration(self, mock_run):
        """Test error recovery across modules"""
        # Simulate various tmux errors
        tmux_orch = TmuxOrchestrator()
        
        # Session creation fails
        mock_run.side_effect = subprocess.CalledProcessError(1, 'tmux')
        result = tmux_orch.create_project_session("fail-project", "/path")
        self.assertFalse(result)
        
        # Message sending with invalid session
        result = tmux_orch.send_message("invalid!session", "0", "test")
        self.assertFalse(result)
        
        # Window output capture fails
        mock_run.side_effect = Exception("Network error")
        result = tmux_orch.get_window_output("session", "0")
        self.assertEqual(result, "")
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    def test_full_workflow_integration(self, mock_exists, mock_run):
        """Test a complete workflow: create session, deploy agent, check status"""
        # Setup mock responses
        mock_run.side_effect = [
            # Create session
            MagicMock(returncode=0),
            # Add Claude window
            MagicMock(returncode=0),
            # Add Server window
            MagicMock(returncode=0),
            # Send message to Claude
            MagicMock(returncode=0),
            # Check status - list sessions
            MagicMock(stdout="test-workflow:123:2\n", returncode=0),
            # List windows
            MagicMock(stdout="0:Claude-Agent:node\n1:Server:npm\n", returncode=0),
            # Capture Claude output
            MagicMock(stdout="I'm analyzing the project...", returncode=0)
        ]
        
        # Create session with TmuxOrchestrator
        tmux_orch = TmuxOrchestrator()
        
        # Step 1: Create project session
        self.assertTrue(tmux_orch.create_project_session("test-workflow", "/tmp/test"))
        
        # Step 2: Add windows
        self.assertTrue(tmux_orch.add_window_to_session("test-workflow", "Claude-Agent", "/tmp/test"))
        self.assertTrue(tmux_orch.add_window_to_session("test-workflow", "Server", "/tmp/test"))
        
        # Step 3: Send briefing to Claude
        self.assertTrue(tmux_orch.send_message("test-workflow", "0", "Please analyze this project"))
        
        # Step 4: Check status with ClaudeOrchestrator
        claude_orch = ClaudeOrchestrator()
        sessions = claude_orch.get_active_sessions()
        
        # Verify the session was created and Claude is working
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].name, "test-workflow")
        self.assertEqual(len(sessions[0].agents), 1)
        self.assertEqual(sessions[0].agents[0].status, AgentStatus.BUSY)
    
    @patch('subprocess.run')
    def test_concurrent_session_management(self, mock_run):
        """Test managing multiple sessions concurrently"""
        # Mock multiple sessions - fix the test to work correctly
        mock_run.side_effect = [
            # Get all sessions
            MagicMock(
                stdout="frontend:123:3\nbackend:124:2\ninfra:125:4\n",
                returncode=0
            ),
            # Windows for frontend
            MagicMock(stdout="0:Claude-Frontend:node\n1:Shell:bash\n2:Server:npm\n", returncode=0),
            # Capture pane for Claude-Frontend
            MagicMock(stdout="> Ready", returncode=0),
            
            # Windows for backend  
            MagicMock(stdout="0:Claude-Backend:node\n1:Database:psql\n", returncode=0),
            # Capture pane for Claude-Backend
            MagicMock(stdout="Error: Database connection failed", returncode=0),
            
            # Windows for infra
            MagicMock(stdout="0:Claude-DevOps:node\n1:Claude-Monitor:node\n2:Shell:bash\n3:Logs:tail\n", returncode=0),
            # Capture panes for infra agents
            MagicMock(stdout="Deploying...", returncode=0),  # Claude-DevOps
            MagicMock(stdout="Monitoring systems", returncode=0)  # Claude-Monitor
        ]
        
        with patch('pathlib.Path.exists', return_value=True):
            claude_orch = ClaudeOrchestrator()
            sessions = claude_orch.get_active_sessions()
        
        # Verify all sessions discovered
        self.assertEqual(len(sessions), 3)
        
        # Check agent counts
        self.assertEqual(len(sessions[0].agents), 1)  # frontend
        self.assertEqual(len(sessions[1].agents), 1)  # backend
        self.assertEqual(len(sessions[2].agents), 2)  # infra has 2 agents
        
        # Check statuses
        self.assertEqual(sessions[0].agents[0].status, AgentStatus.READY)
        self.assertEqual(sessions[1].agents[0].status, AgentStatus.ERROR)
        self.assertEqual(sessions[2].agents[0].status, AgentStatus.BUSY)
        self.assertEqual(sessions[2].agents[1].status, AgentStatus.BUSY)


class TestRegistryIntegration(unittest.TestCase):
    """Test registry persistence integration"""
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    @patch('subprocess.run')
    @patch('pathlib.Path.exists', return_value=True)
    def test_registry_save_and_status(self, mock_exists, mock_run, mock_json_dump, mock_file):
        """Test saving session state to registry"""
        # Mock session discovery
        mock_run.side_effect = [
            MagicMock(stdout="test:123:1\n", returncode=0),
            MagicMock(stdout="0:Claude:node\n", returncode=0),
            MagicMock(stdout="> Ready", returncode=0)
        ]
        
        claude_orch = ClaudeOrchestrator()
        claude_orch.status()
        
        # Verify registry was saved
        mock_json_dump.assert_called_once()
        saved_data = mock_json_dump.call_args[0][0]
        
        self.assertIn('updated', saved_data)
        self.assertIn('sessions', saved_data)
        self.assertEqual(len(saved_data['sessions']), 1)
        self.assertEqual(saved_data['sessions'][0]['name'], 'test')
        self.assertEqual(len(saved_data['sessions'][0]['agents']), 1)


if __name__ == '__main__':
    unittest.main()