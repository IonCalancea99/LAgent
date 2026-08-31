"""Agent process entry point."""

import argparse
import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from lagent.common import GameState, PerceptionResult
from lagent.agent.capture import CaptureThread
from lagent.agent.inference import InferenceClient, PolicyQueue
from lagent.agent.loop import AgentLoop
from lagent.agent.recording import PynputInputListener, RecordingSession
from lagent.agent.fishing_fsm import FishingFSM
from lagent.agent.party_bus import PartyBus
from lagent.agent.prophet import ProphetBuffCycleFSM
from lagent.agent.startup import StartupProfileResolver, scan_window
from lagent.agent.warlord import WarlordCombatFSM
from lagent.common.transport import GPU_ENDPOINT
from lagent.common.transport import (
    ORCHESTRATOR_CONTROL_ENDPOINT,
    PROPHET_PARTY_ENDPOINT,
    WARLORD_PARTY_ENDPOINT,
)
from lagent.common.sessions_db import SessionsDB
from lagent.hsl import HSL


def _ocr_percent(value: str | None, default: float = 100.0) -> float:
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    return min(100.0, max(0.0, float(match.group()))) if match else default


def _game_state_from_perception(result: PerceptionResult, party_bus: Any) -> GameState:
    peer_state = None if party_bus.is_peer_state_stale() else party_bus.peer_party_state
    mob_positions = {}
    character_position = (0, 0)
    loot_presence = False
    for index, detection in enumerate(result.detections):
        x1, y1, x2, y2 = detection.bbox_xyxy
        center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
        name = detection.class_name.lower()
        if name in {"mob", "enemy", "monster"}:
            mob_positions[f"{name}-{index}"] = center
        elif name in {"character", "player", "self"}:
            character_position = center
        elif name == "loot":
            loot_presence = True
    return GameState(
        hp_percent=_ocr_percent(result.ocr_values.get("hp")),
        mp_percent=_ocr_percent(result.ocr_values.get("mp")),
        active_buffs=[],
        mob_positions=mob_positions,
        loot_presence=loot_presence,
        character_position=character_position,
        ui_mode="combat",
        peer_party_state=peer_state,
    )


