"""Stub GPU inference server using the fixed DEALER/ROUTER contract."""

import threading

from lagent.common import PerceptionResult
from lagent.common.transport import GPU_ENDPOINT, decode, encode


class GpuInferenceServer:
    def __init__(self, endpoint: str = GPU_ENDPOINT, context=None):
        import zmq

        self._owns_context = context is None
        self.context = context or zmq.Context()
        self.endpoint = endpoint
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(endpoint)
        self._stopped = threading.Event()

    def serve(self, once: bool = False) -> None:
        import zmq

        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        try:
            while not self._stopped.is_set():
                for _, _ in poller.poll(50):
                    identity, payload = self.socket.recv_multipart()
                    request = decode(payload)
                    self.socket.send_multipart([identity, encode({
                        "agent_id": request["agent_id"],
                        "result": PerceptionResult().model_dump(mode="json"),
                    })])
                    if once:
                        return
        finally:
            self.socket.close(linger=0)
            if self._owns_context:
                self.context.term()

    def stop(self) -> None:
        self._stopped.set()