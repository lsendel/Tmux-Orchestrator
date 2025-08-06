"""
Unit tests for WebSocket Server
"""

import asyncio
import json
import pytest
import websockets
from unittest.mock import Mock, AsyncMock, patch
from websocket_server import WebSocketServer, WebSocketClient
from auth_manager import AuthManager


@pytest.fixture
async def server():
    """Create a test server instance"""
    server = WebSocketServer(host='localhost', port=8766)
    auth_manager = AuthManager("test_tokens.json")
    server.set_auth_manager(auth_manager)
    return server


@pytest.fixture
async def running_server(server):
    """Start a server for testing"""
    task = asyncio.create_task(server.start())
    await asyncio.sleep(0.1)  # Give server time to start
    yield server
    server.running = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class TestWebSocketServer:
    """Test WebSocket Server functionality"""
    
    async def test_server_initialization(self, server):
        """Test server initializes correctly"""
        assert server.host == 'localhost'
        assert server.port == 8766
        assert server.clients == {}
        assert server.running == False
    
    async def test_client_id_generation(self, server):
        """Test unique client ID generation"""
        id1 = server.generate_client_id()
        id2 = server.generate_client_id()
        
        assert id1 != id2
        assert id1.startswith("client-")
        assert len(id1) > 8
    
    async def test_rate_limiting(self, server):
        """Test rate limiting functionality"""
        mock_connection = Mock()
        client = WebSocketClient(
            connection=mock_connection,
            client_id="test-client",
            rate_limit=5,
            token_bucket=5.0
        )
        
        # First 5 requests should pass (we have 5 tokens)
        for i in range(5):
            assert server.check_rate_limit(client) == True
        
        # 6th request should fail (no tokens left)
        assert server.check_rate_limit(client) == False
        
        # After waiting, should reset
        import time
        time.sleep(1.1)
        assert server.check_rate_limit(client) == True
    
    async def test_message_validation(self, server):
        """Test message processing and validation"""
        mock_connection = AsyncMock()
        client = WebSocketClient(
            connection=mock_connection,
            client_id="test-client"
        )
        
        # Test invalid JSON
        await server.process_message(client, "invalid json")
        mock_connection.send.assert_called()
        call_args = mock_connection.send.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"
        assert response["code"] == "INVALID_JSON"
    
    async def test_authentication_flow(self, server):
        """Test authentication process"""
        mock_connection = AsyncMock()
        client = WebSocketClient(
            connection=mock_connection,
            client_id="test-client"
        )
        
        # Generate test token
        token = server.auth_manager.generate_token(
            "test-client",
            {"read", "write"}
        )
        
        # Test authentication
        await server.handle_auth(client, {"token": token})
        
        assert client.authenticated == True
        assert "read" in client.permissions
        assert "write" in client.permissions
        
        # Verify response
        mock_connection.send.assert_called()
        call_args = mock_connection.send.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "auth.response"
        assert response["success"] == True
    
    async def test_subscription_management(self, server):
        """Test subscription handling"""
        mock_connection = AsyncMock()
        client = WebSocketClient(
            connection=mock_connection,
            client_id="test-client",
            authenticated=True
        )
        
        # Test subscription
        filters = {
            "types": ["agent.status", "pane.output"],
            "sessions": ["test-session"]
        }
        
        await server.handle_subscribe(client, {"filters": filters})
        
        assert "type:agent.status" in client.subscriptions
        assert "type:pane.output" in client.subscriptions
        assert "session:test-session" in client.subscriptions
        
        # Test unsubscribe
        await server.handle_unsubscribe(client, {
            "filters": {"types": ["agent.status"]}
        })
        
        assert "type:agent.status" not in client.subscriptions
        assert "type:pane.output" in client.subscriptions
    
    async def test_event_broadcasting(self, server):
        """Test event broadcasting to subscribed clients"""
        # Create multiple mock clients
        clients = []
        for i in range(3):
            mock_conn = AsyncMock()
            client = WebSocketClient(
                connection=mock_conn,
                client_id=f"client-{i}",
                authenticated=True
            )
            clients.append(client)
            server.clients[client.client_id] = client
        
        # Set up subscriptions
        clients[0].subscriptions.add("type:test.event")
        clients[1].subscriptions.add("session:test-session")
        clients[2].subscriptions.add("*")  # Wildcard
        
        # Broadcast event
        event = {
            "type": "test.event",
            "session": "test-session",
            "data": {"test": "data"}
        }
        
        await server.broadcast_event(event)
        
        # Check who received the event
        clients[0].connection.send.assert_called()  # Subscribed to type
        clients[1].connection.send.assert_called()  # Subscribed to session
        clients[2].connection.send.assert_called()  # Wildcard subscription
    
    async def test_snapshot_handling(self, server):
        """Test snapshot request handling"""
        mock_connection = AsyncMock()
        client = WebSocketClient(
            connection=mock_connection,
            client_id="test-client",
            authenticated=True
        )
        
        # Request snapshot
        target = {"session": "test-session", "window": 0}
        await server.handle_snapshot(client, {"target": target})
        
        # Check that snapshot request was queued
        assert not server.event_queue.empty()
        
        snapshot_request = await server.event_queue.get()
        assert snapshot_request["type"] == "snapshot.request"
        assert snapshot_request["target"] == target
        assert snapshot_request["client_id"] == "test-client"
    
    async def test_ping_pong(self, server):
        """Test ping/pong functionality"""
        mock_connection = AsyncMock()
        client = WebSocketClient(
            connection=mock_connection,
            client_id="test-client"
        )
        
        await server.handle_ping(client)
        
        mock_connection.send.assert_called()
        call_args = mock_connection.send.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "pong"


class TestWebSocketIntegration:
    """Integration tests for WebSocket server"""
    
    async def test_client_connection_lifecycle(self):
        """Test full client connection lifecycle"""
        server = WebSocketServer(host='localhost', port=8767)
        auth_manager = AuthManager("test_tokens.json")
        server.set_auth_manager(auth_manager)
        
        # Generate test token
        token = auth_manager.generate_token("test", {"read", "write"})
        
        # Start server
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)
        
        try:
            # Connect client
            async with websockets.connect('ws://localhost:8767') as ws:
                # Receive welcome message
                welcome = await ws.recv()
                welcome_data = json.loads(welcome)
                assert welcome_data["type"] == "connection.established"
                
                # Authenticate
                await ws.send(json.dumps({
                    "action": "auth",
                    "token": token
                }))
                
                auth_response = await ws.recv()
                auth_data = json.loads(auth_response)
                assert auth_data["type"] == "auth.response"
                assert auth_data["success"] == True
                
                # Subscribe to events
                await ws.send(json.dumps({
                    "action": "subscribe",
                    "filters": {
                        "types": ["test.event"]
                    }
                }))
                
                sub_response = await ws.recv()
                sub_data = json.loads(sub_response)
                assert sub_data["type"] == "subscription.confirmed"
                
        finally:
            server.running = False
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])