def build_state_handler(selected_class: str, *, profile: Any, session_id: str, db: Any, party_bus: Any) -> Any:
    if selected_class == "fishing":
        return FishingFSM(profile=profile, session_id=session_id, db=db)
    if selected_class == "warlord":
        return WarlordCombatFSM(profile=profile, session_id=session_id, db=db, party_bus=party_bus)
    if selected_class == "prophet":
        return ProphetBuffCycleFSM(
            profile=profile,
            game_state_provider=lambda result: _game_state_from_perception(result, party_bus),
            session_id=session_id,
            db=db,
            party_bus=party_bus,
        )
    raise ValueError(f"unsupported agent class: {selected_class}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start a LAgent agent")
    parser.add_argument(
        "--class",
        dest="profile_class",
        default=None,
        choices=("warlord", "prophet", "fishing"),
    )
    parser.add_argument("--session-id", dest="session_id", default=None, help="Session ID (auto-generated if not provided)")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--record", action="store_true", help="Record frames and manual keyboard/mouse input")
    parser.add_argument("--debug", action="store_true", help="Run the live capture and inference debug pipeline")
    mode_group.add_argument("--shadow", action="store_true", help="Shape and log actions without sending OS input")
    parser.add_argument("--window-title", default="Lineage II", help="Game window title to capture")
    parser.add_argument("--gpu-endpoint", default=GPU_ENDPOINT, help="GPU inference server endpoint")
    parser.add_argument("--fps", type=int, default=10, help="Capture and inference rate")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Resolve the profile, record session start, then exit without running the control loop",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    session_mode = "recording" if args.record else ("shadow" if args.shadow else "active")

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    def startup_scan() -> PerceptionResult:
        try:
            return scan_window(args.window_title, endpoint=args.gpu_endpoint, fps=args.fps)
        except (OSError, RuntimeError, TimeoutError) as exc:
            logger.warning("Startup character scan unavailable: %s; using manual fallback", exc)
            return PerceptionResult()

    def confirm_profile(result) -> str:
        while True:
            try:
                selected = input(
                    f"Unable to identify character ({result.profile_class or 'unknown'}, "
                    f"confidence={result.confidence:.3f}). Enter class [warlord/prophet]: "
                ).strip().lower()
            except EOFError:
                logger.warning("No interactive confirmation available; selecting warlord")
                return "warlord"
            if selected in ("warlord", "prophet"):
                return selected
            logger.warning("Unsupported profile '%s'; enter warlord or prophet", selected or "<empty>")

    # Initialize sessions database
    db_path = Path("data") / "sessions.db"
    try:
        db = SessionsDB(str(db_path))
        
        # Generate or use provided session ID
        session_id = args.session_id or f"agent-{args.profile_class or 'auto'}-{uuid.uuid4().hex[:8]}"

        # Session row must exist before any event is appended (events.session_id is a foreign key).
        db.log_session_start(
            session_id=session_id,
            profile=args.profile_class or "pending",
            mode=session_mode,
        )
        logger.info("Session started: %s", session_id)

        resolver = StartupProfileResolver()
        assignment = resolver.resolve(
            override=args.profile_class,
            scan=startup_scan,
            confirm=confirm_profile,
            session_id=session_id,
            db=db,
        )
        profile = assignment.profile
        selected_class = assignment.profile_class
        logger.info("Profile loaded: %s", profile.name)

        if selected_class != args.profile_class:
            db.update_session_profile(session_id, selected_class)

        # Log startup event
        db.append_event(
            session_id=session_id,
            source="agent",
            type="startup",
            payload={
                "profile": selected_class,
                "component": "agent",
                "status": "initialized",
                "mode": session_mode,
            }
        )

        if not args.check:
            party_endpoints = {
                "warlord": WARLORD_PARTY_ENDPOINT,
                "prophet": PROPHET_PARTY_ENDPOINT,
            }
            party_bus = PartyBus(
                selected_class,
                party_endpoints.get(selected_class),
                session_db=db,
                session_id=session_id,
            )
            if party_bus.publisher_endpoint is not None:
                party_bus.start_publisher()
            for endpoint in party_endpoints.values():
                if endpoint != party_bus.publisher_endpoint:
                    party_bus.subscribe(endpoint)
            party_bus.subscribe(ORCHESTRATOR_CONTROL_ENDPOINT)
            recording = RecordingSession(session_id) if args.record else None
            input_listener = PynputInputListener(recording) if recording is not None else None
            capture = CaptureThread(
                args.window_title,
                fps=args.fps,
                on_frame=recording.publish if recording is not None else None,
            )
            if recording is not None:
                recording.start(capture.frame_queue.put_frame)
                input_listener.start()
            policy_queue = PolicyQueue(maxsize=2)
            inference = InferenceClient(
                selected_class,
                capture.frame_queue,
                policy_queue,
                endpoint=args.gpu_endpoint,
                profile=profile,
                debug=True,
            )
            state_handler = build_state_handler(
                selected_class,
                profile=profile,
                session_id=session_id,
                db=db,
                party_bus=party_bus,
            )
            hsl = HSL(
                profile=profile,
                mode="shadow" if args.shadow or args.record else "active",
                session_id=session_id,
                sessions_db=db,
            )
            loop = AgentLoop(
                frame_queue=capture.frame_queue,
                policy_queue=policy_queue,
                state_handler=state_handler,
                hsl=hsl,
                profile=profile,
                session_id=session_id,
                db=db,
                capture=capture,
                inference=inference,
                party_bus=party_bus,
            )
            logger.info("Agent control loop started for %s", args.window_title)
            try:
                loop.run(tick_interval=0.1)
            except KeyboardInterrupt:
                logger.info("Stopping agent control loop")
            finally:
                if input_listener is not None:
                    input_listener.stop()
                if recording is not None:
                    recording.close()
                db.close()
                party_bus.close()
        else:
            db.close()
        
    except Exception as e:
        logger.error("Agent startup failed: %s", e)
        raise


if __name__ == "__main__":
    main()
