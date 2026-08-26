import time

from lagent.agent.capture import Frame, FrameQueue
from lagent.agent.inference import PolicyQueue
from lagent.agent.loop import AgentLoop
from lagent.common import Action, PerceptionResult
from lagent.hsl import HSL


def test_frame_and_policy_queues_record_oldest_evictions():
    frame_queue = FrameQueue(maxsize=2)
    policy_queue = PolicyQueue(maxsize=2)

    frame_queue.put_nowait(Frame("win", 1, 1, "src", 1.0))
    frame_queue.put_nowait(Frame("win", 2, 2, "src", 2.0))
    frame_queue.put_nowait(Frame("win", 3, 3, "src", 3.0))

    policy_queue.put_nowait(PerceptionResult(ocr_values={"hp": "1"}))
    policy_queue.put_nowait(PerceptionResult(ocr_values={"hp": "2"}))
    policy_queue.put_nowait(PerceptionResult(ocr_values={"hp": "3"}))

    assert frame_queue.dropped_frames == 1
    assert policy_queue.dropped_results == 1
    assert frame_queue.qsize() == 2
    assert policy_queue.qsize() == 2


def test_agent_loop_tick_emits_tick_id_and_dispatches_action():
    frame_queue = FrameQueue(maxsize=2)
    frame_queue.put_nowait(Frame("win", [1, 2, 3], 1, "src", time.time()))
    policy_queue = PolicyQueue(maxsize=2)
    policy_queue.put_nowait(PerceptionResult(ocr_values={"hp": "99%"}))

    def state_handler(result, state):
        assert result.ocr_values["hp"] == "99%"
        return Action(action_type="wait", duration=0.01)

    loop = AgentLoop(
        frame_queue=frame_queue,
        policy_queue=policy_queue,
        state_handler=state_handler,
        hsl=HSL(mode="shadow"),
        state_name="IDLE",
        profile={},
    )

    tick = loop.tick()

    assert tick["tick_id"]
    assert tick["action"].action_type == "wait"
    assert tick["queue_state"]["frame_queue_size"] == 0
    assert tick["queue_state"]["policy_queue_size"] == 0
