# Technical Specification: WebSocket Real-Time Monitoring

## Architecture Details

### System Design

The WebSocket monitoring system implements a layered, event-driven architecture that integrates with the existing Tmux Orchestrator while maintaining loose coupling:

```
┌─────────────────────────────────────────────────────────┐
│                   Client Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Web UI   │  │ CLI Tool │  │ Custom   │             │
│  │ Dashboard│  │ Monitor  │  │ Client   │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
└───────┼─────────────┼─────────────┼────────────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │ WebSocket Protocol
┌─────────────────────▼────────────────────────────────────┐
│              WebSocket Server Layer                       │
│  ┌────────────────────────────────────────────────┐     │
│  │         AsyncIO WebSocket Server               │     │
│  ├────────────────────────────────────────────────┤     │
│  │ Connection │ Auth │ Subscription │ Rate       │     │
│  │ Manager    │ Handler │ Manager    │ Limiter   │     │
│  └────────────────────────────────────────────────┘     │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│              Event Processing Layer                       │
│  ┌────────────────────────────────────────────────┐     │
│  │           Event Collector & Router              │     │
│  ├────────────────────────────────────────────────┤     │
│  │ Event Queue │ Event Filter │ Event Aggregator  │     │
│  └────────────────────────────────────────────────┘     │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│            Integration Layer (Existing)                   │
│  ┌────────────────────────────────────────────────┐     │
│  │              tmux_core.py                      │     │
│  │         (BatchOperations, TmuxCommand)         │     │
│  └────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. WebSocket Server (`websocket_server.py`)

```python
import asyncio
import websockets
import json
from typing import Set, Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client"""
    connection: websockets.WebSocketServerProtocol
    client_id: str
    authenticated: bool = False
    subscriptions: Set[str] = None
    rate_limit: int = 100  # messages per second
    
    def __post_init__(self):
        if self.subscriptions is None:
            self.subscriptions = set()

class WebSocketServer:
    """Main WebSocket server for real-time monitoring"""
    
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, WebSocketClient] = {}
        self.event_queue = asyncio.Queue()
        self.running = False
        
    async def start(self):
        """Start the WebSocket server"""
        self.running = True
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port
        ):
            await asyncio.gather(
                self.event_broadcaster(),
                self.event_collector()
            )
    
    async def handle_client(self, websocket, path):
        """Handle individual client connections"""
        client_id = self.generate_client_id()
        client = WebSocketClient(websocket, client_id)
        self.clients[client_id] = client
        
        try:
            async for message in websocket:
                await self.process_message(client, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            del self.clients[client_id]
    
    async def event_broadcaster(self):
        """Broadcast events to subscribed clients"""
        while self.running:
            event = await self.event_queue.get()
            await self.broadcast_event(event)
```

#### 2. Event Collector (`event_collector.py`)

```python
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from tmux_core import BatchOperations

@dataclass
class TmuxEvent:
    """Represents a tmux event"""
    type: str
    timestamp: datetime
    session: Optional[str] = None
    window: Optional[int] = None
    data: Dict[str, Any] = None

class TmuxEventCollector:
    """Collects events from tmux sessions"""
    
    def __init__(self, poll_interval=0.5):
        self.poll_interval = poll_interval
        self.batch_ops = BatchOperations()
        self.previous_state = {}
        self.running = False
        
    async def start_collecting(self, event_queue: asyncio.Queue):
        """Start collecting tmux events"""
        self.running = True
        while self.running:
            events = await self.detect_changes()
            for event in events:
                await event_queue.put(event)
            await asyncio.sleep(self.poll_interval)
    
    async def detect_changes(self) -> List[TmuxEvent]:
        """Detect changes in tmux state"""
        events = []
        current_state = await self.get_current_state()
        
        # Detect new sessions
        for session in current_state:
            if session not in self.previous_state:
                events.append(TmuxEvent(
                    type="session.created",
                    timestamp=datetime.now(),
                    data={"session": session}
                ))
        
        # Detect removed sessions
        for session in self.previous_state:
            if session not in current_state:
                events.append(TmuxEvent(
                    type="session.removed",
                    timestamp=datetime.now(),
                    data={"session": session}
                ))
        
        # Detect window changes
        for session, windows in current_state.items():
            if session in self.previous_state:
                events.extend(
                    self.detect_window_changes(
                        session,
                        self.previous_state[session],
                        windows
                    )
                )
        
        self.previous_state = current_state
        return events
```

#### 3. Authentication Manager (`auth_manager.py`)

```python
import secrets
import hashlib
from typing import Optional
from dataclasses import dataclass

@dataclass
class AuthToken:
    """Authentication token for WebSocket connections"""
    token: str
    client_name: str
    permissions: Set[str]
    expires_at: Optional[datetime] = None

class AuthManager:
    """Manages authentication for WebSocket connections"""
    
    def __init__(self):
        self.tokens: Dict[str, AuthToken] = {}
        self.load_tokens()
    
    def generate_token(self, client_name: str, 
                       permissions: Set[str]) -> str:
        """Generate a new authentication token"""
        token_value = secrets.token_urlsafe(32)
        token = AuthToken(
            token=token_value,
            client_name=client_name,
            permissions=permissions
        )
        self.tokens[token_value] = token
        self.save_tokens()
        return token_value
    
    def validate_token(self, token: str) -> Optional[AuthToken]:
        """Validate an authentication token"""
        if token in self.tokens:
            auth_token = self.tokens[token]
            if auth_token.expires_at:
                if datetime.now() > auth_token.expires_at:
                    del self.tokens[token]
                    return None
            return auth_token
        return None
    
    def has_permission(self, token: str, permission: str) -> bool:
        """Check if a token has a specific permission"""
        auth_token = self.validate_token(token)
        if auth_token:
            return permission in auth_token.permissions
        return False
```

### Data Flow

#### Event Generation Flow
1. **Tmux State Change** → TmuxEventCollector detects via polling
2. **Event Creation** → Create TmuxEvent with type, timestamp, and data
3. **Event Queue** → Add event to AsyncIO queue
4. **Event Broadcasting** → Server broadcasts to subscribed clients
5. **Client Filtering** → Clients receive only subscribed events

#### Client Connection Flow
1. **WebSocket Connect** → Client establishes WebSocket connection
2. **Authentication** → Client sends auth token
3. **Validation** → Server validates token and permissions
4. **Subscription** → Client subscribes to event types/sessions
5. **Event Stream** → Client receives filtered event stream

### Message Protocol

#### Client to Server Messages

```python
# Authentication
{
    "action": "auth",
    "token": "your-secure-token-here"
}

# Subscribe to events
{
    "action": "subscribe",
    "filters": {
        "types": ["agent.status", "pane.output"],
        "sessions": ["ai-chat", "backend"],
        "windows": [0, 1, 2]
    }
}

# Request snapshot
{
    "action": "snapshot",
    "target": {
        "session": "ai-chat",
        "window": 0
    }
}

# Send command (requires permission)
{
    "action": "command",
    "target": {
        "session": "ai-chat",
        "window": 0
    },
    "command": "status"
}
```

#### Server to Client Messages

```python
# Authentication response
{
    "type": "auth.response",
    "success": true,
    "permissions": ["read", "write"],
    "client_id": "client-123"
}

# Event notification
{
    "type": "agent.status",
    "timestamp": "2025-08-06T12:00:00.123Z",
    "session": "ai-chat",
    "window": 0,
    "data": {
        "status": "busy",
        "previous": "ready"
    }
}

# Error message
{
    "type": "error",
    "message": "Invalid subscription filter",
    "code": "INVALID_FILTER"
}
```

### Performance Optimization

#### 1. Event Batching
```python
async def batch_events(self, events: List[TmuxEvent], 
                       max_batch_size=10,
                       max_wait_ms=50):
    """Batch multiple events for efficient transmission"""
    batch = []
    start_time = asyncio.get_event_loop().time()
    
    for event in events:
        batch.append(event)
        if len(batch) >= max_batch_size:
            yield batch
            batch = []
        elif (asyncio.get_event_loop().time() - start_time) * 1000 > max_wait_ms:
            if batch:
                yield batch
                batch = []
            start_time = asyncio.get_event_loop().time()
    
    if batch:
        yield batch
```

#### 2. Efficient Change Detection
```python
def calculate_diff_hash(self, data: Dict) -> str:
    """Calculate hash for efficient change detection"""
    return hashlib.md5(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()
```

#### 3. Connection Pooling
```python
class ConnectionPool:
    """Manage WebSocket connections efficiently"""
    def __init__(self, max_connections=100):
        self.max_connections = max_connections
        self.connections = {}
        self.semaphore = asyncio.Semaphore(max_connections)
```

### Security Implementation

#### 1. Rate Limiting
```python
class RateLimiter:
    """Token bucket rate limiter"""
    def __init__(self, rate=100, per=1.0):
        self.rate = rate
        self.per = per
        self.tokens = rate
        self.updated_at = time.time()
    
    def allow_request(self) -> bool:
        now = time.time()
        elapsed = now - self.updated_at
        self.tokens = min(
            self.rate,
            self.tokens + elapsed * (self.rate / self.per)
        )
        self.updated_at = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
```

#### 2. Input Validation
```python
def validate_message(message: Dict) -> bool:
    """Validate incoming WebSocket messages"""
    required_fields = {"action"}
    allowed_actions = {"auth", "subscribe", "unsubscribe", "snapshot"}
    
    if not all(field in message for field in required_fields):
        return False
    
    if message["action"] not in allowed_actions:
        return False
    
    # Additional validation based on action
    return True
```

### Testing Strategy

#### Unit Tests
```python
# test_websocket_server.py
async def test_client_connection():
    """Test WebSocket client connection"""
    server = WebSocketServer()
    # Test connection, auth, and subscription
    
async def test_event_broadcasting():
    """Test event broadcasting to multiple clients"""
    # Test that events reach subscribed clients only

# test_event_collector.py
async def test_change_detection():
    """Test tmux change detection"""
    # Test detection of session/window changes
    
async def test_event_generation():
    """Test event generation from tmux state"""
    # Test correct event types and data
```

#### Integration Tests
```python
async def test_end_to_end_monitoring():
    """Test complete monitoring flow"""
    # Start server, connect client, generate tmux changes
    # Verify client receives correct events
```

#### Performance Tests
```python
async def test_concurrent_connections():
    """Test with many concurrent clients"""
    # Connect 100 clients, measure latency and throughput
    
async def test_high_frequency_events():
    """Test with rapid tmux changes"""
    # Generate 1000 events/second, measure delivery
```

### Deployment Configuration

```yaml
# websocket_config.yaml
server:
  host: 0.0.0.0
  port: 8765
  max_connections: 100
  
security:
  require_auth: true
  tls_enabled: false
  tls_cert: null
  tls_key: null
  
performance:
  poll_interval_ms: 500
  event_batch_size: 10
  event_batch_timeout_ms: 50
  max_event_queue_size: 10000
  
monitoring:
  log_level: INFO
  metrics_enabled: true
  metrics_port: 9090
```

### Migration Path

1. **Phase 1**: Deploy alongside existing system (no breaking changes)
2. **Phase 2**: Update orchestrator to emit events
3. **Phase 3**: Migrate monitoring tools to WebSocket
4. **Phase 4**: Deprecate polling-based monitoring
5. **Phase 5**: Remove legacy monitoring code