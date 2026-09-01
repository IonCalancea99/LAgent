"""Agent Party Bus PUB/SUB client."""

import logging
import time
from typing import Any

from lagent.common import PartyState
from lagent.common.transport import (
    HEARTBEAT_INTERVAL,
    HEARTBEAT_MISSED_COUNT,
    MessageType,
    decode,
    encode,
)


class PartyBus:
    def __init__(
        self,
        agent_id: str,
        publisher_endpoint: str | None,
        context=None,
        session_db=None,
        session_id: str | None = None,
    ):
        import zmq

        self.agent_id = agent_id
        self.publisher_endpoint = publisher_endpoint
        self._owns_context = context is None
        self.context = context or zmq.Context()
        self.publisher = None
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b"")
        self._peer_party_state: PartyState | None = None
        self.peer_party_state_received_at: float | None = None
        self._peer_state_stale_logged = False
        self.logger = logging.getLogger(__name__)
        self.session_db = session_db
        self.session_id = session_id

    @property
    def peer_party_state(self) -> PartyState | None:
        return self._peer_party_state

    @peer_party_state.setter
    def peer_party_state(self, value: PartyState | None) -> None:
        raise AttributeError("peer_party_state is read-only")

    def start_publisher(self) -> None:
        import zmq

        if self.publisher_endpoint is None:
            raise ValueError("A publisher endpoint is required")
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind(self.publisher_endpoint)

    def subscribe(self, endpoint: str) -> None:
        self.subscriber.connect(endpoint)
        time.sleep(0.05)

    def publish_state(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise TypeError("Party state payload must be a dict")

        normalized = dict(state)
        normalized.setdefault("heartbeat_timestamp", time.time())
        snapshot = PartyState.model_validate(normalized)
        self._publish(MessageType.PARTY_STATE, snapshot.model_dump(mode="json"))

    def publish_heartbeat(self) -> None:
        self._publish(MessageType.HEARTBEAT, {"heartbeat_timestamp": time.time()})

    def publish_control(self, message_type: MessageType, payload: dict[str, Any]) -> None:
        if message_type not in (MessageType.SESSION_HALT, MessageType.SESSION_RESUME):
            raise ValueError("Only session halt and resume messages are control messages")
        self._publish(message_type, payload)

    def handle_control(self, message: dict[str, Any], agent_loop: Any) -> bool:
        message_type = message.get("type")
        payload = message.get("payload") or {}
        if message_type == MessageType.SESSION_HALT:
            if payload.get("session_id") != agent_loop.session_id:
                return False
            agent_loop.request_session_halt(payload.get("missed_agent_id", "unknown"), payload.get("missed_count", 0))
            return True
        if message_type == MessageType.SESSION_RESUME:
            agent_ids = payload.get("agent_ids")
            if (
                payload.get("session_id") != agent_loop.session_id
                or payload.get("reason") != "operator_resume"
                or not isinstance(agent_ids, list)
                or self.agent_id not in agent_ids
            ):
                return False
            return agent_loop.request_resume()
        return False

    def _publish(self, message_type: MessageType, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            raise RuntimeError("Publisher has not started")
        self.publisher.send(encode({"agent_id": self.agent_id, "type": message_type, "payload": payload}))

    def _apply_peer_state(self, message: dict[str, Any]) -> None:
        if message.get("type") != MessageType.PARTY_STATE:
            return
        payload = message.get("payload") or {}
        try:
            snapshot = PartyState.model_validate(payload)
        except Exception as exc:  # pragma: no cover - defensive guard against malformed peer snapshots
            self.logger.warning(
                "party_bus_invalid_snapshot: agent_id=%s; peer_agent_id=%s; reason=%s; payload=%s",
                self.agent_id,
                message.get("agent_id"),
                exc,
                payload,
            )
            return

        self._peer_party_state = snapshot
        self.peer_party_state_received_at = time.time()
        self._peer_state_stale_logged = False

    def is_peer_state_stale(self, now: float | None = None) -> bool:
        if self._peer_party_state is None or self.peer_party_state_received_at is None:
            return True
        threshold = HEARTBEAT_INTERVAL * HEARTBEAT_MISSED_COUNT
        now = now if now is not None else time.time()
        stale = (now - self.peer_party_state_received_at) >= threshold
        if stale and not self._peer_state_stale_logged:
            payload = {
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "reason": "peer_state_stale",
                "last_valid_snapshot_received_at": self.peer_party_state_received_at,
                "threshold_seconds": threshold,
                "fsm_state": self._peer_party_state.fsm_state,
            }
            self.logger.warning(
                "party_bus_disconnected: agent_id=%s; last_valid_snapshot_received_at=%s; threshold_seconds=%s",
                self.agent_id,
                self.peer_party_state_received_at,
                threshold,
            )
            if self.session_db is not None and self.session_id is not None:
                try:
                    self.session_db.append_event(self.session_id, "party_bus", "party_bus_disconnected", payload)
                except Exception:
                    self.logger.exception("Failed to append party_bus_disconnected event for %s", self.session_id)
            self._peer_state_stale_logged = True
        return stale

    def receive(self, timeout: float = 0.05) -> dict[str, Any]:
        if self.subscriber.poll(int(timeout * 1000)) == 0:
            raise TimeoutError("No Party Bus message received")
        message = decode(self.subscriber.recv())
        self._apply_peer_state(message)
        return message

    def close(self) -> None:
        if self.publisher is not None:
            self.publisher.close(linger=0)
        self.subscriber.close(linger=0)
        if self._owns_context:
            self.context.term()