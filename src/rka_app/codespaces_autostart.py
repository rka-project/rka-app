"""Opt-in private Codespaces restart adapter. No public artifact fetching.

postStart invokes `start`: without an owned opt-in record it does nothing.
Each actual launch requires a fresh successful GitHub private-port query.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from rka_app.codespaces import (
    CORE_CLI,
    RUNTIME,
    RUNTIME_CWD,
    STATE_ROOT,
    codespace_name,
    demo_environment,
    prepare_state,
)
from rka_app.codespaces_privacy import TRUSTED_PATH, PrivatePortGuard
from rka_app.demo_runtime import AlreadyRunning, namespace_lock, run_demo
from rka_app.demo_seed import SHOWCASE, SeedError, read_regular, verified_pack, write_receipt

CONFIG = "autostart.json"
STATUS = "runtime-status.json"


def runtime_available() -> None:
    if not RUNTIME.is_file() or not CORE_CLI.is_file():
        raise SeedError("Pinned Core runtime missing; automatic startup refused")
    if (RUNTIME_CWD / ".env").exists():
        raise SeedError("Unexpected runtime .env; automatic startup refused")


def load_config(state: Path, name: str) -> dict:
    try:
        value = json.loads(read_regular(state / CONFIG, 16384))
        if (
            not isinstance(value, dict)
            or set(value) != {"format", "codespace", "enabled", "sha256", "pack_path"}
            or type(value["format"]) is not int
            or value["format"] != 1
            or value["codespace"] != name
            or type(value["enabled"]) is not bool
            or value["sha256"] != SHOWCASE.sha256
            or not isinstance(value["pack_path"], str)
            or not Path(value["pack_path"]).is_absolute()
        ):
            raise SeedError("Automatic-start configuration does not match this demo")
        return value
    except (ValueError, OSError) as exc:
        raise SeedError("Cannot validate automatic-start configuration; state retained") from exc


def managed_state(name: str) -> Path | None:
    candidate = STATE_ROOT / name
    if not candidate.exists() and not candidate.is_symlink():
        return None
    # Validates ownership before reading any opt-in or status files.
    return prepare_state(STATE_ROOT, name)


def is_running(state: Path) -> bool:
    try:
        with namespace_lock(state):
            return False
    except AlreadyRunning:
        return True


def read_status(state: Path) -> dict | None:
    path = state / STATUS
    if not path.exists() and not path.is_symlink():
        return None
    try:
        value = json.loads(read_regular(path, 16384))
        if (
            not isinstance(value, dict)
            or value.get("format") != 1
            or value.get("phase") not in {"starting", "running", "stopped", "failed"}
            or not isinstance(value.get("launch_id"), str)
            or not re.fullmatch(r"[a-f0-9]{32}", value["launch_id"])
        ):
            raise SeedError("Invalid runtime status")
        return value
    except (OSError, ValueError) as exc:
        raise SeedError("Cannot validate runtime status; state retained") from exc


def configure(name: str, pack_path: Path) -> Path:
    runtime_available()
    verified_pack(pack_path, SHOWCASE)
    # Refuse before creating opt-in/state if this environment cannot read ACLs.
    PrivatePortGuard(name, os.environ).check(force=True)
    state = prepare_state(STATE_ROOT, name)
    with namespace_lock(state, filename=".startup.lock"), namespace_lock(state):
        value = {
            "format": 1,
            "codespace": name,
            "enabled": True,
            "sha256": SHOWCASE.sha256,
            "pack_path": str(pack_path),
        }
        if (state / CONFIG).exists() or (state / CONFIG).is_symlink():
            existing = load_config(state, name)
            if existing["pack_path"] != value["pack_path"]:
                raise SeedError("Existing sample location differs; automatic overwrite refused")
        write_receipt(state, value, filename=CONFIG)
    return state


def control_environment() -> dict[str, str]:
    keep = {
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "TZ",
        "TMPDIR",
        "CODESPACES",
        "CODESPACE_NAME",
        "GITHUB_TOKEN",
        "GH_TOKEN",
    }
    result = {key: value for key, value in os.environ.items() if key in keep}
    result.update(
        {
            "PATH": TRUSTED_PATH,
            "PYTHONPATH": "/opt/rka-app",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return result


def stop_owned_launch(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=60)
    except subprocess.TimeoutExpired:
        # start_new_session made this exact live child the group owner. No PID
        # read from a status file is ever used to signal an existing process.
        if os.getpgid(child.pid) != child.pid:
            raise SeedError("Cannot verify launch process group; inspect manually") from None
        os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=5)


def start(name: str) -> str:
    state = managed_state(name)
    if state is None or not ((state / CONFIG).exists() or (state / CONFIG).is_symlink()):
        return "disabled: no opt-in record; nothing started"
    config = load_config(state, name)
    if not config["enabled"]:
        return "disabled: nothing started"
    runtime_available()
    with namespace_lock(state, filename=".startup.lock"):
        if is_running(state):
            return "already running: no additional process started (not a fresh readiness claim)"
        launch_id = uuid.uuid4().hex
        child = subprocess.Popen(
            [str(RUNTIME), "-m", "rka_app.codespaces_autostart", "_run", "--launch-id", launch_id],
            env=control_environment(),
            cwd=RUNTIME_CWD,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 180
            while child.poll() is None:
                status = read_status(state)
                if status and status["launch_id"] == launch_id:
                    if status["phase"] == "running":
                        return "running: open private port 7860 and select the sample project"
                    if status["phase"] in {"stopped", "failed"}:
                        break
                if time.monotonic() >= deadline:
                    raise SeedError("Automatic startup timed out; this launch will be stopped")
                time.sleep(0.2)
            raise SeedError("Automatic startup failed; inspect status and retry in the foreground")
        except BaseException:
            stop_owned_launch(child)
            raise


def run_managed(name: str, launch_id: str) -> int:
    if not re.fullmatch(r"[a-f0-9]{32}", launch_id):
        raise SeedError("Invalid launch identity")
    runtime_available()
    state = managed_state(name)
    if state is None:
        raise SeedError("No owned demo state")
    config = load_config(state, name)
    if not config["enabled"]:
        raise SeedError("Automatic startup is disabled")
    guard = PrivatePortGuard(name, os.environ)
    # On resume the lifecycle hook may precede forwarding registration. Waiting
    # is safe here: no Core process has been started and no import has occurred.
    guard.wait_for_private()

    def report(phase: str, project_id: str | None) -> None:
        write_receipt(
            state,
            {
                "format": 1,
                "launch_id": launch_id,
                "phase": phase,
                "project_id": project_id,
                "pid": os.getpid(),
                "updated_at": time.time(),
            },
            filename=STATUS,
        )

    # The controller alone retains the necessary gh auth in its private object;
    # the Core processes get neither GitHub credentials nor proxy overrides.
    env = demo_environment(os.environ, state)
    os.environ.clear()
    os.environ.update(env)
    os.chdir(RUNTIME_CWD)
    return run_demo(state, Path(config["pack_path"]), guard=guard.check, report=report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    enable = subcommands.add_parser(
        "enable", help="Verify prerequisites and opt in; does not start"
    )
    enable.add_argument("--sample-pack", type=Path, required=True)
    subcommands.add_parser("disable", help="Disable future automatic launches; does not stop Core")
    subcommands.add_parser("start", help="Start or reuse the explicitly enabled private demo")
    subcommands.add_parser("run", help="Run enabled automatic mode in the foreground for diagnosis")
    subcommands.add_parser("status", help="Show last status and whether its namespace is locked")
    internal = subcommands.add_parser("_run", help=argparse.SUPPRESS)
    internal.add_argument("--launch-id", required=True)
    args = parser.parse_args()
    try:
        name = codespace_name(os.environ)
        os.umask(0o077)
        if args.command == "enable":
            configure(name, args.sample_pack)
            print("[rka-app] Auto-start enabled. Run start now, or resume this Codespace later.")
        elif args.command == "start":
            print("[rka-app] " + start(name))
        elif args.command == "_run":
            raise SystemExit(run_managed(name, args.launch_id))
        elif args.command == "run":
            raise SystemExit(run_managed(name, uuid.uuid4().hex))
        else:
            state = managed_state(name)
            if state is None:
                print("[rka-app] No managed state; nothing changed")
            elif args.command == "disable":
                with namespace_lock(state, filename=".startup.lock"):
                    config = load_config(state, name)
                    config["enabled"] = False
                    write_receipt(state, config, filename=CONFIG)
                print("[rka-app] Future automatic starts disabled; running Core was not stopped")
            else:
                print(
                    json.dumps(
                        {"namespace_locked": is_running(state), "last_status": read_status(state)}
                    )
                )
    except (ValueError, OSError) as exc:
        print(f"[rka-app] Automatic mode refused: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
