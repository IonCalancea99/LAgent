"""
Shared SQLite database bootstrap and sessions/events logging for LAgent.

Story 1.3: Session Database - WAL-mode SQLite Setup

Architecture Compliance:
- AD-9: Single shared data/sessions.db with one connection per process
- Logging convention: JSON-structured events
- WAL mode for concurrent access without exclusive locks
"""

import sqlite3
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel

# Module logger
logger = logging.getLogger(__name__)


class SessionJSONEncoder(json.JSONEncoder):
    """Serialize common Python data types into SQLite-friendly JSON."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, (bytes, bytearray)):
            return bytes(obj).decode("utf-8", errors="replace")
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        return super().default(obj)


def create_db_bootstrap(db_path: str) -> sqlite3.Connection:
    """
    Bootstrap SQLite database with WAL mode and schema.
    
    This function:
    1. Creates the database file if it doesn't exist
    2. Enables WAL (Write-Ahead Logging) journal mode for concurrent access
    3. Sets write-safe pragmas
    4. Creates sessions and events tables idempotently
    
    Args:
        db_path: Path to the SQLite database file (e.g., "data/sessions.db")
    
    Returns:
        sqlite3.Connection: Open database connection ready for operations
    
    Raises:
        sqlite3.DatabaseError: If database initialization fails
        OSError: If directory creation fails
    """
    # Ensure parent directory exists
    db_file = Path(db_path)
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create database directory {db_file.parent}: {e}")
        raise
    
    # Open connection with appropriate timeout
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
    except sqlite3.DatabaseError as e:
        logger.error(f"Failed to open database {db_path}: {e}")
        raise
    
    try:
        # Enable WAL mode for concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        
        # Set write-safe pragmas
        conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and performance
        conn.execute("PRAGMA cache_size=10000")     # Improve cache efficiency
        conn.execute("PRAGMA temp_store=MEMORY")    # Use memory for temp tables
        conn.execute("PRAGMA busy_timeout=5000")    # 5 second timeout for locks
        
        # Create tables idempotently (IF NOT EXISTS)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                profile TEXT NOT NULL,
                mode TEXT NOT NULL,
                ended_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migrate existing databases: add ended_at column if it doesn't exist
        cursor = conn.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in cursor.fetchall()}
        if 'ended_at' not in columns:
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN ended_at TEXT")
                conn.commit()
                logger.info("Migrated sessions table: added ended_at column")
            except sqlite3.OperationalError:
                # Column may already exist or migration may have already run
                pass
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                source TEXT NOT NULL,
                type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        # Create index on session_id for faster queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session_id 
            ON events(session_id)
        """)
        
        conn.commit()
        logger.debug(f"Database bootstrap complete: {db_path}")
        
    except sqlite3.DatabaseError as e:
        logger.error(f"Failed to initialize database schema: {e}")
        conn.close()
        raise
    
    return conn


