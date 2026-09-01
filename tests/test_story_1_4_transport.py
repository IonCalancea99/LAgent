import logging
import sys
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


def _receive_with_context(bus, *, receiver, expected_message):
    try:
        return bus.receive(timeout=1.0)
    except TimeoutError as exc:
        raise AssertionError(
            f"{receiver} timed out waiting for {expected_message}"
        ) from exc


def _cleanup_server(clients, server, thread, server_errors):
    cleanup_errors = []
    for agent_id, client in clients.items():
        try:
            client.close()
        except Exception as exc:
            exc.add_note(f"Failed to close {agent_id} transport")
            cleanup_errors.append(exc)
    try:
        server.stop()
    except Exception as exc:
        exc.add_note("Failed to stop GPU server")
        cleanup_errors.append(exc)
    thread.join(timeout=1.0)
    if thread.is_alive():
        cleanup_errors.append(
            AssertionError("GPU server thread did not terminate after bounded join")
        )
    for error in server_errors:
        error.add_note("GPU server thread failed")
        cleanup_errors.append(error)

    primary_error = sys.exception()
    if primary_error is not None:
        for error in cleanup_errors:
            primary_error.add_note(f"Cleanup failure: {error!r}")
    elif cleanup_errors:
        raise ExceptionGroup("Transport cleanup failed", cleanup_errors)


def test_gpu_routes_stub_result_to_originating_agent():
    server_endpoint = make_endpoint()
    server = GpuInferenceServer(server_endpoint)
    server_errors = []

    def serve():
        try:
            server.serve()
        except Exception as exc:
            server_errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    time.sleep(0.03)

    clients = {
        agent_id: AgentTransport(agent_id, server_endpoint)
        for agent_id in ("warlord", "prophet")
    }
    try:
        for client in clients.values():
            client.connect()
        results = {}
        errors = {}
        request_timeout = 1.0
        start_barrier = threading.Barrier(len(clients))

        def request(agent_id):
            try:
                start_barrier.wait(timeout=1.0)
                results[agent_id] = clients[agent_id].request_inference(
                    b"frame", {"hp": b"roi"}, timeout=request_timeout
                )
            except Exception as exc:
                errors[agent_id] = exc

        request_threads = {
            agent_id: threading.Thread(
                target=request,
                args=(agent_id,),
                daemon=True,
            )
            for agent_id in clients
        }
        for request_thread in request_threads.values():
            request_thread.start()
        for request_thread in request_threads.values():
            request_thread.join(timeout=request_timeout + 0.5)

        request_failures = []
        for agent_id, request_thread in request_threads.items():
            if request_thread.is_alive():
                request_failures.append(
                    AssertionError(
                        f"{agent_id} request thread did not terminate after bounded join"
                    )
                )
            if agent_id in errors:
                errors[agent_id].add_note(f"{agent_id} inference request failed")
                request_failures.append(errors[agent_id])
        if request_failures:
            raise ExceptionGroup("Inference requests failed", request_failures)

        for agent_id in clients:
            assert agent_id in results, f"{agent_id} inference request produced no result"
            result = results[agent_id]
            assert result.agent_id == agent_id, (
                f"{agent_id} received response for {result.agent_id}"
            )
            assert result.result.detections == [], (
                f"{agent_id} received unexpected detections: {result.result.detections!r}"
            )
            assert result.result.ocr_values == {}, (
                f"{agent_id} received unexpected OCR values: {result.result.ocr_values!r}"
            )
            assert result.latency_ms < 50, (
                f"{agent_id} inference latency {result.latency_ms}ms exceeded 50ms"
            )
    finally:
        _cleanup_server(clients, server, thread, server_errors)


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
        assert _receive_with_context(
            prophet,
            receiver="prophet",
            expected_message="warlord party state",
        )["agent_id"] == "warlord"
        assert _receive_with_context(
            orchestrator,
            receiver="orchestrator",
            expected_message="party state",
        )["type"] == MessageType.PARTY_STATE
        assert _receive_with_context(
            orchestrator,
            receiver="orchestrator",
            expected_message="heartbeat",
        )["type"] == MessageType.HEARTBEAT
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
        msg = _receive_with_context(
            prophet,
            receiver="prophet",
            expected_message="warlord party state snapshot",
        )
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
        first_msg = _receive_with_context(
            prophet,
            receiver="prophet",
            expected_message="first warlord party state snapshot",
        )
        second_msg = _receive_with_context(
            prophet,
            receiver="prophet",
            expected_message="second warlord party state snapshot",
        )
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
