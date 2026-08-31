# Contributing to LAgent

## Environment

Use Python 3.12 and the repository virtual environment. Do not install dependencies into the system interpreter.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Development rules

- Preserve the [architecture decisions](docs/architecture-decisions.md), especially GPU ownership, import direction, tray-only process launching, and oldest-item queue eviction.
- Keep shared process contracts in `lagent.common`; do not add cross-package runtime imports.
- Add focused tests for changed behavior and do not hide missing runtime dependencies with code fallbacks.
- Keep Quest Mode fail-closed. Production activation requires an explicit product decision beyond the current shadow-validation gate.
- Do not commit runtime data, recordings, model weights, virtual environments, or generated package metadata.

## Validation

Run focused tests first, followed by the complete suite:

```bash
.venv/bin/python -m pytest tests/path_to_focused_test.py -q
.venv/bin/python -m pytest -q
```

For tray command changes, build every configured child command and parse it with the child module's own CLI parser. Review the final diff for unrelated formatting or generated artifacts before opening a change.