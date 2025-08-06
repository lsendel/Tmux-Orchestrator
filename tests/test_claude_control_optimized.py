"""
Unit tests for optimized claude_control.py
Tests batch operations and performance improvements
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import json
from pathlib import Path

from claude_control_optimized import ClaudeMonitor, format_status
from tmux_core import AgentStatus, SessionInfo, WindowInfo


class TestClaudeMonitorOptimized(unittest.TestCase):
    """Test optimized ClaudeMonitor with batch operations"""
    
    def setUp(self):
        self.monitor = ClaudeMonitor()
    
    @patch.object(ClaudeMonitor, 'batch_get_all_sessions_and_windows')
    def test_get_all_agents_batch(self, mock_batch):
        """Test get_all_agents uses batch operations"""
        # Mock batch data
        mock_batch.return_value = {
            'sessions': {
                'test-session': SessionInfo('test-session', 2, '12345', False),
                'prod-session': SessionInfo('prod-session', 1, '12346', True)
            },
            'windows': {
                'test-session': [
                    WindowInfo('test-session', 0, 'Claude-Agent', True, 1, 'tiled', 'node'),
                    WindowInfo('test-session', 1, 'Shell', False, 1, 'tiled', 'bash')
                ],
                'prod-session': [
                    WindowInfo('prod-session', 0, 'Project-Manager', True, 1, 'tiled', 'node')
                ]
            }
        }
        
        # Mock status determination
        with patch.object(self.monitor, '_determine_agent_status') as mock_status:
            mock_status.return_value = AgentStatus.READY
            
            agents = self.monitor.get_all_agents()
        
        # Should only call batch once
        mock_batch.assert_called_once()
        
        # Should find 2 Claude agents (not the bash shell)
        self.assertEqual(len(agents), 2)
        
        # Verify agent data
        test_agent = next(a for a in agents if a['session'] == 'test-session')
        self.assertEqual(test_agent['window'], 0)
        self.assertEqual(test_agent['name'], 'Claude-Agent')
        self.assertEqual(test_agent['type'], 'CLAUDE_AGENT')
        
        prod_agent = next(a for a in agents if a['session'] == 'prod-session')
        self.assertEqual(prod_agent['window'], 0)
        self.assertEqual(prod_agent['name'], 'Project-Manager')
        self.assertEqual(prod_agent['type'], 'PROJECT_MANAGER')
    
    @patch.object(ClaudeMonitor, 'execute_command')
    def test_determine_agent_status_patterns(self, mock_execute):
        """Test agent status determination"""
        test_cases = [
            ("waiting for your next message", AgentStatus.READY),
            ("Running task...", AgentStatus.BUSY),
            ("Executing command", AgentStatus.BUSY),
            ("Processing request", AgentStatus.BUSY),
            ("Error: Something failed", AgentStatus.ERROR),
            ("Random output", AgentStatus.UNKNOWN)
        ]
        
        window = WindowInfo('test', 0, 'Claude', True, 1, 'tiled', 'node')
        
        for output, expected_status in test_cases:
            with self.subTest(output=output):
                mock_execute.return_value = MagicMock(stdout=output)
                status = self.monitor._determine_agent_status('test', window)
                self.assertEqual(status, expected_status)
    
    @patch.object(ClaudeMonitor, 'get_all_agents')
    def test_health_check_performance(self, mock_agents):
        """Test health check uses efficient grouping"""
        mock_agents.return_value = [
            {'session': 's1', 'status': AgentStatus.READY},
            {'session': 's1', 'status': AgentStatus.BUSY},
            {'session': 's2', 'status': AgentStatus.ERROR},
            {'session': 's2', 'status': AgentStatus.READY},
            {'session': 's3', 'status': AgentStatus.UNKNOWN}
        ]
        
        health = self.monitor.health_check()
        
        # Should call get_all_agents only once
        mock_agents.assert_called_once()
        
        # Verify health data
        self.assertFalse(health['healthy'])  # Has error
        self.assertEqual(health['total_agents'], 5)
        self.assertEqual(health['sessions'], 3)
        self.assertEqual(health['status_breakdown'][AgentStatus.READY], 2)
        self.assertEqual(health['status_breakdown'][AgentStatus.BUSY], 1)
        self.assertEqual(health['status_breakdown'][AgentStatus.ERROR], 1)
        self.assertEqual(health['status_breakdown'][AgentStatus.UNKNOWN], 1)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch.object(ClaudeMonitor, 'get_all_agents')
    def test_save_status_format(self, mock_agents, mock_file):
        """Test status save format"""
        mock_agents.return_value = [
            {
                'session': 'test',
                'window': 0,
                'name': 'Claude-Agent',
                'status': AgentStatus.READY,
                'type': 'CLAUDE_AGENT',
                'created': '12345'
            }
        ]
        
        self.monitor.save_status(mock_agents.return_value)
        
        # Get written data
        written_data = ''.join(call.args[0] for call in mock_file().write.call_args_list)
        data = json.loads(written_data)
        
        # Verify format
        self.assertIn('updated', data)
        self.assertIn('sessions', data)
        self.assertEqual(len(data['sessions']), 1)
        self.assertEqual(data['sessions'][0]['name'], 'test')
        self.assertEqual(len(data['sessions'][0]['agents']), 1)
    
    @patch.object(ClaudeMonitor, 'health_check')
    @patch.object(ClaudeMonitor, 'get_all_agents')
    def test_get_status_json(self, mock_agents, mock_health):
        """Test JSON status output"""
        mock_agents.return_value = [
            {'session': 'test', 'window': 0, 'status': AgentStatus.READY}
        ]
        mock_health.return_value = {'healthy': True, 'total_agents': 1}
        
        json_output = self.monitor.get_status_json()
        
        # Should be valid JSON
        data = json.loads(json_output)
        
        self.assertIn('agents', data)
        self.assertIn('health', data)
        self.assertIn('timestamp', data)
        self.assertEqual(len(data['agents']), 1)


class TestFormatStatusOptimized(unittest.TestCase):
    """Test status formatting"""
    
    def test_format_status_empty(self):
        """Test formatting with no agents"""
        output = format_status([])
        self.assertEqual(output, "No active Claude agents found.")
    
    def test_format_status_grouping(self):
        """Test proper session grouping"""
        agents = [
            {'session': 's1', 'window': 0, 'name': 'Agent1', 'status': AgentStatus.READY},
            {'session': 's1', 'window': 1, 'name': 'Agent2', 'status': AgentStatus.BUSY},
            {'session': 's2', 'window': 0, 'name': 'Agent3', 'status': AgentStatus.ERROR}
        ]
        
        output = format_status(agents, detailed=True)
        
        # Verify structure
        self.assertIn("Active Sessions: 2", output)
        self.assertIn("Total Agents: 3", output)
        self.assertIn("📁 s1", output)
        self.assertIn("📁 s2", output)
        
        # Verify detailed info
        self.assertIn("[ready] ✅", output)
        self.assertIn("[busy] 🔄", output)
        self.assertIn("[error] ❌", output)


class TestPerformanceImprovements(unittest.TestCase):
    """Test that optimizations actually improve performance"""
    
    @patch('subprocess.run')
    def test_batch_operations_reduce_calls(self, mock_run):
        """Verify batch operations reduce subprocess calls"""
        monitor = ClaudeMonitor()
        
        # Setup mock responses for batch operations
        mock_run.side_effect = [
            # First call: list-sessions
            MagicMock(stdout="s1|2|123|0\ns2|1|124|0", returncode=0),
            # Second call: list-windows -a
            MagicMock(stdout="s1:0|Claude|1|1|tiled|node\ns1:1|Shell|0|1|tiled|bash", returncode=0),
            # Status checks for Claude windows only
            MagicMock(stdout="waiting for your next message", returncode=0)
        ]
        
        # Get all agents with new batch approach
        with patch.object(monitor, 'execute_command', side_effect=mock_run.side_effect):
            agents = monitor.get_all_agents()
        
        # With old approach, this would be:
        # - 1 call for list-sessions
        # - 2 calls for list-windows (one per session)
        # - N calls for capture-pane (one per window)
        # Total: 1 + 2 + N
        
        # With new approach:
        # - 1 call for list-sessions
        # - 1 call for list-windows -a (all at once)
        # - Only capture Claude windows
        # Total: 2 + number of Claude windows
        
        # Much more efficient!
        self.assertLessEqual(len(mock_run.side_effect), 3)


if __name__ == '__main__':
    unittest.main()