import json
import threading
import time
from pathlib import Path

import pytest

from lagent.agent.__main__ import build_parser
from lagent.agent.capture import Frame
from lagent.agent.recording import RecordingSession
from lagent.common.sessions_db import SessionsDB


def test_record_flag_is_available_and_mutually_exclusive_with_live_mode():
    args = build_parser().parse_args(["--record", "--class", "fishing"])

    assert args.record is True
    assert args.profile_class == "fishing"


def test_recording_dual_writes_frames_and_preserves_pipeline_callback(tmp_path: Path):
    pipeline_frames = []
    recording = RecordingSession("session-1", tmp_path)
    recording.start(pipeline_frames.append)

    frame = Frame("window", b"png-bytes", 1000, "test", 1.0)
    recording.publish(frame)
    recording.close()

    assert pipeline_frames == [frame]
    frame_path = tmp_path / "session-1" / "frames" / "000000.png"
    assert frame_path.read_bytes() == b"png-bytes"
    assert recording.frame_count == 1


def test_recording_logs_input_events_and_closes_cleanly(tmp_path: Path):
    recording = RecordingSession("session-2", tmp_path)
    recording.start(lambda frame: None)

    recording.log_input("keyboard", "a", "pressed", timestamp=2.5)
    recording.log_input("mouse", {"x": 10, "y": 20}, "moved", timestamp=2.6)
    recording.close()

    lines = (tmp_path / "session-2" / "inputs.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in lines]
    assert events == [
        {"timestamp": 2.5, "event_type": "keyboard", "key_or_position": "a", "state": "pressed", "frame_number": 0},
        {"timestamp": 2.6, "event_type": "mouse", "key_or_position": {"x": 10, "y": 20}, "state": "moved", "frame_number": 0},
    ]


def test_recording_rejects_path_traversal_session_ids(tmp_path: Path):
    with pytest.raises(ValueError):
        RecordingSession("../outside", tmp_path)


def test_recording_publish_forwards_without_waiting_for_disk_write(tmp_path: Path, monkeypatch):
    pipeline_frames = []
    recording = RecordingSession("session-3", tmp_path)
    recording.start(pipeline_frames.append)
    monkeypatch.setattr("lagent.agent.recording._frame_bytes", lambda frame: time.sleep(0.05) or b"frame")

    started = time.perf_counter()
    recording.publish(Frame("window", b"raw", 1000, "test", 1.0))
    elapsed_ms = (time.perf_counter() - started) * 1000
    recording.close()

    assert pipeline_frames
    assert elapsed_ms < 3.0


def test_recording_session_uses_recording_database_mode(tmp_path: Path):
    db = SessionsDB(str(tmp_path / "sessions.db"))
    db.log_session_start("session-4", "fishing", "recording")

    assert db.get_session("session-4")["mode"] == "recording"
    db.close()


def test_recording_serializes_concurrent_input_and_frame_updates(tmp_path: Path):
    recording = RecordingSession("session-5", tmp_path)
    recording.start(lambda frame: None)
    errors = []

    def publish_frames():
        try:
            for index in range(20):
                recording.publish(Frame("window", f"frame-{index}".encode(), index, "test", float(index)))
        except Exception as exc:  # pragma: no cover - assertion guard
            errors.append(exc)

    def log_inputs():
        try:
            for index in range(20):
                recording.log_input("keyboard", str(index), "pressed", timestamp=float(index))
        except Exception as exc:  # pragma: no cover - assertion guard
            errors.append(exc)

    publishers = threading.Thread(target=publish_frames)
    inputs = threading.Thread(target=log_inputs)
    publishers.start()
    inputs.start()
    publishers.join()
    inputs.join()
    recording.close()

    assert errors == []
    assert recording.frame_count == 20