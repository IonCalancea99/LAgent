"""
UI process entry point.

Story 8.1: System Tray Icon & Session Control Menu

Entry point: python -m lagent.ui

Launches the system tray icon and session control menu.
Does not import agent/hsl/gpu_server modules (AD-5).
"""

import sys
import logging
import argparse
import threading
import time
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import UI modules (only)
from lagent.common.sessions_db import SessionsDB
from lagent.ui.tray import TrayIcon
from lagent.ui.process_manager import ProcessManager
from lagent.ui.telemetry import TelemetryLogger, TelemetryReader
from lagent.ui.overlay import StatusOverlay, QApplication
from lagent.ui.notifications import NotificationAdapter
from lagent.ui.state import UIEvent, UIState, reduce_state, SessionState


class UIController:
    """Orchestrates tray icon, menu, and process management."""
    
    def __init__(
        self,
        db_path: str = "data/sessions.db",
        icon_path: Optional[str] = None,
        startup_timeout: float = 30.0,
        shutdown_timeout: float = 5.0,
        telemetry_stale_after: float = 2.0,
        monitor_interval: float = 0.5,
    ):
        """
        Initialize UI controller.
        
        Args:
            db_path: Path to sessions database
            icon_path: Path to tray icon asset
            startup_timeout: Max time for child processes to start
            shutdown_timeout: Grace period before force-kill
        """
        self.db_path = db_path
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout
        self.telemetry_stale_after = telemetry_stale_after
        self.monitor_interval = monitor_interval
        
        # Initialize components
        self.db = SessionsDB(db_path)
        self.process_manager = ProcessManager(
            sessions_db=self.db,
            startup_timeout=startup_timeout,
            shutdown_timeout=shutdown_timeout,
        )
        self.telemetry = TelemetryLogger(self.db)
        self.telemetry_reader = TelemetryReader(db_path, stale_after=telemetry_stale_after)
        self.notifications = NotificationAdapter()
        self.state = UIState()
        
        # Default icon path
        if icon_path is None:
            icon_path = self._find_icon_asset()
        
        self.tray = TrayIcon(icon_path=icon_path)
        self._overlay_app = None
        self.overlay = None
        self._monitor_stop = threading.Event()
        self._monitor_thread = None
        self._exiting = False
        
        # Register menu callbacks
        self._setup_menu_callbacks()
        
        logger.info("UI Controller initialized")
    
    def _find_icon_asset(self) -> str:
        """Find or create a default icon asset."""
        # Look for icon in common locations
        icon_paths = [
            Path("lagent/ui/assets/icon.png"),
            Path("lagent/ui/assets/icon.ico"),
            Path("assets/icon.png"),
            Path("assets/icon.ico"),
        ]
        
        for path in icon_paths:
            if path.exists():
                logger.debug(f"Found icon asset: {path}")
                return str(path)
        
        # If no icon found, create a minimal placeholder
        try:
            from PIL import Image
            
            assets_dir = Path("lagent/ui/assets")
            assets_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a simple 32x32 pixel icon
            img = Image.new("RGBA", (32, 32), color=(0, 120, 215, 255))
            icon_path = assets_dir / "icon.png"
            img.save(icon_path)
            
            logger.info(f"Created default icon asset: {icon_path}")
            return str(icon_path)
        except ImportError:
            logger.warning("PIL not available, using fallback icon")
            return "icon.png"  # Will fail if icon doesn't exist
    
    def _setup_menu_callbacks(self) -> None:
        """Register callbacks for menu actions."""
        self.tray.setup_menu_callbacks(
            on_start_fishing=self._on_start_session_fishing,
            on_start_combat=self._on_start_session_combat,
            on_start_shadow=self._on_start_session_shadow,
            on_stop_session=self._on_stop_session,
            on_toggle_recording=self._on_toggle_recording,
            on_toggle_overlay=self._on_toggle_overlay,
            on_exit=self._on_exit,
        )
    
    def _on_start_session_fishing(self) -> None:
        """Handle Start Session -> Fishing."""
        logger.info("User selected Start Session -> Fishing")
        self._start_session("fishing")
    
    def _on_start_session_combat(self) -> None:
        """Handle Start Session -> Combat."""
        logger.info("User selected Start Session -> Combat")
        self._start_session("combat")
    
    def _on_start_session_shadow(self) -> None:
        """Handle Start Session -> Shadow."""
        logger.info("User selected Start Session -> Shadow")
        self._start_session("shadow")
    
    def _start_session(self, mode: str) -> None:
        """Start a session with the given mode."""
        try:
            self.tray.menu.on_session_starting()
            self.state = reduce_state(self.state, UIEvent("startup_started", "pending", {"mode": mode}))
            
            # Start the session
            session_id = self.process_manager.start_session(mode, self.tray.menu.state.recording_mode_active)
            self.state = reduce_state(self.state, UIEvent("startup_started", session_id, {
                "mode": mode, "profile": self.process_manager.current_session.profile,
                "recording": self.tray.menu.state.recording_mode_active,
            }))
            if self.overlay is not None:
                self.overlay.session_id = session_id
            
            # Log telemetry
            self.telemetry.log_startup_started(
                session_id,
                mode=mode,
                profile=self.process_manager.current_session.profile
            )
            
            # Processes are running, enable Stop
            self.tray.menu.on_processes_registered()
            self.state = reduce_state(self.state, UIEvent("startup_complete", session_id))
            self.tray.update_state(self.state)
            
            # Log startup complete
            self.telemetry.log_startup_complete(session_id)
            
            logger.info(f"Session {session_id} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            self.tray.menu.on_session_stopped()
            self.state = UIState()
            self.tray.update_state(self.state)
            
            # Log error
            try:
                self.telemetry.log_ui_error(
                    session_id=None,
                    error_type="startup_failed",
                    error_message=str(e),
                )
            except Exception:
                pass
    
    def _on_stop_session(self) -> None:
        """Handle Stop Session."""
        logger.info("User selected Stop Session")
        
        try:
            self.process_manager.stop_session()
            self.tray.menu.on_session_stopped()
            self.state = reduce_state(self.state, UIEvent("session_stopped", self.state.session_id))
            self.tray.update_state(self.state)
            if self.overlay is not None:
                self.overlay.session_id = None
            logger.info("Session stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping session: {e}")
    
    def _on_toggle_recording(self) -> None:
        """Handle Recording Mode toggle."""
        logger.info("User toggled Recording Mode")
        requested = not self.tray.menu.state.recording_mode_active
        session = self.process_manager.current_session
        if session is not None:
            try:
                self.process_manager.restart_recording(requested)
                self.telemetry.log_recording_mode_changed(session.session_id, requested)
            except Exception as exc:
                self.state = reduce_state(self.state, UIEvent("recording_restart_failed", session.session_id))
                self.tray.update_state(self.state)
                try:
                    self.telemetry.log_session_halted(session.session_id, "recording_restart_failed")
                except Exception:
                    logger.exception("Failed to log recording restart failure")
                self.notifications.notify_halted(session.session_id, "recording_restart_failed")
                logger.error("Recording restart failed: %s", exc)
                return
        self.tray.menu.state.recording_mode_active = requested
        self.tray.menu.recording_mode_toggle.label = f"Recording Mode: {'ON' if requested else 'OFF'}"
        if session is not None:
            self.state = reduce_state(self.state, UIEvent("recording_started" if requested else "recording_stopped", session.session_id))
        self.tray.update_state(self.state)

    def handle_session_event(self, event: UIEvent) -> None:
        """Apply an orchestrator/child event without blocking the tray callback."""
        previous = self.state
        self.state = reduce_state(self.state, event)
        self.tray.update_state(self.state)
        if self.state.status == SessionState.HALTED and previous.status != SessionState.HALTED:
            event_id = self.state.halt_event_id or event.type
            self.notifications.notify_halted(self.state.session_id, event_id)

    def _monitor_once(self) -> None:
        """Poll process and telemetry health without blocking tray callbacks."""
        session = self.process_manager.current_session
        if session is None or self.state.status not in {SessionState.RUNNING, SessionState.RECORDING}:
            return
        session_id = session.session_id
        for process_name, process in session.processes.items():
            if process.poll() is not None:
                self.handle_session_event(UIEvent("child_exited", session_id, {
                    "event_id": f"child_exited:{process_name}",
                    "process": process_name,
                    "returncode": process.returncode,
                }))
                try:
                    self.telemetry.log_session_halted(session_id, "child_exited", f"child_exited:{process_name}")
                except Exception:
                    logger.exception("Failed to log child exit")
                return
        latest = self.telemetry_reader.latest_event_time(session_id)
        stale = latest is None or (time.time() - latest.timestamp()) > self.telemetry_stale_after
        self.handle_session_event(UIEvent("refresh_timeout" if stale else "telemetry_fresh", session_id))

    def _monitor_loop(self) -> None:
        while not self._monitor_stop.wait(self.monitor_interval):
            try:
                self._monitor_once()
            except Exception:
                logger.exception("Session health monitor failed")

    def _start_monitor(self) -> None:
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._monitor_stop.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_loop, name="lagent-ui-monitor", daemon=True)
            self._monitor_thread.start()

    def _stop_monitor(self) -> None:
        self._monitor_stop.set()
        if self._monitor_thread is not None and self._monitor_thread is not threading.current_thread():
            self._monitor_thread.join(timeout=max(1.0, self.monitor_interval * 2))
        self._monitor_thread = None
    
    def _on_toggle_overlay(self) -> None:
        """Handle Status Overlay toggle."""
        logger.info("User toggled Status Overlay")
        if self.tray.menu.state.status_overlay_active:
            if self.overlay is not None:
                self.overlay.close()
            self.tray.menu.toggle_status_overlay()
            return
        if QApplication is None:
            logger.warning("PyQt6 is not installed; status overlay unavailable")
            return
        if self._overlay_app is None:
            self._overlay_app = QApplication.instance() or QApplication([])
        session_id = (self.process_manager.current_session.session_id
                       if self.process_manager.current_session else None)
        if self.overlay is None:
            self.overlay = StatusOverlay(self.db_path, session_id=session_id)
        else:
            self.overlay.session_id = session_id
        self.overlay.show_overlay()
        self.tray.menu.toggle_status_overlay()

    def _run_qt_event_loop(self) -> None:
        """Run the Qt event loop while pystray owns its detached loop."""
        if self._overlay_app is None:
            self._overlay_app = QApplication.instance() or QApplication([])
        self.tray.show_detached()
        self._overlay_app.exec()
    
    def _on_exit(self) -> None:
        """Handle Exit."""
        # Guard against re-entrancy: this callback runs on pystray's own
        # thread and sys.exit() there does not stop the Qt main loop, so a
        # slow/duplicate click could otherwise run this teardown twice.
        if self._exiting:
            logger.debug("Exit already in progress, ignoring duplicate request")
            return
        self._exiting = True

        logger.info("User selected Exit")
        self._stop_monitor()
        
        # Stop session if running
        if self.process_manager.current_session:
            try:
                self.process_manager.stop_session()
            except Exception as e:
                logger.error(f"Error stopping session before exit: {e}")
        
        # Close database
        try:
            self.db.close()
        except Exception as e:
            logger.error(f"Error closing database: {e}")

        if self.overlay is not None:
            self.overlay.close()
        
        # Exit tray
        self.tray.hide()

        # sys.exit() only unwinds the thread it's called from (pystray's
        # dispatch thread here), so it can't stop the Qt event loop running
        # on the main thread. Quit the Qt app directly if it exists, and
        # only fall back to sys.exit() when there is no Qt loop to stop.
        if self._overlay_app is not None:
            self._overlay_app.quit()
        else:
            sys.exit(0)
    
    def run(self) -> None:
        """Run the UI (blocking call)."""
        logger.info("Starting LAgent UI")
        
        try:
            self._start_monitor()
            if QApplication is None:
                self.tray.show()
            else:
                self._run_qt_event_loop()
        except Exception as e:
            logger.error(f"Fatal error in UI: {e}", exc_info=True)
            sys.exit(1)
        finally:
            self._stop_monitor()
            # Cleanup
            try:
                self.db.close()
            except Exception:
                pass


def main():
    """Entry point for lagent.ui."""
    parser = argparse.ArgumentParser(
        description="LAgent System Tray UI - Session Control Menu",
    )
    parser.add_argument(
        "--db-path",
        default="data/sessions.db",
        help="Path to sessions database",
    )
    parser.add_argument(
        "--icon-path",
        default=None,
        help="Path to tray icon asset",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=30.0,
        help="Max time for child processes to start (seconds)",
    )
    parser.add_argument(
        "--shutdown-timeout",
        type=float,
        default=5.0,
        help="Grace period before force-killing processes (seconds)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate command-line startup without opening the UI event loop",
    )
    
    args = parser.parse_args()
    
    # Update logging level
    logging.getLogger().setLevel(args.log_level)

    if args.check:
        return
    
    # Create and run controller
    controller = UIController(
        db_path=args.db_path,
        icon_path=args.icon_path,
        startup_timeout=args.startup_timeout,
        shutdown_timeout=args.shutdown_timeout,
    )
    
    try:
        controller.run()
    except KeyboardInterrupt:
        logger.info("UI interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
