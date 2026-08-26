"""Orchestrator process entry point."""

import logging
import argparse
import uuid
from pathlib import Path

from lagent.common.sessions_db import SessionsDB
from lagent.agent.party_bus import PartyBus
from lagent.common.transport import (
    MessageType,
    ORCHESTRATOR_CONTROL_ENDPOINT,
    PROPHET_PARTY_ENDPOINT,
    WARLORD_PARTY_ENDPOINT,
)
from lagent.orchestrator.heartbeat import HeartbeatMonitor


def main():
    """
    Initialize orchestrator and log session lifecycle events.
    
    The orchestrator:
    1. Creates a session in the shared sessions.db
    2. Logs startup event
    3. Manages session lifecycle for connected agents
    """
    parser = argparse.ArgumentParser(description="Start the LAgent orchestrator")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    
    logger.info("Orchestrator starting")
    
    # Initialize sessions database
    db_path = Path("data") / "sessions.db"
    try:
        db = SessionsDB(str(db_path))
        
        # Create orchestrator session
        session_id = args.session_id or f"orchestrator-{uuid.uuid4().hex[:8]}"
        
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
        
        party_bus = PartyBus("orchestrator", ORCHESTRATOR_CONTROL_ENDPOINT, session_db=db, session_id=session_id)
        party_bus.start_publisher()
        party_bus.subscribe(WARLORD_PARTY_ENDPOINT)
        party_bus.subscribe(PROPHET_PARTY_ENDPOINT)
        monitor = HeartbeatMonitor(
            ("warlord", "prophet"),
            session_id=session_id,
            session_db=db,
            control_publisher=lambda control: party_bus.publish_control(
                MessageType(control["type"]), control["payload"]
            ),
        )
        logger.info("Orchestrator ready")
        try:
            while True:
                try:
                    monitor.observe_message(party_bus.receive(timeout=0.05))
                except TimeoutError:
                    pass
                monitor.check()
        except KeyboardInterrupt:
            logger.info("Stopping orchestrator")
        finally:
            party_bus.close()
            db.close()
        
    except Exception as e:
        logger.error("Failed to initialize orchestrator sessions database: %s", e)
        raise


if __name__ == "__main__":
    main()
