#!/usr/bin/env python3
"""
WebSocket Monitoring System - Main Entry Point
Integrates all components for real-time tmux monitoring
"""

import asyncio
import signal
import logging
import argparse
import sys
from pathlib import Path

from websocket_server import WebSocketServer
from event_collector import TmuxEventCollector
from auth_manager import AuthManager, TokenGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketMonitor:
    """Main monitoring application"""
    
    def __init__(self, host='localhost', port=8765, poll_interval=0.5):
        self.host = host
        self.port = port
        self.poll_interval = poll_interval
        
        # Initialize components
        self.server = WebSocketServer(host, port)
        self.collector = TmuxEventCollector(poll_interval)
        self.auth_manager = AuthManager()
        
        # Wire components together
        self.server.set_auth_manager(self.auth_manager)
        self.server.set_event_collector(self.collector)
        
        # Shutdown flag
        self.shutdown_event = asyncio.Event()
    
    async def start(self):
        """Start the monitoring system"""
        logger.info("Starting WebSocket Monitoring System")
        logger.info(f"Server: ws://{self.host}:{self.port}")
        logger.info(f"Poll interval: {self.poll_interval}s")
        
        # List available tokens
        tokens = self.auth_manager.list_tokens()
        if tokens:
            logger.info(f"Active tokens: {len(tokens)}")
            for token_preview in tokens:
                logger.info(f"  - {token_preview}: {tokens[token_preview]['client_name']}")
        else:
            logger.warning("No authentication tokens found!")
            logger.warning("Run with --generate-token to create one")
        
        # Set up signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)
        
        try:
            # Start the server
            await self.server.start()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            await self.shutdown()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.shutdown())
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down WebSocket Monitoring System")
        
        # Stop components
        await self.server.stop()
        await self.collector.stop()
        
        # Set shutdown event
        self.shutdown_event.set()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="WebSocket Real-Time Monitoring for Tmux Orchestrator"
    )
    
    # Server options
    parser.add_argument(
        '--host',
        default='localhost',
        help='Host to bind to (default: localhost)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8765,
        help='Port to bind to (default: 8765)'
    )
    parser.add_argument(
        '--poll-interval',
        type=float,
        default=0.5,
        help='Tmux polling interval in seconds (default: 0.5)'
    )
    
    # Token management
    parser.add_argument(
        '--generate-token',
        action='store_true',
        help='Generate a new authentication token'
    )
    parser.add_argument(
        '--list-tokens',
        action='store_true',
        help='List all authentication tokens'
    )
    parser.add_argument(
        '--cleanup-tokens',
        action='store_true',
        help='Remove expired tokens'
    )
    
    # Logging
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle token management commands
    auth_manager = AuthManager()
    
    if args.generate_token:
        generator = TokenGenerator(auth_manager)
        generator.interactive_generate()
        return
    
    if args.list_tokens:
        tokens = auth_manager.list_tokens()
        if tokens:
            print("\n=== Active Tokens ===\n")
            for token_preview, info in tokens.items():
                print(f"Token: {token_preview}")
                print(f"  Client: {info['client_name']}")
                print(f"  Permissions: {', '.join(info['permissions'])}")
                print(f"  Created: {info['created_at']}")
                if info.get('expires_at'):
                    print(f"  Expires: {info['expires_at']}")
                if info.get('last_used'):
                    print(f"  Last used: {info['last_used']}")
                if info.get('description'):
                    print(f"  Description: {info['description']}")
                print()
        else:
            print("No tokens found")
            print("Run with --generate-token to create one")
        return
    
    if args.cleanup_tokens:
        auth_manager.cleanup_expired_tokens()
        print("Expired tokens cleaned up")
        return
    
    # Start the monitoring system
    monitor = WebSocketMonitor(
        host=args.host,
        port=args.port,
        poll_interval=args.poll_interval
    )
    
    try:
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()