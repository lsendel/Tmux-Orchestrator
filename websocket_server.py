"""
WebSocket Server for Real-Time Tmux Monitoring
Provides real-time event streaming and monitoring capabilities
"""

import asyncio
import websockets
import json
import logging
import uuid
import time
from typing import Set, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client"""
    connection: websockets.WebSocketServerProtocol
    client_id: str
    authenticated: bool = False
    subscriptions: Set[str] = field(default_factory=set)
    rate_limit: int = 100  # messages per second
    last_message_time: float = field(default_factory=time.time)
    token_bucket: float = 100.0  # Current tokens in bucket
    permissions: Set[str] = field(default_factory=set)


class WebSocketServer:
    """Main WebSocket server for real-time monitoring"""
    
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, WebSocketClient] = {}
        self.event_queue = asyncio.Queue()
        self.running = False
        self.auth_manager = None  # Will be injected
        self.event_collector = None  # Will be injected
        
    def set_auth_manager(self, auth_manager):
        """Inject authentication manager"""
        self.auth_manager = auth_manager
        
    def set_event_collector(self, event_collector):
        """Inject event collector"""
        self.event_collector = event_collector
        
    async def start(self):
        """Start the WebSocket server"""
        self.running = True
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        
        # Start event collection if collector is available
        collector_task = None
        if self.event_collector:
            collector_task = asyncio.create_task(
                self.event_collector.start_collecting(self.event_queue)
            )
        
        # Start the WebSocket server
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port
        ):
            logger.info(f"WebSocket server listening on ws://{self.host}:{self.port}")
            
            # Run the event broadcaster
            await self.event_broadcaster()
            
            # Clean up collector task if it exists
            if collector_task:
                collector_task.cancel()
                try:
                    await collector_task
                except asyncio.CancelledError:
                    pass
    
    async def handle_client(self, websocket):
        """Handle individual client connections"""
        client_id = self.generate_client_id()
        client = WebSocketClient(websocket, client_id)
        self.clients[client_id] = client
        
        logger.info(f"New client connected: {client_id}")
        
        # Send welcome message
        await self.send_to_client(client, {
            "type": "connection.established",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            async for message in websocket:
                await self.process_message(client, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            del self.clients[client_id]
    
    async def process_message(self, client: WebSocketClient, message: str):
        """Process incoming client messages"""
        try:
            data = json.loads(message)
            
            # Rate limiting check
            if not self.check_rate_limit(client):
                await self.send_error(client, "Rate limit exceeded", "RATE_LIMIT")
                return
            
            action = data.get("action")
            
            if action == "auth":
                await self.handle_auth(client, data)
            elif action == "subscribe":
                await self.handle_subscribe(client, data)
            elif action == "unsubscribe":
                await self.handle_unsubscribe(client, data)
            elif action == "snapshot":
                await self.handle_snapshot(client, data)
            elif action == "ping":
                await self.handle_ping(client)
            else:
                await self.send_error(client, f"Unknown action: {action}", "UNKNOWN_ACTION")
                
        except json.JSONDecodeError:
            await self.send_error(client, "Invalid JSON", "INVALID_JSON")
        except Exception as e:
            logger.error(f"Error processing message from {client.client_id}: {e}")
            await self.send_error(client, "Internal server error", "INTERNAL_ERROR")
    
    async def handle_auth(self, client: WebSocketClient, data: Dict):
        """Handle authentication request"""
        token = data.get("token")
        
        if not token:
            await self.send_error(client, "Token required", "AUTH_REQUIRED")
            return
        
        if self.auth_manager:
            auth_token = self.auth_manager.validate_token(token)
            if auth_token:
                client.authenticated = True
                client.permissions = auth_token.permissions
                await self.send_to_client(client, {
                    "type": "auth.response",
                    "success": True,
                    "permissions": list(client.permissions),
                    "client_id": client.client_id
                })
                logger.info(f"Client {client.client_id} authenticated")
            else:
                await self.send_error(client, "Invalid token", "AUTH_FAILED")
        else:
            # No auth manager, allow all connections (development mode)
            client.authenticated = True
            client.permissions = {"read", "write"}
            await self.send_to_client(client, {
                "type": "auth.response",
                "success": True,
                "permissions": list(client.permissions),
                "client_id": client.client_id,
                "note": "Development mode - no authentication required"
            })
    
    async def handle_subscribe(self, client: WebSocketClient, data: Dict):
        """Handle subscription request"""
        if not client.authenticated:
            await self.send_error(client, "Authentication required", "AUTH_REQUIRED")
            return
        
        filters = data.get("filters", {})
        event_types = filters.get("types", [])
        sessions = filters.get("sessions", [])
        
        # Build subscription keys
        for event_type in event_types:
            client.subscriptions.add(f"type:{event_type}")
        
        for session in sessions:
            client.subscriptions.add(f"session:{session}")
        
        # Add a wildcard subscription if no specific filters
        if not event_types and not sessions:
            client.subscriptions.add("*")
        
        await self.send_to_client(client, {
            "type": "subscription.confirmed",
            "subscriptions": list(client.subscriptions)
        })
        
        logger.info(f"Client {client.client_id} subscribed to: {client.subscriptions}")
    
    async def handle_unsubscribe(self, client: WebSocketClient, data: Dict):
        """Handle unsubscribe request"""
        if not client.authenticated:
            await self.send_error(client, "Authentication required", "AUTH_REQUIRED")
            return
        
        filters = data.get("filters", {})
        if not filters:
            # Unsubscribe from all
            client.subscriptions.clear()
        else:
            # Remove specific subscriptions
            event_types = filters.get("types", [])
            sessions = filters.get("sessions", [])
            
            for event_type in event_types:
                client.subscriptions.discard(f"type:{event_type}")
            
            for session in sessions:
                client.subscriptions.discard(f"session:{session}")
        
        await self.send_to_client(client, {
            "type": "unsubscribe.confirmed",
            "subscriptions": list(client.subscriptions)
        })
    
    async def handle_snapshot(self, client: WebSocketClient, data: Dict):
        """Handle snapshot request"""
        if not client.authenticated:
            await self.send_error(client, "Authentication required", "AUTH_REQUIRED")
            return
        
        target = data.get("target", {})
        
        # Create a snapshot event request
        snapshot_event = {
            "type": "snapshot.request",
            "client_id": client.client_id,
            "target": target,
            "timestamp": datetime.now().isoformat()
        }
        
        # Queue the snapshot request for the event collector
        await self.event_queue.put(snapshot_event)
        
        await self.send_to_client(client, {
            "type": "snapshot.acknowledged",
            "target": target
        })
    
    async def handle_ping(self, client: WebSocketClient):
        """Handle ping request"""
        await self.send_to_client(client, {
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })
    
    async def event_broadcaster(self):
        """Broadcast events to subscribed clients"""
        while self.running:
            try:
                # Wait for events with timeout to allow checking running status
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                await self.broadcast_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in event broadcaster: {e}")
    
    async def broadcast_event(self, event: Dict):
        """Broadcast an event to all subscribed clients"""
        event_type = event.get("type", "")
        session = event.get("session", "")
        
        # Determine which clients should receive this event
        recipients = []
        for client_id, client in self.clients.items():
            if not client.authenticated:
                continue
            
            # Check if client is subscribed to this event
            if "*" in client.subscriptions:
                recipients.append(client)
            elif f"type:{event_type}" in client.subscriptions:
                recipients.append(client)
            elif session and f"session:{session}" in client.subscriptions:
                recipients.append(client)
        
        # Send to all recipients
        for client in recipients:
            try:
                await self.send_to_client(client, event)
            except Exception as e:
                logger.error(f"Failed to send event to client {client.client_id}: {e}")
    
    async def send_to_client(self, client: WebSocketClient, data: Dict):
        """Send data to a specific client"""
        try:
            message = json.dumps(data)
            await client.connection.send(message)
        except Exception as e:
            logger.error(f"Failed to send to client {client.client_id}: {e}")
    
    async def send_error(self, client: WebSocketClient, message: str, code: str):
        """Send error message to client"""
        await self.send_to_client(client, {
            "type": "error",
            "message": message,
            "code": code,
            "timestamp": datetime.now().isoformat()
        })
    
    def check_rate_limit(self, client: WebSocketClient) -> bool:
        """Check if client is within rate limit using token bucket algorithm"""
        current_time = time.time()
        elapsed = current_time - client.last_message_time
        
        # Refill tokens based on elapsed time
        # Rate limit defines tokens per second
        tokens_to_add = elapsed * client.rate_limit
        client.token_bucket = min(
            client.rate_limit,  # Max bucket size
            client.token_bucket + tokens_to_add
        )
        client.last_message_time = current_time
        
        # Check if we have tokens available
        if client.token_bucket >= 1:
            client.token_bucket -= 1
            return True
        return False
    
    def generate_client_id(self) -> str:
        """Generate unique client ID"""
        return f"client-{uuid.uuid4().hex[:8]}"
    
    async def stop(self):
        """Stop the WebSocket server"""
        self.running = False
        logger.info("Stopping WebSocket server")
        
        # Close all client connections
        for client in self.clients.values():
            await client.connection.close()
        
        self.clients.clear()


async def main():
    """Main entry point for testing"""
    server = WebSocketServer()
    
    try:
        await server.start()
    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())