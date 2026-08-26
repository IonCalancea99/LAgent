"""
Process Manager: Child process lifecycle management for LAgent UI.

Story 8.1: System Tray Icon & Session Control Menu

Implements:
- SessionID generation
- ProcessGroup tracking for a session
- Child process launching with profile/mode mapping
- Graceful and forced termination
- Startup timeout and rollback on failure
"""

import logging
import subprocess
import signal
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from uuid import uuid4
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProcessGroup:
    """Tracks all child processes for a session."""
    
    session_id: str
    mode: str
    profile: str
    processes: Dict[str, subprocess.Popen] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    clean_shutdown: bool = False
    child_exit_codes: Dict[str, int] = field(default_factory=dict)
    
    def add_process(self, name: str, proc: subprocess.Popen) -> None:
        """Add a child process to the group."""
        self.processes[name] = proc
        logger.debug(f"Process group {self.session_id}: added {name} (PID {proc.pid})")
    
    def get_process(self, name: str) -> Optional[subprocess.Popen]:
        """Get a process by name."""
        return self.processes.get(name)
    
    def all_running(self) -> bool:
        """Check if all processes are still running."""
        return all(p.poll() is None for p in self.processes.values())
    
    def mark_ended(self, clean: bool = True) -> None:
        """Mark when the session ended."""
        self.ended_at = datetime.now()
        self.clean_shutdown = clean


