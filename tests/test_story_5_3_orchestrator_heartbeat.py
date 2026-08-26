from lagent.agent.fishing_fsm import FishingFSM
from lagent.agent.loop import AgentLoop
from lagent.agent.party_bus import PartyBus
from lagent.agent.capture import FrameQueue
from lagent.agent.inference import PolicyQueue
from lagent.common import PerceptionResult
from lagent.common.transport import MessageType
from lagent.hsl import HSL
from lagent.orchestrator.heartbeat import HeartbeatMonitor


class FakeDB:
    def __init__(self):
        self.events = []

    def append_event(self, session_id, source, event_type, payload):
        self.events.append((session_id, source, event_type, payload))


def test_party_bus_rejects_resume_for_another_session_or_agent():
    bus = PartyBus("warlord", None)

    class FakeLoop:
        session_id = "session-1"

        def request_resume(self):
            raise AssertionError("invalid resume must not reach the agent loop")

    try:
        assert bus.handle_control(
            {
                "type": MessageType.SESSION_RESUME,
                "payload": {
                    "session_id": "session-2",
                    "reason": "operator_resume",
                    "agent_ids": ["warlord", "prophet"],
                },
            },
            FakeLoop(),
        ) is False
        assert bus.handle_control(
            {
                "type": MessageType.SESSION_RESUME,
                "payload": {
                    "session_id": "session-1",
                    "reason": "operator_resume",
                    "agent_ids": ["prophet"],
                },
            },
            FakeLoop(),
        ) is False
    finally:
        bus.close()


def test_monitor_emits_one_halt_and_persists_missed_heartbeat():
    now = [100.0]
    db = FakeDB()
    controls = []
    monitor = HeartbeatMonitor(
        ("warlord", "prophet"),
        interval=1.0,
        missed_count=3,
        session_id="session-1",
        session_db=db,
        control_publisher=controls.append,
        clock=lambda: now[0],
    )

    monitor.observe("warlord")
    monitor.observe("prophet")
    now[0] = 102.9
    assert monitor.check() == []
    now[0] = 103.0
    assert monitor.check() == ["warlord", "prophet"]
    assert monitor.check() == []

    assert controls == [{
        "type": MessageType.SESSION_HALT,
        "payload": {
            "session_id": "session-1",
            "reason": "heartbeat_missed",
            "missed_agent_id": "warlord",
            "missed_count": 3,
        },
    }]
    assert [event[2] for event in db.events] == ["heartbeat_missed", "session_halt"]


def test_resume_requires_explicit_operator_command_and_logs_reconnection():
    now = [0.0]
    db = FakeDB()
    monitor = HeartbeatMonitor(
        ("warlord", "prophet"),
        interval=1.0,
        missed_count=2,
        session_id="session-2",
        session_db=db,
        clock=lambda: now[0],
    )
    monitor.observe("warlord")
    monitor.observe("prophet")
    now[0] = 2.0
    monitor.check()
    now[0] = 2.1
    monitor.observe("warlord")
    monitor.observe("prophet")
    assert monitor.halted is True
    assert monitor.resume({"session_id": "session-2", "reason": "operator_resume", "agent_ids": ["warlord", "prophet"]}) is True
    assert monitor.halted is False
    assert [event[2] for event in db.events] == ["heartbeat_missed", "session_halt", "party_bus_reconnected", "session_resume"]


def test_paused_fsm_restores_state_only_on_explicit_resume_and_loop_sends_no_input():
    db = FakeDB()
    fsm = FishingFSM(session_id="session-3", db=db)
    fsm(PerceptionResult(), "CASTING")
    fsm.pause_for_session_halt("warlord", 3)
    assert fsm.state == "PAUSED"
    assert fsm(PerceptionResult(), "PAUSED") is None
    fsm.resume_session("operator_resume")
    assert fsm.state == "CASTING"

    actions = []
    hsl = HSL(mode="shadow")
    hsl.dispatch_action = lambda action, **kwargs: actions.append(action)
    loop = AgentLoop(
        frame_queue=FrameQueue(maxsize=1),
        policy_queue=PolicyQueue(maxsize=1),
        state_handler=fsm,
        hsl=hsl,
        state_name="PAUSED",
    )
    loop.request_halt()
    loop.tick()
    assert actions == []