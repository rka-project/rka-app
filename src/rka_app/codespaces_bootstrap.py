"""First-use provisioning for a released user-owned demo; safe resume thereafter."""

from __future__ import annotations

import os
import sys

from rka_app import codespaces_autostart as auto
from rka_app import demo_distribution as distribution
from rka_app.codespaces import codespace_name, prepare_state
from rka_app.codespaces_privacy import PrivatePortGuard
from rka_app.demo_runtime import namespace_lock
from rka_app.demo_seed import SHOWCASE, SeedError, write_receipt

# Source gate opened after the Core 3.0.1 release and non-root image checks.
# Publishing this exact candidate still requires its own image tests and review;
# anonymous pull and fresh/non-owner Codespace acceptance gate the homepage link.
PUBLIC_DEMO_ENABLED = True


def bootstrap(name: str) -> str:
    state = auto.managed_state(name)
    if state is not None and ((state / auto.CONFIG).exists() or (state / auto.CONFIG).is_symlink()):
        # Includes explicit disable, corrupt config, edited project and a lost
        # original ZIP. Never overwrite configuration or re-enable a user opt-out.
        return auto.start(name)
    if not PUBLIC_DEMO_ENABLED or not distribution.PUBLIC_SAMPLE_ENABLED:
        return "preview only: public demo runtime is not released; follow WELCOME.md"
    auto.runtime_available()
    PrivatePortGuard(name, os.environ).wait_for_private()
    state = prepare_state(auto.STATE_ROOT, name)
    with namespace_lock(state, filename=".startup.lock"), namespace_lock(state):
        if (state / auto.CONFIG).exists() or (state / auto.CONFIG).is_symlink():
            # Another invocation may have finished setup during the port wait.
            auto.load_config(state, name)
        else:
            # Only our marker and lock/download cache may precede first setup.
            # Never create an opt-in beside uncertain receipts or existing data.
            allowed = {
                ".rka-app-codespaces-owner.json",
                ".startup.lock",
                ".runtime.lock",
                distribution.SAMPLE_FILENAME,
            }
            if any(path.name not in allowed for path in state.iterdir()):
                raise SeedError(
                    "Existing state without automatic configuration; inspect, do not reset"
                )
            pack = distribution.download_sample(state)
            write_receipt(
                state,
                {
                    "format": 1,
                    "codespace": name,
                    "enabled": True,
                    "sha256": SHOWCASE.sha256,
                    "pack_path": str(pack),
                },
                filename=auto.CONFIG,
            )
    return auto.start(name)


def main() -> None:
    try:
        name = codespace_name(os.environ)
        os.umask(0o077)
        print("[rka-app] " + bootstrap(name), flush=True)
    except (ValueError, OSError) as exc:
        print(f"[rka-app] Setup refused: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
