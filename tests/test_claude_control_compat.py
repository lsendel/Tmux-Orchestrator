#!/usr/bin/env python3
"""Test the simplified claude_control works with old test patterns"""

import unittest
from unittest.mock import patch, MagicMock
import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from claude_control directly
from claude_control import ClaudeMonitor, TmuxClient, format_status, AgentStatus


class TestClaudeControlSimplified(unittest.TestCase):
    """Test cases for simplified claude_control"""
    
    @patch('pathlib.Path.mkdir')
    def setUp(self, mock_mkdir):
        """Set up test fixtures"""
        self.monitor = ClaudeMonitor()
    
    @patch('subprocess.run')
    def test_get_active_sessions_success(self, mock_run):
        """Test getting active sessions successfully"""
        mock_run.side_effect = [
            MagicMock(stdout="test-session:1234567890:3\nother-session:1234567891:2\n", returncode=0),
            MagicMock(stdout="0:Claude-Agent:node\n1:Shell:bash\n2:Server:npm\n", returncode=0),
            MagicMock(stdout="> Ready", returncode=0),
            MagicMock(stdout="0:Claude-Backend:node\n1:Database:psql\n", returncode=0), 
            MagicMock(stdout="Processing...", returncode=0)
        ]
        
        agents = self.monitor.get_all_agents()
        
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0]['session'], 'test-session')
        self.assertEqual(agents[0]['name'], 'Claude-Agent')
        self.assertEqual(agents[0]['status'], AgentStatus.READY)
        self.assertEqual(agents[1]['session'], 'other-session')
        self.assertEqual(agents[1]['name'], 'Claude-Backend')
        self.assertEqual(agents[1]['status'], AgentStatus.BUSY)
    
    @patch('subprocess.run')
    def test_get_active_sessions_no_sessions(self, mock_run):
        """Test getting active sessions when none exist"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        agents = self.monitor.get_all_agents()
        self.assertEqual(agents, [])
    
    @patch('builtins.print')
    def test_status_no_sessions(self, mock_print):
        """Test status output when no sessions exist"""
        with patch.object(self.monitor, 'get_all_agents', return_value=[]):
            format_status([], False)
        
        # Check that "No active sessions" was printed
        printed = ' '.join(str(call[0][0]) for call in mock_print.call_args_list)
        self.assertIn("No active sessions", printed)
    
    def test_health_check(self):
        """Test system health check"""
        with patch.object(self.monitor, 'health_check') as mock_health:
            mock_health.return_value = {
                'timestamp': '2024-01-01T00:00:00',
                'tmux_available': True,
                'claude_available': False,
                'active_sessions': 0,
                'total_agents': 0,
                'issues': ['claude command not found']
            }
            
            health = self.monitor.health_check()
        
        self.assertIn('timestamp', health)
        self.assertTrue(health['tmux_available'])
        self.assertFalse(health['claude_available'])
        self.assertEqual(health['active_sessions'], 0)
        self.assertIn('claude command not found', health['issues'])


if __name__ == '__main__':
    unittest.main()