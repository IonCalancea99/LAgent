"""Platform notification adapter with a headless test-friendly default."""

import logging
import subprocess
import sys
from typing import List, Tuple

logger = logging.getLogger(__name__)


class NotificationAdapter:
    """Send operator notifications without making the tray depend on Windows APIs."""

    def __init__(self, sender=None):
        self.sent: List[Tuple[str, str]] = []
        self._halt_events = set()
        self._sender = sender

    def notify_halted(self, session_id: str, event_id: str) -> None:
        key = (session_id, event_id)
        if key in self._halt_events:
            return
        self._halt_events.add(key)
        title = "Session halted - check status overlay"
        self.sent.append((title, session_id))
        try:
            if self._sender is not None:
                self._sender(title, session_id)
            elif sys.platform == "win32":
                script = (
                    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]; "
                    "$xml = [Windows.Data.Xml.Dom.XmlDocument]::new(); "
                    "$xml.LoadXml('<toast><visual><binding template=\"ToastText02\"><text>"
                    + title
                    + "</text><text>Session "
                    + str(session_id)
                    + "</text></binding></visual></toast>'); "
                    "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
                    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('LAgent').Show($toast)"
                )
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
            else:
                logger.info("%s (%s)", title, session_id)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Notification delivery failed: %s", exc)
