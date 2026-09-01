"""Minimal PID 1 supervisor for the RKA Core server and worker.

This module deliberately treats Core as an external product. It launches the
public ``rka`` CLI, waits on the public health endpoint, and never imports
``rka.*`` or opens Core storage directly.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass


def _log(message: str) -> None:
    print(f"[rka-app] {message}", file=sys.stderr, flush=True)


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero, got {raw!r}")
    return value


def _port(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if not 1 <= value <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535, got {raw!r}")
    return value


def _boolean(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false, got {raw!r}")


def _command_prefix() -> tuple[str, ...]:
    raw_json = os.environ.get("RKA_APP_RKA_COMMAND_JSON")
    if raw_json is not None:
        try:
            value = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError("RKA_APP_RKA_COMMAND_JSON must be a JSON string array") from exc
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(part, str) and part for part in value)
        ):
            raise ValueError("RKA_APP_RKA_COMMAND_JSON must be a non-empty JSON string array")
        return tuple(value)
    raw = os.environ.get("RKA_APP_RKA_COMMAND", "rka")
    command = tuple(shlex.split(raw))
    if not command:
        raise ValueError("RKA_APP_RKA_COMMAND must not be empty")
    return command


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    worker_enabled: bool
    startup_timeout: float
    shutdown_timeout: float
    health_interval: float
    command_prefix: tuple[str, ...]

    @classmethod
    def from_env(cls) -> Settings:
        host = os.environ.get("RKA_HOST", "0.0.0.0").strip()
        if not host:
            raise ValueError("RKA_HOST must not be empty")
        return cls(
            host=host,
            port=_port("RKA_PORT", 7860),
            worker_enabled=_boolean("RKA_APP_WORKER_ENABLED", True),
            startup_timeout=_positive_float("RKA_APP_STARTUP_TIMEOUT", 120.0),
            shutdown_timeout=_positive_float("RKA_APP_SHUTDOWN_TIMEOUT", 20.0),
            health_interval=_positive_float("RKA_APP_HEALTH_INTERVAL", 0.25),
            command_prefix=_command_prefix(),
        )

    @property
    def health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/health"

    @property
    def server_command(self) -> tuple[str, ...]:
        return (*self.command_prefix, "serve", "--host", self.host, "--port", str(self.port))

    @property
    def worker_command(self) -> tuple[str, ...]:
        return (*self.command_prefix, "worker")


def _health_ready(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def _start(command: Sequence[str], role: str) -> subprocess.Popen[bytes]:
    _log(f"starting {role}: {shlex.join(command)}")
    return subprocess.Popen(command)


def _stop(process: subprocess.Popen[bytes] | None, role: str, timeout: float) -> None:
    if process is None or process.poll() is not None:
        return
    _log(f"stopping {role} (pid {process.pid})")
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _log(f"{role} exceeded {timeout:g}s shutdown timeout; killing")
        process.kill()
        process.wait(timeout=5)


def supervise(settings: Settings) -> int:
    stop_requested = threading.Event()

    def request_stop(signum: int, _frame: object) -> None:
        _log(f"received signal {signum}; beginning shutdown")
        stop_requested.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    server: subprocess.Popen[bytes] | None = None
    worker: subprocess.Popen[bytes] | None = None
    exit_code = 0
    try:
        server = _start(settings.server_command, "server")
        deadline = time.monotonic() + settings.startup_timeout
        while not stop_requested.is_set():
            server_code = server.poll()
            if server_code is not None:
                _log(f"server exited before readiness with code {server_code}")
                return server_code or 1
            if _health_ready(settings.health_url):
                _log(f"server ready at {settings.health_url}")
                break
            if time.monotonic() >= deadline:
                _log(f"server readiness timed out after {settings.startup_timeout:g}s")
                return 1
            stop_requested.wait(settings.health_interval)

        if stop_requested.is_set():
            return 0

        if settings.worker_enabled:
            worker = _start(settings.worker_command, "worker")
        else:
            _log("worker disabled by RKA_APP_WORKER_ENABLED=false")

        while not stop_requested.wait(settings.health_interval):
            server_code = server.poll()
            if server_code is not None:
                _log(f"server exited unexpectedly with code {server_code}")
                exit_code = server_code or 1
                break
            if worker is not None:
                worker_code = worker.poll()
                if worker_code is not None:
                    _log(f"worker exited unexpectedly with code {worker_code}")
                    exit_code = worker_code or 1
                    break
    finally:
        _stop(worker, "worker", settings.shutdown_timeout)
        _stop(server, "server", settings.shutdown_timeout)
    return exit_code


def main() -> None:
    try:
        settings = Settings.from_env()
        raise SystemExit(supervise(settings))
    except ValueError as exc:
        _log(f"configuration error: {exc}")
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
