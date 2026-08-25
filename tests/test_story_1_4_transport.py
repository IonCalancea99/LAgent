import logging
import threading
import time

from lagent.agent.party_bus import PartyBus
from lagent.common.transport import (
    AgentTransport,
    MessageType,
    make_endpoint,
)
from lagent.gpu_server.server import GpuInferenceServer
from lagent.orchestrator.heartbeat import HeartbeatMonitor


def test_gpu_routes_stub_result_to_originating_agent():
    server_endpoint = make_endpoint()
    server = GpuInferenceServer(server_endpoint)
    thread = threading.Thread(target=server.serve, daemon=True)
    thread.start()
    time.sleep(0.03)

    clients = [
        AgentTransport("warlord", server_endpoint),
        AgentTransport("prophet", server_endpoint),
    ]
    try:
        for client in clients:
            client.connect()
        results = [
            client.request_inference(b"frame", {"hp": b"roi"}, timeout=1.0)
            for client in clients
        ]
        assert [result.agent_id for result in results] == ["warlord", "prophet"]
        assert all(result.result.detections == [] for result in results)
        assert all(result.result.ocr_values == {} for result in results)
        assert all(result.latency_ms < 50 for result in results)
    finally:
        for client in clients:
            client.close()
        server.stop()
        thread.join(timeout=1)


def test_party_state_and_heartbeat_reach_peer_and_orchestrator():
    warlord = PartyBus("warlord", make_endpoint())
    prophet = PartyBus("prophet", make_endpoint())
    orchestrator = PartyBus("orchestrator", None)
    try:
        warlord.start_publisher()
        prophet.start_publisher()
        prophet.subscribe(prophet.publisher_endpoint)
        prophet.subscribe(warlord.publisher_endpoint)
        orchestrator.subscribe(warlord.publisher_endpoint)
        orchestrator.subscribe(prophet.publisher_endpoint)
        time.sleep(0.05)

        warlord.publish_state({"fsm_state": "PULLING"})
        warlord.publish_heartbeat()
        assert prophet.receive(timeout=1.0)["agent_id"] == "warlord"
        assert orchestrator.receive(timeout=1.0)["type"] == MessageType.PARTY_STATE
        assert orchestrator.receive(timeout=1.0)["type"] == MessageType.HEARTBEAT
    finally:
        warlord.close()
        prophet.close()
        orchestrator.close()


def test_monitor_logs_after_configured_missed_interval(caplog):
    monitor = HeartbeatMonitor(("warlord",), interval=0.02, missed_count=2)
    monitor.observe("warlord", time.time())
    with caplog.at_level(logging.WARNING):
        time.sleep(0.05)
        warnings = monitor.check()
    assert warnings == ["warlord"]
    assert "heartbeat missed" in caplog.text
