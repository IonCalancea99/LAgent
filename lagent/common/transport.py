"""Shared ZeroMQ endpoint and message-envelope contracts."""

import base64
import json
import socket
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from lagent.common import PerceptionResult

GPU_ENDPOINT = "tcp://127.0.0.1:5555"
WARLORD_PARTY_ENDPOINT = "tcp://127.0.0.1:5556"
PROPHET_PARTY_ENDPOINT = "tcp://127.0.0.1:5557"
ORCHESTRATOR_CONTROL_ENDPOINT = "tcp://127.0.0.1:5558"
HEARTBEAT_INTERVAL = 1.0
HEARTBEAT_MISSED_COUNT = 3


class MessageType(StrEnum):
    PARTY_STATE = "party_state"
    HEARTBEAT = "heartbeat"
    SESSION_HALT = "session_halt"
    SESSION_RESUME = "session_resume"


def make_endpoint() -> str:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return f"tcp://127.0.0.1:{probe.getsockname()[1]}"


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(_json_value(message), separators=(",", ":")).encode("utf-8")


def decode(payload: bytes) -> dict[str, Any]:
    def restore(value: Any) -> Any:
        if isinstance(value, dict) and set(value) == {"__bytes__"}:
            return base64.b64decode(value["__bytes__"])
        if isinstance(value, dict):
            return {key: restore(item) for key, item in value.items()}
        if isinstance(value, list):
            return [restore(item) for item in value]
        return value

    return restore(json.loads(payload.decode("utf-8")))


@dataclass(frozen=True)
class InferenceResponse:
    agent_id: str
    result: PerceptionResult
    latency_ms: float


class AgentTransport:
    def __init__(self, agent_id: str, endpoint: str = GPU_ENDPOINT, context=None):
        import zmq

        self.agent_id = agent_id
        self.endpoint = endpoint
        self._owns_context = context is None
        self.context = context or zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt_string(zmq.IDENTITY, agent_id)

    def connect(self) -> None:
        self.socket.connect(self.endpoint)

    def request_inference(self, frame_bytes: bytes, roi_map: dict[str, Any], timeout: float = 0.05) -> InferenceResponse:
        started = time.perf_counter()
        self.socket.send(encode({"agent_id": self.agent_id, "frame_bytes": frame_bytes, "roi_map": roi_map}))
        if self.socket.poll(int(timeout * 1000)) == 0:
            raise TimeoutError(f"No inference response for {self.agent_id}")
        response = decode(self.socket.recv())
        return InferenceResponse(
            agent_id=response["agent_id"],
            result=PerceptionResult.model_validate(response["result"]),
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    def close(self) -> None:
        self.socket.close(linger=0)
        if self._owns_context:
            self.context.term()