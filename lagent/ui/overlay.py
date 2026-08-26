"""Compact, click-through status overlay for the two runtime agents."""

from typing import Optional

from lagent.ui.telemetry import AgentSnapshot, TelemetryReader

try:
    from PyQt6.QtCore import Qt, QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
    from PyQt6.QtWidgets import QApplication, QGridLayout, QLabel, QProgressBar, QWidget
except ImportError:
    QApplication = None


def native_overlay_flags():
    """Keep platform-specific window flags isolated for headless tests."""
    if QApplication is None:
        return None
    return (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.BypassWindowManagerHint)


if QApplication is not None:
    class _TelemetrySignals(QObject):
        completed = pyqtSignal(object, object)


    class _TelemetryTask(QRunnable):
        def __init__(self, reader, session_id, signals):
            super().__init__()
            self.reader = reader
            self.session_id = session_id
            self.signals = signals

        def run(self):
            try:
                snapshots = self.reader.read(self.session_id)
                self.signals.completed.emit(self.session_id, snapshots)
            except Exception:
                self.signals.completed.emit(self.session_id, {})


    class AgentRow(QWidget):
        def __init__(self, name: str, parent=None):
            super().__init__(parent)
            self.name_label = QLabel(name)
            self.state_label = QLabel("Stopped")
            self.hp_label = QLabel("HP --")
            self.mp_label = QLabel("MP --")
            self.elapsed_label = QLabel("--:--:--")
            self.hp_bar = QProgressBar()
            self.mp_bar = QProgressBar()
            for bar in (self.hp_bar, self.mp_bar):
                bar.setRange(0, 100)
                bar.setTextVisible(False)
            layout = QGridLayout(self)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.addWidget(self.name_label, 0, 0)
            layout.addWidget(self.state_label, 0, 1)
            layout.addWidget(self.elapsed_label, 0, 2)
            layout.addWidget(self.hp_label, 1, 0)
            layout.addWidget(self.hp_bar, 1, 1, 1, 2)
            layout.addWidget(self.mp_label, 2, 0)
            layout.addWidget(self.mp_bar, 2, 1, 1, 2)

        def update_snapshot(self, snapshot: AgentSnapshot):
            self.state_label.setText(snapshot.state + (" (stale)" if snapshot.stale else ""))
            self.hp_label.setText(f"HP {snapshot.hp_percent:.0f}" if snapshot.hp_percent is not None else "HP --")
            self.mp_label.setText(f"MP {snapshot.mp_percent:.0f}" if snapshot.mp_percent is not None else "MP --")
            self.elapsed_label.setText(snapshot.elapsed)
            self.hp_bar.setValue(int(snapshot.hp_percent or 0))
            self.mp_bar.setValue(int(snapshot.mp_percent or 0))


    class StatusOverlay(QWidget):
        def __init__(self, db_path: str, session_id: Optional[str] = None, parent=None):
            super().__init__(parent)
            self.reader = TelemetryReader(db_path)
            self.session_id = session_id
            self.rows = {name: AgentRow(name, self) for name in ("WL", "PP")}
            layout = QGridLayout(self)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.addWidget(self.rows["WL"], 0, 0)
            layout.addWidget(self.rows["PP"], 1, 0)
            self.setWindowFlags(native_overlay_flags())
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.setFixedSize(300, 160)
            self.timer = QTimer(self)
            self.timer.setInterval(500)
            self.timer.timeout.connect(self.refresh)
            self._telemetry_pool = QThreadPool.globalInstance()
            self._telemetry_signals = _TelemetrySignals()
            self._telemetry_signals.completed.connect(self._apply_snapshots)
            self._poll_in_flight = False

        def refresh(self):
            if self._poll_in_flight:
                return
            self._poll_in_flight = True
            task = _TelemetryTask(self.reader, self.session_id, self._telemetry_signals)
            self._telemetry_pool.start(task)

        def _apply_snapshots(self, session_id, snapshots):
            self._poll_in_flight = False
            if session_id != self.session_id:
                return
            for name, snapshot in snapshots.items():
                self.rows[name].update_snapshot(snapshot)

        def show_overlay(self):
            self.refresh()
            self.show()
            self.timer.start()

        def closeEvent(self, event):
            self.timer.stop()
            self.timer.deleteLater()
            super().closeEvent(event)

else:
    class AgentRow:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyQt6 is required to create the status overlay")

    class StatusOverlay:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyQt6 is required to create the status overlay")