class SessionsDB:
    """
    High-level interface for logging sessions and events to SQLite.
    
    Thread-safe for concurrent writes from separate connections (per AD-9).
    Each process should maintain its own SessionsDB instance.
    
    Usage:
        db = SessionsDB("data/sessions.db")
        db.log_session_start("session-123", profile="prophet", mode="active")
        db.append_event("session-123", source="agent", type="startup", payload={...})
        db.close()
    
    Context Manager:
        with SessionsDB("data/sessions.db") as db:
            db.log_session_start(...)
            db.append_event(...)
    """
    
    def __init__(self, db_path: str):
        """
        Initialize SessionsDB connection.
        
        Args:
            db_path: Path to the SQLite database file
        
        Raises:
            sqlite3.DatabaseError: If database initialization fails
        """
        self.path = db_path
        try:
            self.conn = create_db_bootstrap(db_path)
            logger.debug(f"SessionsDB initialized: {db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SessionsDB: {e}")
            raise
    
    def log_session_start(
        self,
        session_id: str,
        profile: str,
        mode: str
    ) -> None:
        """
        Log a session start event to the sessions table.
        
        Creates a record with the current timestamp.
        
        Args:
            session_id: Unique session identifier
            profile: Agent profile (e.g., "prophet", "warlord")
            mode: Execution mode (e.g., "active", "autonomous", "shadow")
        
        Raises:
            sqlite3.IntegrityError: If session_id already exists
            sqlite3.OperationalError: If database operation fails
        """
        started_at = datetime.now().isoformat()
        
        try:
            self.conn.execute(
                """
                INSERT INTO sessions (session_id, started_at, profile, mode)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, started_at, profile, mode)
            )
            self.conn.commit()
            logger.debug(f"Session started: {session_id} (profile={profile}, mode={mode})")
            
        except sqlite3.IntegrityError as e:
            logger.error(f"Session already exists: {session_id}")
            raise
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to log session start: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return a single session row as a dictionary."""
        row = self.conn.execute(
            "SELECT session_id, started_at, profile, mode, ended_at, created_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None

        columns = [
            "session_id",
            "started_at",
            "profile",
            "mode",
            "ended_at",
            "created_at",
        ]
        return {key: value for key, value in zip(columns, row)}

    def log_session_end(
        self,
        session_id: str,
        outcome: str = "clean"
    ) -> None:
        """
        Log a session end event by updating the ended_at timestamp.
        
        Args:
            session_id: Session ID
            outcome: "clean" or "forced" shutdown outcome
        
        Raises:
            sqlite3.OperationalError: If database operation fails
        """
        ended_at = datetime.now().isoformat()
        
        try:
            self.conn.execute(
                """
                UPDATE sessions 
                SET ended_at = ?
                WHERE session_id = ?
                """,
                (ended_at, session_id)
            )
            self.conn.commit()
            logger.debug(f"Session ended: {session_id} (outcome={outcome})")
            
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to log session end: {e}")
            raise

    def update_session_profile(self, session_id: str, profile: str) -> None:
        """Set the resolved profile on an existing session row."""
        try:
            self.conn.execute(
                """
                UPDATE sessions
                SET profile = ?
                WHERE session_id = ?
                """,
                (profile, session_id)
            )
            self.conn.commit()
            logger.debug(f"Session profile updated: {session_id} -> {profile}")

        except sqlite3.OperationalError as e:
            logger.error(f"Failed to update session profile: {e}")
            raise

    def get_events_by_type(
        self,
        session_id: str,
        event_type: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return events for a session filtered by type with parsed payload data."""
        rows = self.conn.execute(
            """
            SELECT id, session_id, ts, source, type, payload_json, created_at
            FROM events
            WHERE session_id = ? AND type = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, event_type, limit),
        ).fetchall()

        items: List[Dict[str, Any]] = []
        for row in rows:
            event_id, session_row_id, ts, source, type_name, payload_json, created_at = row
            items.append(
                {
                    "id": event_id,
                    "session_id": session_row_id,
                    "ts": ts,
                    "source": source,
                    "type": type_name,
                    "payload": json.loads(payload_json),
                    "created_at": created_at,
                }
            )
        return items

    def get_all_events(self, session_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Return all events for a session with parsed payload data."""
        rows = self.conn.execute(
            """
            SELECT id, session_id, ts, source, type, payload_json, created_at
            FROM events
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()

        items: List[Dict[str, Any]] = []
        for row in rows:
            event_id, session_row_id, ts, source, type_name, payload_json, created_at = row
            items.append(
                {
                    "id": event_id,
                    "session_id": session_row_id,
                    "ts": ts,
                    "source": source,
                    "type": type_name,
                    "payload": json.loads(payload_json),
                    "created_at": created_at,
                }
            )
        return items

    def append_event(
        self,
        session_id: str,
        source: str,
        type: str,
        payload: Dict[str, Any]
    ) -> int:
        """
        Append an event to the events table with JSON serialization.

        IMPORTANT: The session must be logged first via log_session_start().
        Events for non-existent sessions will fail with sqlite3.IntegrityError.

        Args:
            session_id: Session ID the event belongs to
            source: Event source (e.g., "agent", "orchestrator", "ui")
            type: Event type (e.g., "startup", "action", "error")
            payload: Event data as dictionary (will be JSON-serialized)

        Returns:
            int: Row ID of the inserted event

        Raises:
            sqlite3.IntegrityError: If the session does not exist
            sqlite3.InterfaceError: If payload is not JSON-serializable
            sqlite3.OperationalError: If database operation fails
        """
        ts = datetime.now().isoformat()

        try:
            payload_json = json.dumps(payload, cls=SessionJSONEncoder)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize event payload: {e}")
            raise sqlite3.InterfaceError(f"Payload not JSON-serializable: {e}")

        try:
            cursor = self.conn.execute(
                """
                INSERT INTO events (session_id, ts, source, type, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, ts, source, type, payload_json)
            )
            self.conn.commit()

            event_id = cursor.lastrowid
            logger.debug(f"Event appended: id={event_id}, session={session_id}, type={type}")

            return event_id

        except sqlite3.IntegrityError:
            logger.error(f"Event references non-existent session: {session_id}")
            raise
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to append event: {e}")
            raise
    
    def log_telemetry(
        self,
        session_id: str,
        source: str,
        metric_name: str,
        metric_value: Any,
        tags: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Log a telemetry metric as an event.
        
        Telemetry is stored as events with type="telemetry" and structured payload.
        
        Args:
            session_id: Session ID
            source: Source component (e.g., "agent.prophet", "orchestrator.heartbeat")
            metric_name: Name of the metric (e.g., "cpu_usage", "memory_mb")
            metric_value: Numeric or string value
            tags: Optional tags for filtering/aggregation
        
        Returns:
            int: Event ID
        """
        payload = {
            "metric_name": metric_name,
            "metric_value": metric_value,
            "tags": tags or {}
        }
        return self.append_event(session_id, source, "telemetry", payload)
    
    def log_state_transition(
        self,
        session_id: str,
        source: str,
        from_state: str,
        to_state: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Log a state transition event.
        
        Args:
            session_id: Session ID
            source: Source component
            from_state: Previous state
            to_state: New state
            reason: Reason for transition
            metadata: Optional additional data
        
        Returns:
            int: Event ID
        """
        payload = {
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "metadata": metadata or {}
        }
        return self.append_event(session_id, source, "state_transition", payload)
    
    def log_error(
        self,
        session_id: str,
        source: str,
        error_type: str,
        error_message: str,
        stacktrace: Optional[str] = None
    ) -> int:
        """
        Log an error event.
        
        Args:
            session_id: Session ID
            source: Source component
            error_type: Error class name
            error_message: Error message
            stacktrace: Optional stack trace
        
        Returns:
            int: Event ID
        """
        payload = {
            "error_type": error_type,
            "error_message": error_message,
            "stacktrace": stacktrace
        }
        return self.append_event(session_id, source, "error", payload)
    
    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            try:
                self.conn.close()
                logger.debug(f"SessionsDB closed: {self.path}")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

