"""lagent.orchestrator - Process orchestration and coordination."""

from lagent.orchestrator.heartbeat import HeartbeatMonitor


def main() -> None:
    # Imported lazily so the console script does not pull agent/ZeroMQ deps at package import.
    from lagent.orchestrator.__main__ import main as _main

    _main()


__all__ = ["HeartbeatMonitor", "main"]
