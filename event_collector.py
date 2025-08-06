"""
Event Collector for Tmux Monitoring
Detects changes in tmux sessions and generates events
"""

import asyncio
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from tmux_core import TmuxCommand

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TmuxEvent:
    """Represents a tmux event"""
    type: str
    timestamp: str
    session: Optional[str] = None
    window: Optional[int] = None
    pane: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """Convert event to dictionary"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class TmuxEventCollector:
    """Collects events from tmux sessions"""
    
    def __init__(self, poll_interval=0.5):
        self.poll_interval = poll_interval
        self.tmux_cmd = TmuxCommand()
        self.previous_state = {}
        self.previous_pane_content = {}
        self.running = False
        
    async def start_collecting(self, event_queue: asyncio.Queue):
        """Start collecting tmux events"""
        self.running = True
        logger.info(f"Starting event collection with {self.poll_interval}s interval")
        
        # Get initial state
        self.previous_state = await self.get_current_state()
        
        while self.running:
            try:
                events = await self.detect_changes()
                for event in events:
                    await event_queue.put(event.to_dict())
                    logger.debug(f"Generated event: {event.type}")
                    
                # Handle snapshot requests
                try:
                    # Check for snapshot requests with zero timeout
                    while True:
                        snapshot_request = event_queue.get_nowait()
                        if snapshot_request.get("type") == "snapshot.request":
                            snapshot_events = await self.handle_snapshot_request(snapshot_request)
                            for event in snapshot_events:
                                await event_queue.put(event.to_dict())
                except asyncio.QueueEmpty:
                    pass
                    
            except Exception as e:
                logger.error(f"Error in event collection: {e}")
                
            await asyncio.sleep(self.poll_interval)
    
    async def get_current_state(self) -> Dict[str, Any]:
        """Get current tmux state"""
        state = {}
        
        try:
            # Get all sessions
            sessions_result = self.tmux_cmd.execute_command(
                ["tmux", "list-sessions", "-F", "#{session_name}:#{session_attached}"],
                check=False
            )
            
            if sessions_result.returncode == 0 and sessions_result.stdout:
                for line in sessions_result.stdout.strip().split('\n'):
                    if line and ':' in line:
                        session_name, attached = line.split(':', 1)
                        
                        # Get windows for this session
                        windows_result = self.tmux_cmd.execute_command(
                            ["tmux", "list-windows", "-t", session_name,
                             "-F", "#{window_index}:#{window_name}:#{window_active}"],
                            check=False
                        )
                        
                        session_state = {
                            "info": {"attached": attached == "1"},
                            "windows": {}
                        }
                        
                        if windows_result.returncode == 0 and windows_result.stdout:
                            for window_line in windows_result.stdout.strip().split('\n'):
                                if window_line and ':' in window_line:
                                    parts = window_line.split(':')
                                    if len(parts) >= 3:
                                        window_id = int(parts[0])
                                        window_name = parts[1]
                                        window_active = parts[2] == "1"
                                        
                                        # Get panes for this window
                                        panes_result = self.tmux_cmd.execute_command(
                                            ["tmux", "list-panes", "-t", f"{session_name}:{window_id}",
                                             "-F", "#{pane_index}:#{pane_active}"],
                                            check=False
                                        )
                                        
                                        panes = {}
                                        if panes_result.returncode == 0 and panes_result.stdout:
                                            for pane_line in panes_result.stdout.strip().split('\n'):
                                                if pane_line and ':' in pane_line:
                                                    pane_parts = pane_line.split(':')
                                                    if len(pane_parts) >= 2:
                                                        panes[int(pane_parts[0])] = {
                                                            "active": pane_parts[1] == "1"
                                                        }
                                        
                                        window_state = {
                                            "info": {"name": window_name},
                                            "panes": panes,
                                            "active": window_active
                                        }
                                        
                                        session_state["windows"][window_id] = window_state
                        
                        state[session_name] = session_state
                
        except Exception as e:
            logger.error(f"Error getting tmux state: {e}")
        
        return state
    
    async def detect_changes(self) -> List[TmuxEvent]:
        """Detect changes in tmux state"""
        events = []
        current_state = await self.get_current_state()
        
        # Debug logging
        if current_state != self.previous_state:
            logger.debug(f"State changed - Current sessions: {list(current_state.keys())}, Previous: {list(self.previous_state.keys())}")
        
        # Detect session changes
        events.extend(self.detect_session_changes(current_state))
        
        # Detect window changes
        for session in current_state:
            if session in self.previous_state:
                events.extend(
                    self.detect_window_changes(
                        session,
                        self.previous_state[session].get("windows", {}),
                        current_state[session].get("windows", {})
                    )
                )
        
        # Detect pane changes and activity
        events.extend(await self.detect_pane_activity(current_state))
        
        self.previous_state = current_state
        return events
    
    def detect_session_changes(self, current_state: Dict) -> List[TmuxEvent]:
        """Detect session-level changes"""
        events = []
        
        # New sessions
        for session in current_state:
            if session not in self.previous_state:
                events.append(TmuxEvent(
                    type="session.created",
                    timestamp=datetime.now().isoformat(),
                    session=session,
                    data={"session_info": current_state[session].get("info")}
                ))
        
        # Removed sessions
        for session in self.previous_state:
            if session not in current_state:
                events.append(TmuxEvent(
                    type="session.removed",
                    timestamp=datetime.now().isoformat(),
                    session=session
                ))
        
        # Session property changes
        for session in set(current_state.keys()) & set(self.previous_state.keys()):
            prev_info = self.previous_state[session].get("info", {})
            curr_info = current_state[session].get("info", {})
            
            # Check for attached/detached changes
            if prev_info.get("attached") != curr_info.get("attached"):
                events.append(TmuxEvent(
                    type="session.attached" if curr_info.get("attached") else "session.detached",
                    timestamp=datetime.now().isoformat(),
                    session=session
                ))
        
        return events
    
    def detect_window_changes(self, session: str, prev_windows: Dict, curr_windows: Dict) -> List[TmuxEvent]:
        """Detect window-level changes"""
        events = []
        
        # New windows
        for window_id in curr_windows:
            if window_id not in prev_windows:
                events.append(TmuxEvent(
                    type="window.created",
                    timestamp=datetime.now().isoformat(),
                    session=session,
                    window=window_id,
                    data={"window_info": curr_windows[window_id].get("info")}
                ))
        
        # Removed windows
        for window_id in prev_windows:
            if window_id not in curr_windows:
                events.append(TmuxEvent(
                    type="window.removed",
                    timestamp=datetime.now().isoformat(),
                    session=session,
                    window=window_id
                ))
        
        # Window property changes
        for window_id in set(curr_windows.keys()) & set(prev_windows.keys()):
            prev_info = prev_windows[window_id].get("info", {})
            curr_info = curr_windows[window_id].get("info", {})
            
            # Window renamed
            if prev_info.get("name") != curr_info.get("name"):
                events.append(TmuxEvent(
                    type="window.renamed",
                    timestamp=datetime.now().isoformat(),
                    session=session,
                    window=window_id,
                    data={
                        "old_name": prev_info.get("name"),
                        "new_name": curr_info.get("name")
                    }
                ))
            
            # Active window changed
            prev_active = prev_windows[window_id].get("active", False)
            curr_active = curr_windows[window_id].get("active", False)
            if prev_active != curr_active and curr_active:
                events.append(TmuxEvent(
                    type="window.activated",
                    timestamp=datetime.now().isoformat(),
                    session=session,
                    window=window_id
                ))
        
        return events
    
    async def detect_pane_activity(self, current_state: Dict) -> List[TmuxEvent]:
        """Detect pane activity and content changes"""
        events = []
        
        for session_name, session_state in current_state.items():
            for window_id, window_state in session_state.get("windows", {}).items():
                for pane_id, pane_info in window_state.get("panes", {}).items():
                    pane_key = f"{session_name}:{window_id}.{pane_id}"
                    
                    # Get current pane content (last few lines)
                    try:
                        result = self.tmux_cmd.execute_command(
                            ["tmux", "capture-pane", 
                             "-t", f"{session_name}:{window_id}.{pane_id}",
                             "-p", "-S", "-10"],
                            check=False
                        )
                        
                        if result.returncode == 0:
                            current_content = result.stdout
                            content_hash = self.calculate_content_hash(current_content)
                            
                            # Check if content changed
                            if pane_key in self.previous_pane_content:
                                if self.previous_pane_content[pane_key] != content_hash:
                                    # Analyze the type of activity
                                    activity_type = self.analyze_activity(current_content)
                                    
                                    events.append(TmuxEvent(
                                        type=f"pane.{activity_type}",
                                        timestamp=datetime.now().isoformat(),
                                        session=session_name,
                                        window=window_id,
                                        pane=pane_id,
                                        data={
                                            "preview": self.get_safe_preview(current_content),
                                            "activity": activity_type
                                        }
                                    ))
                            
                            self.previous_pane_content[pane_key] = content_hash
                            
                    except Exception as e:
                        logger.debug(f"Could not capture pane {pane_key}: {e}")
        
        return events
    
    async def handle_snapshot_request(self, request: Dict) -> List[TmuxEvent]:
        """Handle a snapshot request"""
        events = []
        target = request.get("target", {})
        client_id = request.get("client_id")
        
        try:
            if "session" in target:
                session = target["session"]
                
                if "window" in target:
                    # Specific window snapshot
                    window = target["window"]
                    result = self.tmux_cmd.execute_command(
                        ["tmux", "capture-pane",
                         "-t", f"{session}:{window}",
                         "-p"],
                        check=False
                    )
                    
                    if result.returncode == 0:
                        events.append(TmuxEvent(
                            type="snapshot.data",
                            timestamp=datetime.now().isoformat(),
                            session=session,
                            window=window,
                            data={
                                "content": result.stdout,
                                "client_id": client_id
                            }
                        ))
                else:
                    # Full session snapshot
                    windows_result = self.tmux_cmd.execute_command(
                        ["tmux", "list-windows", "-t", session,
                         "-F", "#{window_index}:#{window_name}"],
                        check=False
                    )
                    
                    windows = {}
                    if windows_result.returncode == 0 and windows_result.stdout:
                        for line in windows_result.stdout.strip().split('\n'):
                            if line and ':' in line:
                                parts = line.split(':', 1)
                                windows[int(parts[0])] = {"name": parts[1]}
                    
                    session_data = {
                        "windows": windows,
                        "client_id": client_id
                    }
                    
                    events.append(TmuxEvent(
                        type="snapshot.data",
                        timestamp=datetime.now().isoformat(),
                        session=session,
                        data=session_data
                    ))
            else:
                # Full system snapshot
                state = await self.get_current_state()
                events.append(TmuxEvent(
                    type="snapshot.data",
                    timestamp=datetime.now().isoformat(),
                    data={
                        "full_state": state,
                        "client_id": client_id
                    }
                ))
                
        except Exception as e:
            logger.error(f"Error handling snapshot request: {e}")
            events.append(TmuxEvent(
                type="snapshot.error",
                timestamp=datetime.now().isoformat(),
                data={
                    "error": str(e),
                    "client_id": client_id
                }
            ))
        
        return events
    
    def calculate_content_hash(self, content: str) -> str:
        """Calculate hash of content for change detection"""
        return hashlib.md5(content.encode()).hexdigest()
    
    def analyze_activity(self, content: str) -> str:
        """Analyze content to determine activity type"""
        lines = content.strip().split('\n')
        
        # Check for common patterns
        if any('error' in line.lower() for line in lines[-3:]):
            return "error"
        elif any('warning' in line.lower() for line in lines[-3:]):
            return "warning"
        elif any(line.strip().startswith('$') or line.strip().startswith('#') for line in lines[-2:]):
            return "command"
        else:
            return "output"
    
    def get_safe_preview(self, content: str, max_lines=3, max_chars=200) -> str:
        """Get a safe preview of content"""
        lines = content.strip().split('\n')
        preview_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        preview = '\n'.join(preview_lines)
        
        if len(preview) > max_chars:
            preview = preview[:max_chars] + "..."
        
        return preview
    
    async def stop(self):
        """Stop event collection"""
        self.running = False
        logger.info("Stopping event collection")


async def main():
    """Main entry point for testing"""
    collector = TmuxEventCollector()
    queue = asyncio.Queue()
    
    try:
        await collector.start_collecting(queue)
    except KeyboardInterrupt:
        await collector.stop()


if __name__ == "__main__":
    asyncio.run(main())