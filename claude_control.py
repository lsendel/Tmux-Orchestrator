#!/usr/bin/env python3
"""
Claude Control - Core orchestrator management module
Handles agent lifecycle, status reporting, and health checks
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class ClaudeOrchestrator:
    """Main orchestrator control class"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.resolve()

        # Security check - ensure we're in the expected directory
        if not (self.base_dir / "claude_control.py").exists():
            raise RuntimeError(
                "Security check failed: claude_control.py not found in expected location"
            )
        self.registry_dir = self.base_dir / "registry"
        self.registry_dir.mkdir(exist_ok=True)
        self.sessions_file = self.registry_dir / "sessions.json"
        self.logs_dir = self.registry_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

    def get_active_sessions(self) -> List[Dict]:
        """Get all active tmux sessions with Claude agents"""
        try:
            result = subprocess.run(
                [
                    "tmux",
                    "list-sessions",
                    "-F",
                    "#{session_name}:#{session_created}:#{session_windows}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            sessions = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    name, created, windows = line.split(":")
                    sessions.append(
                        {
                            "name": name,
                            "created": created,
                            "windows": int(windows),
                            "agents": self._get_session_agents(name),
                        }
                    )
            return sessions
        except subprocess.CalledProcessError:
            return []

    def _get_session_agents(self, session_name: str) -> List[Dict]:
        """Get all Claude agents in a session"""
        agents = []
        try:
            result = subprocess.run(
                [
                    "tmux",
                    "list-windows",
                    "-t",
                    session_name,
                    "-F",
                    "#{window_index}:#{window_name}:#{pane_current_command}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    idx, name, cmd = line.split(":", 2)
                    if "claude" in name.lower() or cmd == "node":
                        agents.append(
                            {
                                "window": int(idx),
                                "name": name,
                                "command": cmd,
                                "status": self._check_agent_health(session_name, idx),
                            }
                        )
        except subprocess.CalledProcessError:
            pass
        return agents

    def _check_agent_health(self, session: str, window: str) -> str:
        """Check if an agent is responsive"""
        try:
            # Capture last lines to check for activity
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", f"{session}:{window}", "-p", "-S", "-5"],
                capture_output=True,
                text=True,
                check=True,
            )
            output = result.stdout.strip()

            # Check for common Claude prompt indicators
            if ">" in output or "?" in output:
                return "ready"
            elif "error" in output.lower():
                return "error"
            else:
                return "busy"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
            import logging

            logging.warning(f"Health check failed for {session}:{window}: {e}")
            return "unknown"

    def status(self, detailed: bool = False) -> None:
        """Print orchestrator status"""
        sessions = self.get_active_sessions()

        print(f"\n🎯 Tmux Orchestrator Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        if not sessions:
            print("❌ No active sessions found")
            return

        total_agents = sum(len(s["agents"]) for s in sessions)
        print(f"📊 Active Sessions: {len(sessions)} | Total Agents: {total_agents}")
        print()

        for session in sessions:
            print(f"📁 Session: {session['name']} ({session['windows']} windows)")

            if detailed and session["agents"]:
                for agent in session["agents"]:
                    status_icon = {"ready": "✅", "busy": "🔄", "error": "❌", "unknown": "❓"}.get(
                        agent["status"], "❓"
                    )

                    print(
                        f"   {status_icon} Window {agent['window']}: "
                        f"{agent['name']} - {agent['status']}"
                    )
            elif session["agents"]:
                print(f"   🤖 {len(session['agents'])} Claude agents active")
            print()

    def save_registry(self) -> None:
        """Save current session registry"""
        sessions = self.get_active_sessions()
        registry = {"updated": datetime.now().isoformat(), "sessions": sessions}

        with open(self.sessions_file, "w") as f:
            json.dump(registry, f, indent=2)

        print(f"✅ Registry saved to {self.sessions_file}")

    def health_check(self) -> Dict:
        """Perform system health check"""
        health = {
            "timestamp": datetime.now().isoformat(),
            "tmux_available": self._check_tmux(),
            "claude_available": self._check_claude(),
            "active_sessions": len(self.get_active_sessions()),
            "issues": [],
        }

        # Check for common issues
        if not health["tmux_available"]:
            health["issues"].append("tmux not available")

        if not health["claude_available"]:
            health["issues"].append("claude command not found")

        return health

    def _check_tmux(self) -> bool:
        """Check if tmux is available"""
        try:
            subprocess.run(["tmux", "-V"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _check_claude(self) -> bool:
        """Check if claude command is available"""
        # Use our get_claude_command.sh script
        script_path = self.base_dir / "get_claude_command.sh"
        if script_path.exists():
            try:
                result = subprocess.run([str(script_path)], capture_output=True, text=True)
                return result.returncode == 0
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        return False


def main():
    """CLI entry point"""
    orchestrator = ClaudeOrchestrator()

    if len(sys.argv) < 2:
        orchestrator.status()
        return

    command = sys.argv[1]

    if command == "status":
        detailed = len(sys.argv) > 2 and sys.argv[2] == "detailed"
        orchestrator.status(detailed)
    elif command == "save":
        orchestrator.save_registry()
    elif command == "health":
        health = orchestrator.health_check()
        print(json.dumps(health, indent=2))
    else:
        print(f"Unknown command: {command}")
        print("Usage: claude_control.py [status|save|health] [detailed]")
        sys.exit(1)


if __name__ == "__main__":
    main()
