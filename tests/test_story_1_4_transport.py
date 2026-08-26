import logging
import threading
import time

from lagent.agent.party_bus import PartyBus
from lagent.common import GameState, PartyState
from lagent.common.transport import (
    AgentTransport,
    MessageType,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_MISSED_COUNT,
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


def test_party_bus_tracks_peer_party_state_snapshot_and_stale_state():
    warlord = PartyBus("warlord", make_endpoint())
    prophet = PartyBus("prophet", make_endpoint())
    try:
        warlord.start_publisher()
        prophet.start_publisher()
        prophet.subscribe(warlord.publisher_endpoint)

        warlord.publish_state(
            {
                "fsm_state": "PULLING",
                "hp_percent": 88.0,
                "mp_percent": 60.0,
                "position": (100, 200),
                "buff_presence": {"haste": True},
                "heartbeat_timestamp": time.time(),
            }
        )
        msg = prophet.receive(timeout=1.0)
        assert msg["type"] == MessageType.PARTY_STATE
        assert isinstance(prophet.peer_party_state, PartyState)
        assert prophet.peer_party_state.fsm_state == "PULLING"
        assert prophet.peer_party_state.position == (100, 200)
        assert prophet.peer_party_state_received_at is not None
        assert prophet.is_peer_state_stale() is False

        game_state = GameState(
            hp_percent=85.0,
            mp_percent=50.0,
            active_buffs=["haste"],
            character_position=(50, 40),
            ui_mode="combat",
            peer_party_state=prophet.peer_party_state,
        )
        assert game_state.peer_party_state is not None
        assert game_state.peer_party_state.fsm_state == "PULLING"
        assert game_state.hp_percent == 85.0

        prophet.peer_party_state_received_at = time.time() - (HEARTBEAT_INTERVAL * HEARTBEAT_MISSED_COUNT) - 0.1
        assert prophet.is_peer_state_stale() is True
    finally:
        warlord.close()
        prophet.close()


def test_party_bus_uses_atomic_snapshot_replacement_and_read_only_peer_attribute():
    warlord = PartyBus("warlord", make_endpoint())
    prophet = PartyBus("prophet", make_endpoint())
    try:
        warlord.start_publisher()
        prophet.start_publisher()
        prophet.subscribe(warlord.publisher_endpoint)

        first = {
            "fsm_state": "IDLE",
            "hp_percent": 50.0,
            "mp_percent": 20.0,
            "position": (1, 2),
            "buff_presence": {"haste": False},
            "heartbeat_timestamp": time.time(),
        }
        second = {
            "fsm_state": "PULLING",
            "hp_percent": 75.0,
            "mp_percent": 30.0,
            "position": (3, 4),
            "buff_presence": {"haste": True},
            "heartbeat_timestamp": time.time(),
        }

        warlord.publish_state(first)
        warlord.publish_state(second)
        first_msg = prophet.receive(timeout=1.0)
        second_msg = prophet.receive(timeout=1.0)
        assert first_msg["type"] == MessageType.PARTY_STATE
        assert second_msg["type"] == MessageType.PARTY_STATE
        assert prophet.peer_party_state.fsm_state == "PULLING"
        assert prophet.peer_party_state.position == (3, 4)
        assert prophet.peer_party_state.buff_presence["haste"] is True

        try:
            prophet.peer_party_state = PartyState(
                fsm_state="FIGHTING",
                hp_percent=99.0,
                mp_percent=99.0,
                position=(9, 9),
                buff_presence={},
                heartbeat_timestamp=time.time(),
            )
            raise AssertionError("peer_party_state should be read-only")
        except AttributeError:
            pass
    finally:
        warlord.close()
        prophet.close()
