# LAgent

LAgent is a local, vision-driven automation system for a two-character Lineage II party. It observes captured game windows through YOLO and EasyOCR, makes profile-driven FSM decisions, and sends actions through a human simulation layer. It does not read client memory or inject network packets.

## Runtime topology

A full combat session uses five OS processes:

1. `lagent.ui` owns the tray, status overlay, and all child process launches.
2. One `lagent.agent` process controls the Warlord window.
3. One `lagent.agent` process controls the Prophet window.
4. `lagent.gpu_server` exclusively owns YOLO, EasyOCR, and CUDA.
5. `lagent.orchestrator` monitors party heartbeats and coordinates halts.

Processes communicate only over ZeroMQ and append telemetry to `data/sessions.db`. The offline `lagent.train` CLI records, prelabels, trains, and atomically deploys models; it must not run alongside a live session.

## Install

Use Python 3.12 in a project-local environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

The full live runtime targets Windows. macOS and Linux support development and tests; `dxcam` and `pywin32` are skipped there by platform markers.

## Run

The tray is the only supported runtime launcher:

```bash
.venv/bin/python -m lagent.ui
```

Prepare profiles and model weights before starting a session. Quest Mode remains behind its deterministic shadow-validation gate and is not a tray or agent CLI mode.

## Test

```bash
.venv/bin/python -m pytest -q
```

## Documentation

- [Installation](docs/site/installation.html)
- [Preparation and configuration](docs/site/preparation.html)
- [Running LAgent](docs/site/running.html)
- [Combat Mode](docs/site/combat-mode.html)
- [Quest Mode](docs/site/quest-mode.html)
- [Architecture](docs/site/architecture.html)
- [Architecture decisions](docs/architecture-decisions.md)
- [Contributing](CONTRIBUTING.md)