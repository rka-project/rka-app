"""Opt-in launcher for an owner-private Codespace, not a hosted public service.

Consumes only the released Core CLI through the existing App supervisor.
Never imports Core, reads a database, or resets existing state. Optional reviewed
sample initialization uses Core's public REST API after the server is ready.
The environment guard prevents accidental local execution; it is not auth.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections.abc import Mapping
from pathlib import Path

from rka_app.demo_runtime import run_demo

STATE_ROOT = Path("/workspaces/.rka-codespaces-demo")
RUNTIME = Path("/app/.venv/bin/python")
CORE_CLI = Path("/app/.venv/bin/rka")
RUNTIME_CWD = Path("/app")
MARKER = ".rka-app-codespaces-owner.json"


def codespace_name(env: Mapping[str, str]) -> str:
    name = env.get("CODESPACE_NAME", "")
    if env.get("CODESPACES") != "true" or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", name):
        raise ValueError("Run only inside the intended GitHub Codespace; local execution refused")
    return name


def prepare_state(root: Path, name: str) -> Path:
    """Create a separate namespace; refuse symlinks or unrecognized existing data."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", name):
        raise ValueError("Invalid Codespace name")
    if not root.is_absolute() or root.resolve() != root:
        raise ValueError("Demo state root must be absolute and contain no symlinks")
    root.mkdir(mode=0o700, exist_ok=True)  # Parent must already exist.
    # An older operator preview ran as root. Never adopt/chown its live data
    # implicitly when switching the development shell to the workspace owner.
    if os.name == "posix" and root.stat().st_uid != os.geteuid():
        raise ValueError(
            "Demo state belongs to a different OS user; retain it and follow the "
            "non-root migration guide (do not recursively chown a running database)"
        )
    state = root / name
    expected = {"format": 1, "owner": "rka-app-codespaces", "codespace": name}
    if state.is_symlink():
        raise ValueError("Demo state must not be a symlink")
    try:
        state.mkdir(mode=0o700)
    except FileExistsError:
        if os.name == "posix" and state.stat().st_uid != os.geteuid():
            raise ValueError(
                "Existing demo state belongs to a different OS user; retain it"
            ) from None
        marker = state / MARKER
        if not state.is_dir() or marker.is_symlink() or not marker.is_file():
            raise ValueError(
                "Existing state is not owned by this demo; refusing to reuse it"
            ) from None
        try:
            actual = json.loads(marker.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ValueError("Cannot validate existing demo ownership marker") from exc
        if actual != expected:
            raise ValueError(
                "Existing demo ownership marker does not match this Codespace"
            ) from None
        if os.name == "posix" and stat.S_IMODE(state.stat().st_mode) & 0o077:
            raise ValueError(
                "Existing demo state is not private to its OS user; retain it"
            ) from None
    else:
        # Codespaces parent default ACLs may override mkdir's requested mode.
        state.chmod(0o700)
        with (state / MARKER).open("x", encoding="utf-8") as stream:
            json.dump(expected, stream)
        (state / MARKER).chmod(0o600)
    return state


def demo_environment(env: Mapping[str, str], state: Path) -> dict[str, str]:
    # Do not inherit a local DB, server, model endpoint, or custom Core command.
    # Core does not need the Codespace's repository token, cloud credentials or
    # proxy settings. Keep only ordinary process/locale configuration.
    keep = {"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TZ", "TERM", "TMPDIR"}
    clean = {key: value for key, value in env.items() if key in keep}
    clean.update(
        {
            "PYTHONPATH": "/opt/rka-app",
            "PYTHONNOUSERSITE": "1",
            "RKA_DATA_DIR": str(state),
            "RKA_DB_PATH": str(state / "rka.db"),
            "RKA_PROJECT_DIR": str(state),
            "RKA_EMBEDDING_CACHE_DIR": str(state / "fastembed_cache"),
            "RKA_SQLITE_VEC_PATH": "/usr/local/lib/vec0.so",
            "RKA_HOST": "127.0.0.1",
            "RKA_PORT": "7860",
            "RKA_EMBEDDINGS_ENABLED": "false",
            "RKA_LLM_ENABLED": "false",
            "RKA_SERVER_FILE_ROOTS": "[]",
            "RKA_APP_RKA_COMMAND_JSON": json.dumps([str(CORE_CLI)]),
            "RKA_APP_WORKER_ENABLED": "true",
        }
    )
    return clean


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-private-port",
        action="store_true",
        help="Confirm the Codespaces Ports panel shows port 7860 as Private",
    )
    parser.add_argument(
        "--sample-pack",
        type=Path,
        help="Absolute path to the reviewed fictional ZIP (SHA-256 is pinned in App)",
    )
    args = parser.parse_args()
    try:
        name = codespace_name(os.environ)
        if not args.confirm_private_port:
            raise ValueError(
                "Verify port 7860 visibility is Private, then pass --confirm-private-port"
            )
        if not RUNTIME.is_file() or not CORE_CLI.is_file():
            raise ValueError(
                "Pinned Core runtime is missing; build the reviewed devcontainer first"
            )
        if (RUNTIME_CWD / ".env").exists():
            raise ValueError("Unexpected /app/.env; refusing unreviewed runtime configuration")
        os.umask(0o077)
        state = prepare_state(STATE_ROOT, name)
        env = demo_environment(os.environ, state)
        os.chdir(RUNTIME_CWD)
        print(f"[rka-app] private demo state: {state}; port 7860; embeddings off", flush=True)
        os.environ.clear()
        os.environ.update(env)
        raise SystemExit(run_demo(state, args.sample_pack))
    except (ValueError, OSError) as exc:
        print(f"[rka-app] Codespaces launch refused: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
