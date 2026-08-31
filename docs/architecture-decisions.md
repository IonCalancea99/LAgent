# LAgent Architecture Decisions

This is the stable, linkable index for decisions AD-1 through AD-13. The authoritative design detail remains the [Architecture Spine](../_bmad-output/planning-artifacts/architecture/architecture-LAgent-2026-08-04/ARCHITECTURE-SPINE.md).

| Decision | Invariant |
|---|---|
| AD-1 | Runtime processes communicate only through ZeroMQ; no shared memory or filesystem polling. |
| AD-2 | The GPU server is the sole owner of model loading, YOLO, EasyOCR, and CUDA. |
| AD-3 | Bounded agent queues have maximum depth 2 and evict the oldest item; capture never blocks. |
| AD-4 | Each agent exclusively owns its `GameState`; only `PartyState` crosses process boundaries. |
| AD-5 | The tray/UI is the sole launcher of runtime child processes. |
| AD-6 | Training is an offline CLI and never runs with a live session. |
| AD-7 | Models deploy through an atomic `models/<class>/current.pt` replacement and load only at GPU-server startup. |
| AD-8 | Every action passes through a per-agent HSL instance; Shadow Mode suppresses OS input inside HSL. |
| AD-9 | Processes use separate connections to one WAL-mode `data/sessions.db`. |
| AD-10 | OCR runs only in the GPU server; agents consume `PerceptionResult` and use frame-pixel coordinates. |
| AD-11 | Agent/GPU uses DEALER/ROUTER; party state and heartbeats use PUB/SUB; runtime uses no REQ/REP sockets. |
| AD-12 | Allowed imports are `lagent.{hsl,agent,gpu_server,train,ui} -> lagent.common`, plus `lagent.agent -> lagent.hsl`. |
| AD-13 | Recording Mode is selected at agent launch and cannot be combined with active OS input. |