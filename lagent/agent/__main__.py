"""Agent process entry point."""

import argparse
import logging
import time
import uuid
from pathlib import Path

from lagent.agent.capture import CaptureThread
from lagent.agent.inference import InferenceClient, PolicyQueue
from lagent.agent.profile import load_profile
from lagent.common.transport import GPU_ENDPOINT
from lagent.common.sessions_db import SessionsDB


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a LAgent agent")
    parser.add_argument(
        "--class",
        dest="profile_class",
        default="warlord",
        choices=("warlord", "prophet"),
    )
    parser.add_argument(
        "--session-id",
        dest="session_id",
        default=None,
        help="Session ID (auto-generated if not provided)",
    )
    parser.add_argument("--debug", action="store_true", help="Run the live capture and inference debug pipeline")
    parser.add_argument("--shadow", action="store_true", help="Shape and log actions without sending OS input")
    parser.add_argument("--window-title", default="Lineage II", help="Game window title to capture")
    parser.add_argument("--gpu-endpoint", default=GPU_ENDPOINT, help="GPU inference server endpoint")
    parser.add_argument("--fps", type=int, default=10, help="Capture and inference rate")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    # Load profile
    profile = load_profile(args.profile_class)
    logger.info("Profile loaded: %s", profile.name)

    # Initialize sessions database
    db_path = Path("data") / "sessions.db"
    try:
        db = SessionsDB(str(db_path))
        
        # Generate or use provided session ID
        session_id = args.session_id or f"agent-{args.profile_class}-{uuid.uuid4().hex[:8]}"
        
        # Log session start
        db.log_session_start(
            session_id=session_id,
            profile=args.profile_class,
            mode="shadow" if args.shadow else "active"
        )
        logger.info("Session started: %s", session_id)
        
        # Log startup event
        db.append_event(
            session_id=session_id,
            source="agent",
            type="startup",
            payload={
                "profile": args.profile_class,
                "component": "agent",
                "status": "initialized",
                "mode": "shadow" if args.shadow else "active",
            }
        )
        
        db.close()

        if args.debug:
            capture = CaptureThread(args.window_title, fps=args.fps)
            policy_queue = PolicyQueue(maxsize=2)
            inference = InferenceClient(
                args.profile_class,
                capture.frame_queue,
                policy_queue,
                endpoint=args.gpu_endpoint,
                profile=profile,
                debug=True,
            )
            capture.start()
            inference.start()
            logger.info("Debug perception pipeline started for %s", args.window_title)
            try:
                while capture.is_alive() and inference.is_alive():
                    time.sleep(0.25)
            except KeyboardInterrupt:
                logger.info("Stopping debug perception pipeline")
            finally:
                capture.stop()
                inference.stop()
                capture.join(timeout=1.0)
                inference.join(timeout=1.0)
        
    except Exception as e:
        logger.error("Failed to initialize sessions database: %s", e)
        raise


if __name__ == "__main__":
    main()
