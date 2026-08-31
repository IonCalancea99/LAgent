"""GPU server process entry point."""

import argparse
import logging
import uuid
from pathlib import Path

from lagent.common.sessions_db import SessionsDB
from lagent.gpu_server.server import GpuInferenceServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the LAgent GPU inference server")
    parser.add_argument("--session-id", default=None, help="Session ID for correlated telemetry")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate command-line startup without opening the inference server",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    session_id = args.session_id or f"gpu-server-{uuid.uuid4().hex[:8]}"
    logger.info("GPU server starting for session %s", session_id)
    db = SessionsDB(str(Path("data") / "sessions.db"))
    if db.get_session(session_id) is None:
        db.log_session_start(session_id, profile="gpu_server", mode="service")
    db.append_event(session_id, "gpu_server", "startup", {"status": "initialized"})
    try:
        if args.check:
            return
        GpuInferenceServer(session_id=session_id, db=db).serve()
    finally:
        db.close()


if __name__ == "__main__":
    main()
