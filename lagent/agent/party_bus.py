"""Agent Party Bus PUB/SUB client."""

import time
from typing import Any

from lagent.common.transport import MessageType, decode, encode


class PartyBus:
    def __init__(self, agent_id: str, publisher_endpoint: str | None, context=None):
        import zmq

        self.agent_id = agent_id
        self.publisher_endpoint = publisher_endpoint
        self._owns_context = context is None
        self.context = context or zmq.Context()
        self.publisher = None
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b"")

    def start_publisher(self) -> None:
        import zmq

        if self.publisher_endpoint is None:
            raise ValueError("A publisher endpoint is required")
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind(self.publisher_endpoint)

    def subscribe(self, endpoint: str) -> None:
        self.subscriber.connect(endpoint)

    def publish_state(self, state: dict[str, Any]) -> None:
        self._publish(MessageType.PARTY_STATE, state)

    def publish_heartbeat(self) -> None:
        self._publish(MessageType.HEARTBEAT, {"heartbeat_timestamp": time.time()})

    def _publish(self, message_type: MessageType, payload: dict[str, Any]) -> None:
        if self.publisher is None:
            raise RuntimeError("Publisher has not started")
        self.publisher.send(encode({"agent_id": self.agent_id, "type": message_type, "payload": payload}))

    def receive(self, timeout: float = 0.05) -> dict[str, Any]:
        if self.subscriber.poll(int(timeout * 1000)) == 0:
            raise TimeoutError("No Party Bus message received")
        return decode(self.subscriber.recv())

    def close(self) -> None:
        if self.publisher is not None:
            self.publisher.close(linger=0)
        self.subscriber.close(linger=0)
        if self._owns_context:
            self.context.term()