"""Codespaces-only lifetime lock and optional seeded startup, not a cloud service."""

from __future__ import annotations

import os
import socket
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from rka_app.demo_seed import SHOWCASE, CoreAPI, SeedError, ensure_sample
from rka_app.supervisor import Settings, supervise


class AlreadyRunning(SeedError):
    """A live owner already holds this App namespace lock."""


@contextmanager
def namespace_lock(state: Path, *, filename: str = ".runtime.lock") -> Iterator[None]:
    # Codespaces runs Linux. Import here so pure config tests can run on Windows.
    if os.name != "posix":
        raise SeedError("The Codespaces runtime requires a POSIX namespace lock")
    import fcntl

    if filename not in {".runtime.lock", ".startup.lock"}:
        raise SeedError("Invalid App lock name")
    fd = os.open(state / filename, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise SeedError("Runtime lock must be a regular file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AlreadyRunning(
                "This demo is already running; a second launch was refused"
            ) from exc
        yield
    finally:
        os.close(fd)  # Kernel releases the lock even after a crash; never unlink it.


def run_demo(
    state: Path,
    pack_path: Path | None,
    *,
    guard: Callable[[], None] | None = None,
    report: Callable[[str, str | None], None] | None = None,
) -> int:
    settings = Settings.from_env()
    if settings.host != "127.0.0.1" or settings.port != 7860:
        raise SeedError("Codespaces runtime requires loopback demo port 7860")
    with namespace_lock(state):
        project_id: str | None = None

        def status(phase: str) -> None:
            if report is not None:
                report(phase, project_id)

        try:
            status("starting")
            if guard is not None:
                guard()
            # Refuse an occupied port before starting Core or performing API writes.
            with socket.socket() as probe:
                try:
                    probe.bind((settings.host, settings.port))
                except OSError as exc:
                    raise SeedError(
                        "Demo port is occupied; existing process left untouched"
                    ) from exc

            def initialize() -> None:
                nonlocal project_id
                if pack_path is not None:
                    project_id = ensure_sample(CoreAPI(settings.port), state, pack_path)
                    print(
                        f"[rka-app] Sample ready: {SHOWCASE.project_name} ({project_id}). "
                        "Open private port 7860 and select this project. "
                        "Keyword search is available; embeddings are off.",
                        flush=True,
                    )

            result = supervise(
                settings,
                on_ready=initialize,
                on_started=lambda: status("running"),
                on_tick=guard,
            )
            status("stopped" if result == 0 else "failed")
            return result
        except Exception:
            status("failed")
            raise
