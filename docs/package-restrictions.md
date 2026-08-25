# Package and Environment Restrictions for Future Runs

## Purpose

This document captures the failure patterns seen during the recent setup and verification runs so the same mistakes are avoided in later work. The project is configured for a Python 3.12 environment and should be validated inside an isolated virtual environment, not by mutating the system interpreter.

## Current workflow analysis

The recent failures were not caused by the project logic itself. They were caused by environment drift and package-install mistakes during verification.

### 1) System Python was used for project setup

The system Python on macOS is managed by the OS and blocks direct package installation with PEP 668 errors such as:

- "externally-managed-environment"
- "No module named pytest"
- "No module named numpy"

This is a strong signal that package installs should never be done directly into the machine-wide Python.

### 2) Package installation was attempted outside the project venv

Several commands attempted to install dependencies with `pip` on the default interpreter instead of the project-local environment. That led to inconsistent state across:

- system Python
- project .venv
- VS Code-integrated shell

This mismatch caused missing modules, inconsistent package resolution, and repeated retry loops.

### 3) Platform-specific dependencies were attempted in a non-Windows host

The project declares Windows-only runtime support for `pywin32`:

- [pyproject.toml](../pyproject.toml)

This package is intentionally unavailable on macOS/Linux. Installing it on a non-Windows environment causes resolution failures and wastes time.

### 4) The project requires a disciplined Python runtime

The declared runtime target is Python 3.12:

- [pyproject.toml](../pyproject.toml)

The environment must therefore be aligned to 3.12, not 3.14 or the OS-managed interpreter, unless explicitly chosen for a local override. The default macOS toolchain may not match the intended project runtime.

### 5) SSL or certificate issues were encountered when reaching PyPI

The package index was sometimes unreachable because of SSL trust problems. This is not a code issue, but an environment issue. These failures should be treated as infrastructure/setup issues, not as a project code failure.

## Hard restrictions to enforce in future runs

### Restriction 1: Never install project packages into the system interpreter

Do not run commands like:

- `python3 -m pip install ...`
- `pip install ...`
- `--break-system-packages`

unless the user explicitly requests a system-level override. This project is designed to run in a dedicated virtual environment.

Use instead:

```bash
cd /Users/VCALAIO/Documents/OwnApps/LAgent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

### Restriction 2: Always use the project venv for testing and verification

All validation commands for this repo should be executed inside the project environment, with a local `PYTHONPATH` if needed:

```bash
cd /Users/VCALAIO/Documents/OwnApps/LAgent
. .venv/bin/activate
PYTHONPATH=. python -m pytest -q
```

This avoids hidden drift between the IDE shell and the interpreter used to run the code.

### Restriction 3: Do not install platform-specific packages on unsupported hosts

Do not install or demand packages like:

- `pywin32`
- `dxcam`
- Windows-only screen-capture tooling

unless the target machine is actually Windows and the runtime is compatible with those dependencies.

The project’s Dockerfile explicitly avoids these platform-specific dependencies in the default test image:

- [Dockerfile](../Dockerfile)

### Restriction 4: Keep dependency installation aligned to the project manifest

The canonical dependency list is the source of truth:

- [pyproject.toml](../pyproject.toml)

Do not broaden the dependency set with ad hoc packages just to unblock one failing import in a local shell. If something is missing, first verify:

1. the active interpreter is the project venv
2. the project was installed via `pip install -e .`
3. the missing package is part of the declared dependency set or a test-only requirement
4. the package is valid for the current OS and Python version

### Restriction 5: Handle certificate issues as environment setup, not project logic

If PyPI fails with SSL verification errors, fix the environment before continuing. Typical valid actions include:

- using the environment’s own certificate bundle
- ensuring the venv is active
- verifying Python and OpenSSL are consistent
- testing package installation with the project venv only

Avoid random flags such as `--trusted-host` and `--break-system-packages` unless there is a clear, documented reason and the user approves the workaround.

### Restriction 6: Prefer the project Docker/test workflow for repeatable validation

For CI-like or repeatable validation, use the project’s container path instead of ad hoc local pip attempts:

```bash
docker build -t lagent-test .
docker run --rm lagent-test
```

This keeps the runtime consistent with the project’s expected setup.

## Required developer workflow

For future runs, the safe pattern is:

```bash
cd /Users/VCALAIO/Documents/OwnApps/LAgent
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
PYTHONPATH=. python -m pytest -q
```

If macOS-specific or non-Windows packages are needed, they should be installed only where the runtime supports them, and never as a workaround for a missing system package manager state.

## Decision rule

If a command fails because of:

- system package policy
- missing interpreter alignment
- unsupported OS dependency
- SSL/certificate trust problems

then stop and fix the environment before changing the code.

The project code should not be treated as the source of these errors; the environment is the primary problem.
