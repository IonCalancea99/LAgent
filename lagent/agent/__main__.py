"""Agent process entry point."""

import argparse
import logging
import uuid
from pathlib import Path

from lagent.agent.profile import load_profile
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
            mode="active"
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
                "status": "initialized"
            }
        )
        
        db.close()
        
    except Exception as e:
        logger.error("Failed to initialize sessions database: %s", e)
        raise


if __name__ == "__main__":
    main()
