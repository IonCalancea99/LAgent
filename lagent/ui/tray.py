"""
Tray UI: System tray icon and menu management for LAgent UI.

Story 8.1: System Tray Icon & Session Control Menu

Implements:
- System tray icon with pystray
- Menu structure with start/stop/toggle options
- Menu state management (enabled/disabled transitions)
- Does not import agent/hsl/gpu_server modules (AD-5, AD-12)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, List, Dict, Any
from lagent.ui.state import UIState, SessionState, format_tooltip
from lagent.ui.telemetry import QuestSnapshot, format_quest_summary

logger = logging.getLogger(__name__)


class SessionMode(Enum):
    """Session modes available to user."""
    FISHING = "fishing"
    COMBAT = "combat"
    SHADOW = "shadow"


@dataclass
class MenuState:
    """Current menu state (enabled/disabled for each item)."""
    start_session_enabled: bool = True
    stop_session_enabled: bool = False
    recording_mode_enabled: bool = False
    status_overlay_enabled: bool = False
    recording_mode_active: bool = False
    status_overlay_active: bool = False


class SessionStartItem:
    """Start Session submenu item with modes."""
    
    def __init__(self):
        """Initialize with available session modes."""
        self.modes = {
            "Fishing": SessionMode.FISHING,
            "Combat": SessionMode.COMBAT,
            "Shadow": SessionMode.SHADOW,
        }
        self.enabled = True
        self.callbacks: Dict[str, Callable] = {}
    
    def register_callback(self, mode_name: str, callback: Callable) -> None:
        """Register callback for a mode."""
        self.callbacks[mode_name] = callback
    
    def on_mode_selected(self, mode_name: str) -> None:
        """Call the callback for selected mode."""
        if mode_name in self.callbacks:
            self.callbacks[mode_name]()
        else:
            logger.warning(f"No callback registered for mode: {mode_name}")


class MenuItem:
    """Generic menu item with label and callback."""
    
    def __init__(self, label: str, callback: Optional[Callable] = None, enabled: bool = True):
        """Initialize menu item."""
        self.label = label
        self.callback = callback
        self.enabled = enabled
    
    def invoke(self) -> None:
        """Invoke the callback if set and enabled."""
        if self.enabled and self.callback:
            self.callback()
        elif not self.enabled:
            logger.debug(f"Menu item disabled: {self.label}")


class Menu:
    """System tray menu structure and state management."""
    
    def __init__(self):
        """Initialize menu with all items."""
        self.state = MenuState()
        
        # Menu items
        self.start_session = SessionStartItem()
        self.stop_session = MenuItem("Stop Session", enabled=False)
        self.recording_mode_toggle = MenuItem("Recording Mode: OFF", enabled=False)
        self.status_overlay_toggle = MenuItem("Status Overlay: OFF", enabled=False)
        self.exit = MenuItem("Exit")
        
        # Track session state
        self._session_running = False
        self._processes_registered = False
    
    def get_state(self) -> MenuState:
        """Get current menu state."""
        return MenuState(
            start_session_enabled=self.start_session.enabled,
            stop_session_enabled=self.stop_session.enabled,
            recording_mode_enabled=self.recording_mode_toggle.enabled,
            status_overlay_enabled=self.status_overlay_toggle.enabled,
            recording_mode_active=self.state.recording_mode_active,
            status_overlay_active=self.state.status_overlay_active,
        )
    
    def on_session_starting(self) -> None:
        """Called when user selects Start Session -> Mode."""
        self._session_running = True
        self._processes_registered = False
        
        # Disable Start, keep Stop disabled until processes register
        self.start_session.enabled = False
        self.stop_session.enabled = False
        
        logger.debug("Menu: session starting, Start disabled, Stop disabled")
    
    def on_processes_registered(self) -> None:
        """Called when all child processes are registered and running."""
        self._processes_registered = True
        
        # Now Stop is enabled
        self.stop_session.enabled = True
        self.recording_mode_toggle.enabled = True
        self.status_overlay_toggle.enabled = True
        
        logger.debug("Menu: processes registered, Stop enabled")
    
    def on_session_stopped(self) -> None:
        """Called when session terminates."""
        self._session_running = False
        self._processes_registered = False
        
        # Re-enable Start, disable Stop
        self.start_session.enabled = True
        self.stop_session.enabled = False
        self.recording_mode_toggle.enabled = False
        self.status_overlay_toggle.enabled = False
        
        logger.debug("Menu: session stopped, Start enabled, Stop disabled")
    
    def toggle_recording_mode(self) -> None:
        """Toggle recording mode state and update menu label."""
        self.state.recording_mode_active = not self.state.recording_mode_active
        status = "ON" if self.state.recording_mode_active else "OFF"
        self.recording_mode_toggle.label = f"Recording Mode: {status}"
        logger.debug(f"Recording mode toggled: {status}")
    
    def toggle_status_overlay(self) -> None:
        """Toggle status overlay state and update menu label."""
        self.state.status_overlay_active = not self.state.status_overlay_active
        status = "ON" if self.state.status_overlay_active else "OFF"
        self.status_overlay_toggle.label = f"Status Overlay: {status}"
        logger.debug(f"Status overlay toggled: {status}")

    def apply_state(self, state: UIState) -> None:
        """Project the canonical session state into menu enabled states."""
        active = state.status in {SessionState.STARTING, SessionState.RUNNING, SessionState.RECORDING, SessionState.STOPPING}
        self.start_session.enabled = not active and state.status != SessionState.UNKNOWN
        self.stop_session.enabled = active and state.status != SessionState.STARTING
        self.recording_mode_toggle.enabled = self.stop_session.enabled
        self.status_overlay_toggle.enabled = self.stop_session.enabled
        self.state.recording_mode_active = state.recording
        status = "ON" if state.recording else "OFF"
        self.recording_mode_toggle.label = f"Recording Mode: {status}"


class TrayIcon:
    """System tray icon manager."""
    
    def __init__(self, icon_path: str):
        """
        Initialize tray icon.
        
        Args:
            icon_path: Path to icon asset (PNG, ICO, etc.)
        """
        self.icon_path = icon_path
        self.menu = Menu()
        self._icon_instance = None
        self._stop_event = None
        self.state = UIState()
        self.icon_state = "idle"
        self._base_tooltip = format_tooltip(self.state)
        self.tooltip = self._base_tooltip
        
        logger.debug(f"TrayIcon initialized with icon: {icon_path}")
    
    def setup_menu_callbacks(
        self,
        on_start_fishing: Callable,
        on_start_combat: Callable,
        on_start_shadow: Callable,
        on_stop_session: Callable,
        on_toggle_recording: Callable,
        on_toggle_overlay: Callable,
        on_exit: Callable,
    ) -> None:
        """
        Register callbacks for menu actions.
        
        Args:
            on_start_fishing: Callback when Start -> Fishing selected
            on_start_combat: Callback when Start -> Combat selected
            on_start_shadow: Callback when Start -> Shadow selected
            on_stop_session: Callback when Stop Session selected
            on_toggle_recording: Callback for recording toggle
            on_toggle_overlay: Callback for overlay toggle
            on_exit: Callback for Exit
        """
        self.menu.start_session.register_callback("Fishing", on_start_fishing)
        self.menu.start_session.register_callback("Combat", on_start_combat)
        self.menu.start_session.register_callback("Shadow", on_start_shadow)
        
        self.menu.stop_session.callback = on_stop_session
        self.menu.recording_mode_toggle.callback = on_toggle_recording
        self.menu.status_overlay_toggle.callback = on_toggle_overlay
        self.menu.exit.callback = on_exit
        
        logger.debug("Menu callbacks registered")
    
    def get_icon_instance(self):
        """
        Get or create pystray.Icon instance.
        
        This is lazy-loaded so that pystray is only imported if actually used.
        On non-Windows platforms, this may return None or a mock.
        """
        if self._icon_instance is None:
            try:
                import pystray
                from PIL import Image
                from pathlib import Path
                
                # Validate icon file exists before attempting to load
                icon_file = Path(self.icon_path)
                if not icon_file.exists():
                    logger.error(f"Icon file not found: {self.icon_path}")
                    return None
                
                # Load icon image
                icon_image = Image.open(self.icon_path)
                
                # Create icon
                self._icon_instance = pystray.Icon(
                    "LAgent",
                    icon=icon_image,
                    menu=self._build_pystray_menu()
                )
                logger.debug("Pystray icon instance created")
            except ImportError:
                logger.warning("pystray not installed, tray will not be functional")
                return None
            except Exception as e:
                logger.error(f"Failed to create tray icon: {e}")
                return None
        
        return self._icon_instance
    
    def _build_pystray_menu(self):
        """Build pystray Menu structure from our Menu with current state."""
        try:
            import pystray
        except ImportError:
            return None
        
        # Start Session submenu
        start_fishing = pystray.MenuItem(
            "Fishing",
            self._create_mode_callback("Fishing")
        )
        start_combat = pystray.MenuItem(
            "Combat",
            self._create_mode_callback("Combat")
        )
        start_shadow = pystray.MenuItem(
            "Shadow",
            self._create_mode_callback("Shadow")
        )
        start_session_submenu = pystray.MenuItem(
            "Start Session",
            pystray.Menu(start_fishing, start_combat, start_shadow)
        )
        
        # Main menu items with dynamic labels reflecting current toggle states
        stop_session = pystray.MenuItem(
            "Stop Session",
            self._create_callback(lambda: self.menu.stop_session.invoke())
        )
        recording_status = "ON" if self.menu.state.recording_mode_active else "OFF"
        recording_toggle = pystray.MenuItem(
            f"Recording Mode: {recording_status}",
            self._create_callback(lambda: self._invoke_recording_toggle())
        )
        overlay_status = "ON" if self.menu.state.status_overlay_active else "OFF"
        overlay_toggle = pystray.MenuItem(
            f"Status Overlay: {overlay_status}",
            self._create_callback(lambda: self._invoke_overlay_toggle())
        )
        exit_item = pystray.MenuItem(
            "Exit",
            self._create_callback(lambda: self.menu.exit.invoke())
        )
        
        return pystray.Menu(
            start_session_submenu,
            stop_session,
            pystray.Menu.SEPARATOR,
            recording_toggle,
            overlay_toggle,
            pystray.Menu.SEPARATOR,
            exit_item,
        )
    
    def _create_mode_callback(self, mode_name: str):
        """Create callback for a session mode."""
        def callback(icon, item):
            self.menu.start_session.on_mode_selected(mode_name)
        return callback
    
    def _create_callback(self, func: Callable):
        """Create pystray-compatible callback wrapper."""
        def callback(icon, item):
            func()
        return callback
    
    def _invoke_recording_toggle(self) -> None:
        """Toggle recording mode and refresh menu display."""
        self.menu.recording_mode_toggle.invoke()
        self._refresh_pystray_menu()

    def update_state(self, state: UIState, now=None) -> None:
        """Update icon accessibility text and menu from the canonical state."""
        self.state = state
        self.menu.apply_state(state)
        self._base_tooltip = format_tooltip(state, now)
        self.tooltip = self._base_tooltip
        self.icon_state = {
            SessionState.IDLE: "idle",
            SessionState.STARTING: "active",
            SessionState.RUNNING: "active",
            SessionState.RECORDING: "recording",
            SessionState.STOPPING: "active",
            SessionState.HALTED: "halted",
            SessionState.UNKNOWN: "unknown",
        }[state.status]
        if self._icon_instance is not None:
            self._icon_instance.title = self.tooltip
            self._refresh_pystray_menu()

    def update_quest_status(self, snapshot: QuestSnapshot) -> str:
        """Append the read-only quest projection to the tray tooltip."""

        summary = format_quest_summary(snapshot)
        self.tooltip = f"{self._base_tooltip} | {summary}" if summary else self._base_tooltip
        if self._icon_instance is not None:
            self._icon_instance.title = self.tooltip
        return self.tooltip
    
    def _invoke_overlay_toggle(self) -> None:
        """Toggle overlay mode and refresh menu display."""
        self.menu.status_overlay_toggle.callback and self.menu.status_overlay_toggle.callback()
        self._refresh_pystray_menu()
    
    def _refresh_pystray_menu(self) -> None:
        """
        Refresh the pystray menu to reflect updated toggle states.
        
        Called after toggle operations to update menu labels dynamically.
        """
        if self._icon_instance is None:
            return
        
        try:
            # Rebuild menu with current state and update icon
            new_menu = self._build_pystray_menu()
            if new_menu:
                self._icon_instance.menu = new_menu
                logger.debug("Pystray menu refreshed with updated toggle states")
        except Exception as e:
            logger.error(f"Failed to refresh pystray menu: {e}")
    
    def show(self) -> None:
        """Show the tray icon (blocking call)."""
        icon = self.get_icon_instance()
        if icon:
            logger.info("Showing tray icon")
            icon.run()

    def show_detached(self) -> None:
        """Show the tray icon without taking ownership of the event loop."""
        icon = self.get_icon_instance()
        if icon:
            logger.info("Showing tray icon in detached mode")
            icon.run_detached()
    
    def hide(self) -> None:
        """Hide the tray icon."""
        if self._icon_instance:
            logger.info("Hiding tray icon")
            self._icon_instance.stop()
