"""Read GitHub's current port ACL through its CLI. Never change visibility."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from collections.abc import Mapping

from rka_app.demo_seed import SeedError

TRUSTED_PATH = "/usr/local/bin:/usr/bin:/bin"


class PortNotRegistered(SeedError):
    """The forwarding service has not listed the demo port yet."""


class PrivatePortGuard:
    """Check before launch and at most every 30 seconds during supervision.

    This is a fail-closed operational guard, not the network access boundary.
    GitHub private forwarding is that boundary; an owner can still change it.
    """

    def __init__(self, name: str, env: Mapping[str, str]):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", name):
            raise SeedError("Invalid Codespace identity")
        self.name = name
        keep = {"HOME", "USER", "LANG", "LC_ALL", "GH_TOKEN", "GITHUB_TOKEN"}
        self.env = {key: value for key, value in env.items() if key in keep}
        self.env.update(
            {
                "PATH": TRUSTED_PATH,
                "GH_HOST": "github.com",
                "GH_PROMPT_DISABLED": "1",
                "GH_PAGER": "cat",
                "GH_NO_UPDATE_NOTIFIER": "1",
                "GH_DEBUG": "",
            }
        )
        self.last_verified: float | None = None

    def wait_for_private(self, timeout: float = 60) -> None:
        """Only absent registration is retryable; never retry public/unknown/auth.

        A successful check precedes all Core launch/import activity. The maximum
        wall time includes one final bounded (15-second) CLI call.
        """
        if not 0 <= timeout <= 60:
            raise SeedError("Invalid private-port wait budget")
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.check(force=True)
                return
            except PortNotRegistered:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SeedError(
                        "Port 7860 registration timed out; forward it as Private "
                        "in the Ports panel, then retry. Nothing was made public."
                    ) from None
                time.sleep(min(2, remaining))

    def check(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and self.last_verified is not None and now - self.last_verified < 30:
            return
        executable = shutil.which("gh", path=TRUSTED_PATH)
        if executable is None:
            raise SeedError("GitHub CLI is missing; automatic startup refused")
        try:
            result = subprocess.run(
                [
                    executable,
                    "codespace",
                    "ports",
                    "-c",
                    self.name,
                    "--json",
                    "sourcePort,visibility",
                ],
                env=self.env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SeedError("Cannot verify GitHub port privacy; startup/runtime stopped") from exc
        if result.returncode != 0:
            # gh may print credentials, authorization URLs or repository details.
            # Do not copy stdout/stderr into App diagnostics or fall back to a flag.
            raise SeedError("GitHub port query unavailable; automatic mode requires authorized gh")
        if len(result.stdout) > 65536:
            raise SeedError("Unexpected GitHub port response size")
        try:
            ports = json.loads(result.stdout)
        except (ValueError, UnicodeError) as exc:
            raise SeedError("Invalid GitHub port response") from exc
        if not isinstance(ports, list) or not all(
            isinstance(port, dict) and type(port.get("sourcePort")) is int for port in ports
        ):
            raise SeedError("Invalid GitHub port-list contract")
        matches = [port for port in ports if port["sourcePort"] == 7860]
        if not matches:
            raise PortNotRegistered("Port 7860 is not registered; Core will not start")
        if len(matches) != 1 or matches[0].get("visibility") != "private":
            raise SeedError("Port 7860 is not verified Private; automatic startup/runtime stopped")
        self.last_verified = time.monotonic()