class ProcessManager:
    """Manages child process lifecycle for sessions."""
    
    # Profile to process configuration mapping
    PROFILE_CONFIGS = {
        "fishing": {
            "processes": ["gpu_server", "warlord_agent", "orchestrator"],
            "profile": "fishing",
        },
        "combat": {
            "processes": ["gpu_server", "warlord_agent", "prophet_agent", "orchestrator"],
            "profile": "warlord",
        },
        "shadow": {
            "processes": ["gpu_server", "warlord_agent", "prophet_agent", "orchestrator"],
            "profile": "shadow",
        },
    }
    
    def __init__(
        self,
        sessions_db: Optional[Any] = None,
        startup_timeout: float = 30.0,
        shutdown_timeout: float = 5.0,
        project_root: Optional[str] = None,
    ):
        """
        Initialize process manager.
        
        Args:
            sessions_db: SessionsDB instance for recording events
            startup_timeout: Max time to wait for all processes to start
            shutdown_timeout: Grace period before force-kill
            project_root: Project root path for launching subprocesses
        """
        self.sessions_db = sessions_db
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout
        self.project_root = project_root or str(Path(__file__).parent.parent.parent)
        
        # Track active session
        self.current_session: Optional[ProcessGroup] = None
        
        logger.debug(
            f"ProcessManager initialized: "
            f"startup_timeout={startup_timeout}s, shutdown_timeout={shutdown_timeout}s"
        )
    
    def generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid4())
    
    def map_mode_to_profile(self, mode: str) -> Dict[str, Any]:
        """
        Map user-selected mode to internal profile.
        
        Args:
            mode: "fishing", "combat", or "shadow"
        
        Returns:
            Configuration dict with profile and process list
        """
        mode_lower = mode.lower()
        if mode_lower not in self.PROFILE_CONFIGS:
            raise ValueError(f"Unknown mode: {mode}")
        
        return self.PROFILE_CONFIGS[mode_lower]
    
    def start_session(self, mode: str) -> str:
        """
        Start a new session with all child processes.
        
        Args:
            mode: Session mode ("fishing", "combat", "shadow")
        
        Returns:
            Session ID
        
        Raises:
            RuntimeError: If startup fails or times out
        """
        if self.current_session is not None:
            raise RuntimeError("A session is already running")
        
        session_id = self.generate_session_id()
        config = self.map_mode_to_profile(mode)
        profile = config["profile"]
        
        # Create process group
        self.current_session = ProcessGroup(
            session_id=session_id,
            mode=mode,
            profile=profile,
        )
        
        logger.info(f"Starting session {session_id} with mode={mode}, profile={profile}")
        
        # Record in database
        if self.sessions_db:
            self.sessions_db.log_session_start(session_id, profile=profile, mode=mode)
        
        # Launch child processes
        try:
            self._launch_child_processes(self.current_session, config)
        except Exception as e:
            logger.error(f"Failed to launch child processes: {e}")
            self._rollback_startup(self.current_session)
            self.current_session = None
            raise RuntimeError(f"Startup failed: {e}") from e
        
        return session_id
    
    def _launch_child_processes(self, group: ProcessGroup, config: Dict[str, Any]) -> None:
        """
        Launch all child processes for a session.
        
        Args:
            group: ProcessGroup to populate
            config: Configuration from PROFILE_CONFIGS
        """
        startup_start = time.time()
        
        # Validate process list is non-empty
        if not config.get("processes"):
            raise ValueError(f"No processes defined for mode {group.mode}")
        
        for process_name in config["processes"]:
            if time.time() - startup_start > self.startup_timeout:
                raise TimeoutError(f"Startup timeout: {self.startup_timeout}s exceeded")
            
            try:
                proc = self._launch_process(process_name, group.session_id, group.profile)
                group.add_process(process_name, proc)
                
                # Wait to detect immediate failures (increased from 0.5s to 1.0s)
                # Note: This is a heuristic; ideal solution would use process registration via IPC
                time.sleep(1.0)
                if proc.poll() is not None:
                    raise RuntimeError(f"Process {process_name} exited immediately with code {proc.returncode}")
                
            except Exception as e:
                logger.error(f"Failed to launch {process_name}: {e}")
                raise
    
    def _launch_process(self, process_name: str, session_id: str, profile: str) -> subprocess.Popen:
        """
        Launch a single child process.
        
        Args:
            process_name: Name of process (gpu_server, orchestrator, etc.)
            session_id: Session ID to pass to process
            profile: Profile to use (fishing, warlord, shadow)
        
        Returns:
            subprocess.Popen handle
        """
        # Map process name to module and entry point
        # Note: profile parameter from session config determines agent behavior
        process_config = {
            "gpu_server": {
                "module": "lagent.gpu_server",
                "args": ["--session-id", session_id],
            },
            "warlord_agent": {
                "module": "lagent.agent",
                "args": ["--profile", profile, "--session-id", session_id, "--mode", "active"],
            },
            "prophet_agent": {
                "module": "lagent.agent",
                "args": ["--profile", profile, "--session-id", session_id, "--mode", "active"],
            },
            "orchestrator": {
                "module": "lagent.orchestrator",
                "args": ["--session-id", session_id],
            },
        }
        
        if process_name not in process_config:
            raise ValueError(f"Unknown process: {process_name}")
        
        config = process_config[process_name]
        module = config["module"]
        args = config["args"]
        
        # Build command
        cmd = [sys.executable, "-m", module] + args
        
        logger.debug(f"Launching process {process_name}: {' '.join(cmd)}")
        
        # Launch with proper subprocess handling
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.project_root,
            # Prevent inheriting file handles to avoid hanging
            close_fds=True,
        )
        
        logger.info(f"Launched {process_name} with PID {proc.pid}")
        return proc
    
    def _rollback_startup(self, group: ProcessGroup) -> None:
        """Terminate all started processes and log failure."""
        logger.warning(f"Rolling back startup for session {group.session_id}")
        
        # Terminate all processes
        for name, proc in group.processes.items():
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2.0)
                    logger.debug(f"Terminated {name}")
                except subprocess.TimeoutExpired:
                    proc.kill()
                    logger.debug(f"Force-killed {name}")
        
        # Log startup failure event
        if self.sessions_db:
            try:
                self.sessions_db.append_event(
                    group.session_id,
                    source="ui",
                    type="startup_failed",
                    payload={
                        "session_id": group.session_id,
                        "mode": group.mode,
                        "process_count": len(group.processes),
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log startup failure event: {e}")
    
    def stop_session(self) -> None:
        """
        Stop the current running session gracefully.
        
        Performs:
        1. SIGTERM to all child processes
        2. Wait for grace period
        3. Force-kill remaining processes
        4. Record ended_at and completion event
        """
        if self.current_session is None:
            logger.warning("No session to stop")
            return
        
        group = self.current_session
        session_id = group.session_id
        
        logger.info(f"Stopping session {session_id}")
        
        # Phase 1: Send SIGTERM to all
        self._send_termination_signal(group)
        
        # Phase 2: Wait for graceful shutdown
        shutdown_start = time.time()
        while group.all_running() and (time.time() - shutdown_start) < self.shutdown_timeout:
            time.sleep(0.1)
        
        # Phase 3: Force-kill remaining
        remaining = [
            (name, proc) for name, proc in group.processes.items()
            if proc.poll() is None
        ]
        if remaining:
            logger.warning(f"Force-killing {len(remaining)} processes after grace period")
            for name, proc in remaining:
                proc.kill()
                group.child_exit_codes[name] = -9
        
        # Collect exit codes
        for name, proc in group.processes.items():
            if name not in group.child_exit_codes:
                group.child_exit_codes[name] = proc.wait()
        
        # Mark session ended
        outcome = "clean" if all(code == 0 for code in group.child_exit_codes.values()) else "forced"
        group.mark_ended(clean=(outcome == "clean"))
        
        # Record in database
        if self.sessions_db:
            self.sessions_db.log_session_end(session_id, outcome=outcome)
            
            # Log completion event
            try:
                self.sessions_db.append_event(
                    session_id,
                    source="ui",
                    type="session_stopped",
                    payload={
                        "session_id": session_id,
                        "mode": group.mode,
                        "outcome": outcome,
                        "child_exit_codes": group.child_exit_codes,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log session stopped event: {e}")
        
        logger.info(f"Session {session_id} stopped ({outcome})")
        self.current_session = None
    
    def _send_termination_signal(self, group: ProcessGroup) -> None:
        """Send SIGTERM (or Windows equivalent) to all child processes."""
        for name, proc in group.processes.items():
            if proc.poll() is None:
                try:
                    # Use proc.terminate() on all platforms (works better than CTRL_C_EVENT)
                    # CTRL_C_EVENT requires console group, which may not be available for
                    # detached subprocesses. terminate() sends WM_CLOSE on Windows, SIGTERM on Unix.
                    proc.terminate()
                    logger.debug(f"Sent termination signal to {name} (PID {proc.pid})")
                except ProcessLookupError:
                    # Process already exited
                    logger.debug(f"Process {name} already exited")
                except Exception as e:
                    logger.error(f"Failed to send termination signal to {name}: {e}")
    
    def get_session_status(self) -> Optional[Dict[str, Any]]:
        """Get status of current session."""
        if self.current_session is None:
            return None
        
        group = self.current_session
        return {
            "session_id": group.session_id,
            "mode": group.mode,
            "profile": group.profile,
            "running": group.all_running(),
            "processes": {name: proc.poll() is None for name, proc in group.processes.items()},
        }
