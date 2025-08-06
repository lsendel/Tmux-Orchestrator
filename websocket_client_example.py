#!/usr/bin/env python3
"""
Example WebSocket Client for Testing
Demonstrates how to connect and interact with the monitoring system
"""

import asyncio
import websockets
import json
import argparse
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MonitoringClient:
    """Example monitoring client"""
    
    def __init__(self, url='ws://localhost:8765', token=None):
        self.url = url
        self.token = token
        self.running = True
    
    async def connect(self):
        """Connect to the WebSocket server"""
        logger.info(f"Connecting to {self.url}...")
        
        async with websockets.connect(self.url) as websocket:
            logger.info("Connected!")
            
            # Handle welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            logger.info(f"Server: {welcome_data}")
            
            # Authenticate if token provided
            if self.token:
                await self.authenticate(websocket)
            else:
                logger.warning("No token provided - running in unauthenticated mode")
            
            # Subscribe to events
            await self.subscribe(websocket)
            
            # Start listening for events
            await self.listen(websocket)
    
    async def authenticate(self, websocket):
        """Authenticate with the server"""
        logger.info("Authenticating...")
        
        auth_message = {
            "action": "auth",
            "token": self.token
        }
        
        await websocket.send(json.dumps(auth_message))
        
        response = await websocket.recv()
        response_data = json.loads(response)
        
        if response_data.get("type") == "auth.response":
            if response_data.get("success"):
                logger.info(f"Authentication successful! Permissions: {response_data.get('permissions')}")
            else:
                logger.error("Authentication failed!")
                raise Exception("Authentication failed")
        else:
            logger.error(f"Unexpected response: {response_data}")
    
    async def subscribe(self, websocket):
        """Subscribe to events"""
        logger.info("Subscribing to events...")
        
        # Subscribe to all event types for demo
        subscribe_message = {
            "action": "subscribe",
            "filters": {
                "types": [
                    "session.created",
                    "session.removed",
                    "window.created",
                    "window.removed",
                    "window.renamed",
                    "pane.output",
                    "pane.command",
                    "pane.error"
                ]
            }
        }
        
        await websocket.send(json.dumps(subscribe_message))
        
        response = await websocket.recv()
        response_data = json.loads(response)
        
        if response_data.get("type") == "subscription.confirmed":
            logger.info(f"Subscribed to: {response_data.get('subscriptions')}")
    
    async def listen(self, websocket):
        """Listen for events from the server"""
        logger.info("Listening for events...")
        
        try:
            while self.running:
                # Also send periodic pings to keep connection alive
                ping_task = asyncio.create_task(self.send_ping(websocket))
                
                try:
                    # Wait for messages with timeout
                    message = await asyncio.wait_for(websocket.recv(), timeout=30)
                    data = json.loads(message)
                    
                    # Handle different event types
                    await self.handle_event(data)
                    
                except asyncio.TimeoutError:
                    logger.debug("No events received in 30 seconds")
                    continue
                finally:
                    ping_task.cancel()
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed by server")
        except Exception as e:
            logger.error(f"Error in listener: {e}")
    
    async def handle_event(self, event):
        """Handle incoming events"""
        event_type = event.get("type")
        timestamp = event.get("timestamp", datetime.now().isoformat())
        
        if event_type == "error":
            logger.error(f"[{timestamp}] ERROR: {event.get('message')} ({event.get('code')})")
        elif event_type == "pong":
            logger.debug(f"[{timestamp}] Pong received")
        elif event_type in ["session.created", "session.removed"]:
            logger.info(f"[{timestamp}] {event_type}: {event.get('session', 'unknown')}")
        elif event_type in ["window.created", "window.removed", "window.renamed"]:
            logger.info(f"[{timestamp}] {event_type}: {event.get('session')}:{event.get('window')}")
            if event_type == "window.renamed":
                data = event.get('data', {})
                logger.info(f"  {data.get('old_name')} -> {data.get('new_name')}")
        elif event_type in ["pane.output", "pane.command", "pane.error"]:
            session = event.get('session')
            window = event.get('window')
            pane = event.get('pane')
            preview = event.get('data', {}).get('preview', '')
            logger.info(f"[{timestamp}] {event_type}: {session}:{window}.{pane}")
            if preview:
                logger.info(f"  Preview: {preview[:100]}")
        else:
            logger.info(f"[{timestamp}] {event_type}: {json.dumps(event, indent=2)}")
    
    async def send_ping(self, websocket):
        """Send periodic ping to keep connection alive"""
        await asyncio.sleep(25)
        try:
            await websocket.send(json.dumps({"action": "ping"}))
            logger.debug("Ping sent")
        except:
            pass
    
    async def request_snapshot(self, websocket, session=None, window=None):
        """Request a snapshot of tmux state"""
        logger.info("Requesting snapshot...")
        
        target = {}
        if session:
            target["session"] = session
        if window is not None:
            target["window"] = window
        
        snapshot_message = {
            "action": "snapshot",
            "target": target
        }
        
        await websocket.send(json.dumps(snapshot_message))
        logger.info(f"Snapshot requested for: {target if target else 'all sessions'}")


async def interactive_client(url, token):
    """Run an interactive client session"""
    client = MonitoringClient(url, token)
    
    try:
        await client.connect()
    except Exception as e:
        logger.error(f"Connection failed: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="WebSocket Monitoring Client Example"
    )
    
    parser.add_argument(
        '--url',
        default='ws://localhost:8765',
        help='WebSocket server URL (default: ws://localhost:8765)'
    )
    parser.add_argument(
        '--token',
        help='Authentication token'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check for token in environment if not provided
    if not args.token:
        import os
        args.token = os.environ.get('WEBSOCKET_TOKEN')
        if args.token:
            logger.info("Using token from WEBSOCKET_TOKEN environment variable")
    
    try:
        asyncio.run(interactive_client(args.url, args.token))
    except KeyboardInterrupt:
        logger.info("Client stopped by user")


if __name__ == "__main__":
    main()