"""Orchestrator process entry point."""

import logging
import uuid
from pathlib import Path

from lagent.common.sessions_db import SessionsDB


def main():
    """
    Initialize orchestrator and log session lifecycle events.
    
    The orchestrator:
    1. Creates a session in the shared sessions.db
    2. Logs startup event
    3. Manages session lifecycle for connected agents
    """
    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    
    logger.info("Orchestrator starting")
    
    # Initialize sessions database
    db_path = Path("data") / "sessions.db"
    try:
        db = SessionsDB(str(db_path))
        
        # Create orchestrator session
        session_id = f"orchestrator-{uuid.uuid4().hex[:8]}"
        
        # Log orchestrator session start
        db.log_session_start(
            session_id=session_id,
            profile="orchestrator",
            mode="autonomous"
        )
        logger.info("Orchestrator session started: %s", session_id)
        
        # Log startup event
        db.append_event(
            session_id=session_id,
            source="orchestrator",
            type="startup",
            payload={
                "component": "orchestrator",
                "status": "initialized",
                "session_id": session_id
            }
        )
        
        # Log that orchestrator is ready
        db.log_state_transition(
            session_id=session_id,
            source="orchestrator",
            from_state="initializing",
            to_state="ready",
            reason="Bootstrap complete"
        )
        
        db.close()
        logger.info("Orchestrator ready")
        
    except Exception as e:
        logger.error("Failed to initialize orchestrator sessions database: %s", e)
        raise


if __name__ == "__main__":
    main()
