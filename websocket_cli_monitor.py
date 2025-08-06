#!/usr/bin/env python3
"""
WebSocket CLI Monitor with Rich UI
Real-time display of tmux events with color-coded terminal interface
"""

import asyncio
import websockets
import json
import argparse
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.columns import Columns
from rich import box
from rich.style import Style

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class EventMonitor:
    """Real-time event monitor with Rich UI"""
    
    # Event type color mapping
    EVENT_COLORS = {
        "session.created": "bold green",
        "session.removed": "bold red",
        "session.attached": "cyan",
        "session.detached": "dark_cyan",
        "window.created": "green",
        "window.removed": "red",
        "window.renamed": "yellow",
        "window.activated": "bright_cyan",
        "pane.output": "white",
        "pane.command": "bright_blue",
        "pane.error": "bright_red",
        "pane.warning": "bright_yellow",
        "snapshot.data": "magenta",
        "error": "bold red on dark_red",
        "auth.response": "bold green",
        "subscription.confirmed": "green",
        "connection.established": "bold cyan",
        "pong": "dim white"
    }
    
    # Event type icons
    EVENT_ICONS = {
        "session.created": "➕",
        "session.removed": "➖",
        "session.attached": "🔗",
        "session.detached": "🔓",
        "window.created": "🪟",
        "window.removed": "❌",
        "window.renamed": "✏️",
        "window.activated": "👁️",
        "pane.output": "📝",
        "pane.command": "⚡",
        "pane.error": "🔴",
        "pane.warning": "⚠️",
        "snapshot.data": "📸",
        "error": "❗",
        "auth.response": "🔐",
        "subscription.confirmed": "✅",
        "connection.established": "🌐",
        "pong": "🏓"
    }
    
    def __init__(self, url: str, token: Optional[str] = None, max_events: int = 100):
        self.url = url
        self.token = token
        self.max_events = max_events
        self.console = Console()
        self.events = deque(maxlen=max_events)
        self.stats = {
            "total_events": 0,
            "events_by_type": {},
            "connected": False,
            "authenticated": False,
            "server_info": {}
        }
        self.running = True
        self.websocket = None
        self.last_error = None
        
    async def connect(self):
        """Connect to WebSocket server and start monitoring"""
        try:
            self.console.print("[cyan]Connecting to WebSocket server...[/cyan]")
            
            async with websockets.connect(self.url) as websocket:
                self.websocket = websocket
                self.stats["connected"] = True
                
                # Handle welcome message
                welcome = await websocket.recv()
                welcome_data = json.loads(welcome)
                self.add_event(welcome_data)
                self.stats["server_info"] = welcome_data
                
                # Authenticate if token provided
                if self.token:
                    await self.authenticate(websocket)
                
                # Subscribe to all events
                await self.subscribe(websocket)
                
                # Start monitoring
                await self.monitor(websocket)
                
        except websockets.exceptions.ConnectionClosed as e:
            self.console.print(f"[red]Connection closed: {e}[/red]")
            self.stats["connected"] = False
        except Exception as e:
            self.console.print(f"[red]Connection error: {e}[/red]")
            self.last_error = str(e)
            self.stats["connected"] = False
    
    async def authenticate(self, websocket):
        """Authenticate with the server"""
        auth_msg = {
            "action": "auth",
            "token": self.token
        }
        
        await websocket.send(json.dumps(auth_msg))
        response = await websocket.recv()
        response_data = json.loads(response)
        
        self.add_event(response_data)
        
        if response_data.get("type") == "auth.response" and response_data.get("success"):
            self.stats["authenticated"] = True
            self.console.print("[green]✅ Authentication successful[/green]")
        else:
            self.console.print("[red]❌ Authentication failed[/red]")
            raise Exception("Authentication failed")
    
    async def subscribe(self, websocket):
        """Subscribe to events"""
        subscribe_msg = {
            "action": "subscribe",
            "filters": {}  # Subscribe to all events
        }
        
        await websocket.send(json.dumps(subscribe_msg))
        response = await websocket.recv()
        response_data = json.loads(response)
        
        self.add_event(response_data)
        
        if response_data.get("type") == "subscription.confirmed":
            self.console.print("[green]✅ Subscribed to events[/green]")
    
    async def monitor(self, websocket):
        """Monitor events with Rich Live display"""
        with Live(self.create_display(), refresh_per_second=2, console=self.console) as live:
            # Send initial ping
            ping_task = asyncio.create_task(self.send_periodic_ping(websocket))
            
            try:
                while self.running:
                    try:
                        # Wait for messages with timeout
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        # Add event to history
                        self.add_event(data)
                        
                        # Update display
                        live.update(self.create_display())
                        
                    except asyncio.TimeoutError:
                        # Update display even without new events
                        live.update(self.create_display())
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        self.stats["connected"] = False
                        self.console.print("[red]Connection lost[/red]")
                        break
                    
            finally:
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass
    
    async def send_periodic_ping(self, websocket):
        """Send periodic ping to keep connection alive"""
        while self.running:
            await asyncio.sleep(25)
            try:
                await websocket.send(json.dumps({"action": "ping"}))
            except:
                break
    
    def add_event(self, event: Dict):
        """Add event to history and update stats"""
        # Add timestamp if not present
        if "timestamp" not in event:
            event["timestamp"] = datetime.now().isoformat()
        
        # Add to events list
        self.events.append(event)
        
        # Update statistics
        self.stats["total_events"] += 1
        event_type = event.get("type", "unknown")
        self.stats["events_by_type"][event_type] = self.stats["events_by_type"].get(event_type, 0) + 1
    
    def create_display(self) -> Layout:
        """Create the Rich display layout"""
        layout = Layout()
        
        # Create main sections
        layout.split_column(
            Layout(self.create_header(), size=3),
            Layout(name="body"),
            Layout(self.create_stats(), size=6)
        )
        
        # Split body into events table
        layout["body"].update(self.create_events_table())
        
        return layout
    
    def create_header(self) -> Panel:
        """Create header panel"""
        status = "🟢 Connected" if self.stats["connected"] else "🔴 Disconnected"
        auth = "🔐 Authenticated" if self.stats["authenticated"] else "🔓 Not Authenticated"
        
        header_text = Text()
        header_text.append("WebSocket Monitor", style="bold cyan")
        header_text.append(" | ", style="dim")
        header_text.append(status)
        header_text.append(" | ", style="dim")
        header_text.append(auth)
        header_text.append(" | ", style="dim")
        header_text.append(f"Events: {self.stats['total_events']}", style="yellow")
        
        return Panel(header_text, box=box.DOUBLE)
    
    def create_events_table(self) -> Panel:
        """Create events table"""
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=box.ROUNDED,
            expand=True,
            show_lines=False
        )
        
        # Add columns
        table.add_column("Time", style="dim", width=12)
        table.add_column("Type", width=20)
        table.add_column("Target", width=20)
        table.add_column("Details", ratio=1)
        
        # Add recent events (most recent first)
        for event in reversed(self.events):
            # Parse timestamp
            timestamp = event.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M:%S.%f")[:-3]
                except:
                    time_str = timestamp[:12]
            else:
                time_str = "-"
            
            # Get event type and style
            event_type = event.get("type", "unknown")
            style = self.EVENT_COLORS.get(event_type, "white")
            icon = self.EVENT_ICONS.get(event_type, "•")
            
            # Build target info
            target_parts = []
            if event.get("session"):
                target_parts.append(f"S:{event['session']}")
            if event.get("window") is not None:
                target_parts.append(f"W:{event['window']}")
            if event.get("pane") is not None:
                target_parts.append(f"P:{event['pane']}")
            target = " ".join(target_parts) if target_parts else "-"
            
            # Build details
            details = self.format_event_details(event)
            
            # Add row with color
            type_text = Text(f"{icon} {event_type}", style=style)
            table.add_row(time_str, type_text, target, details)
        
        return Panel(table, title="📊 Event Stream", border_style="cyan")
    
    def format_event_details(self, event: Dict) -> str:
        """Format event details for display"""
        data = event.get("data", {})
        event_type = event.get("type", "")
        
        # Special formatting for different event types
        if event_type == "window.renamed":
            return f"{data.get('old_name', '?')} → {data.get('new_name', '?')}"
        elif event_type in ["pane.output", "pane.command", "pane.error"]:
            preview = data.get("preview", "")
            if preview:
                # Truncate and clean preview
                preview = preview.replace("\n", " ").strip()
                if len(preview) > 50:
                    preview = preview[:47] + "..."
                return preview
            return data.get("activity", "-")
        elif event_type == "auth.response":
            if event.get("success"):
                perms = event.get("permissions", [])
                return f"Permissions: {', '.join(perms)}"
            return "Failed"
        elif event_type == "subscription.confirmed":
            subs = event.get("subscriptions", [])
            return f"{len(subs)} subscriptions"
        elif event_type == "error":
            return f"{event.get('message', 'Unknown error')} ({event.get('code', 'UNKNOWN')})"
        elif event_type == "snapshot.data":
            if "content" in data:
                lines = data["content"].count("\n") if data["content"] else 0
                return f"{lines} lines"
            elif "full_state" in data:
                sessions = len(data["full_state"])
                return f"{sessions} sessions"
            return "Data received"
        else:
            # Generic data display
            if data:
                # Take first few key-value pairs
                items = []
                for k, v in list(data.items())[:2]:
                    if isinstance(v, str) and len(v) > 20:
                        v = v[:17] + "..."
                    items.append(f"{k}={v}")
                return ", ".join(items) if items else "-"
            return "-"
    
    def create_stats(self) -> Panel:
        """Create statistics panel"""
        # Create stats grid
        stats_text = Text()
        
        # Sort event types by count
        sorted_types = sorted(
            self.stats["events_by_type"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Display top event types
        stats_text.append("Event Distribution:\n", style="bold yellow")
        for event_type, count in sorted_types[:5]:
            icon = self.EVENT_ICONS.get(event_type, "•")
            color = self.EVENT_COLORS.get(event_type, "white")
            bar_length = min(20, int(count / max(1, self.stats["total_events"]) * 20))
            bar = "█" * bar_length + "░" * (20 - bar_length)
            stats_text.append(f"{icon} {event_type:20} ", style=color)
            stats_text.append(f"{bar} {count:4}\n", style="dim")
        
        return Panel(stats_text, title="📈 Statistics", border_style="yellow")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="WebSocket CLI Monitor with Rich UI"
    )
    
    parser.add_argument(
        "--url",
        default="ws://localhost:8765",
        help="WebSocket server URL"
    )
    parser.add_argument(
        "--token",
        help="Authentication token"
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=100,
        help="Maximum events to keep in memory"
    )
    
    args = parser.parse_args()
    
    # Check for token in environment if not provided
    if not args.token:
        import os
        args.token = os.environ.get("WEBSOCKET_TOKEN")
    
    # Create and run monitor
    monitor = EventMonitor(args.url, args.token, args.max_events)
    
    # Set up signal handlers
    def signal_handler(sig, frame):
        monitor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await monitor.connect()
    except KeyboardInterrupt:
        monitor.console.print("\n[yellow]Monitoring stopped by user[/yellow]")
    except Exception as e:
        monitor.console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())