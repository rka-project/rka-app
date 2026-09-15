#!/usr/bin/env python3
"""Exercise RKA App against real Core without touching a live installation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LABEL_KEY = "org.rka.foundation0.run"
PROTECTED_NAMES = ("rka-server", "rka-worker")
PROTECTED_HEALTH_URL = "http://127.0.0.1:9712/api/health"


class SmokeFailure(RuntimeError):
    pass


def run(
    command: Sequence[str],
    *,
    check: bool = True,
    capture: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    return subprocess.run(
        command,
        check=check,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def optional_health(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            body = response.read()
            return {
                "reachable": True,
                "status": response.status,
                "sha256": hashlib.sha256(body).hexdigest(),
            }
    except (OSError, urllib.error.URLError) as exc:
        return {"reachable": False, "error_type": type(exc).__name__}


def protected_snapshot() -> dict[str, Any]:
    containers: dict[str, Any] = {}
    for name in PROTECTED_NAMES:
        result = run(("docker", "inspect", name), check=False, capture=True)
        if result.returncode != 0:
            containers[name] = None
            continue
        raw = json.loads(result.stdout)[0]
        containers[name] = {
            "id": raw["Id"],
            "image": raw["Image"],
            "status": raw["State"]["Status"],
            "mounts": sorted(
                (mount.get("Name") or mount.get("Source"), mount["Destination"])
                for mount in raw["Mounts"]
            ),
        }
    return {"containers": containers, "health": optional_health(PROTECTED_HEALTH_URL)}


def assert_clean_checkout(path: Path) -> str:
    commit = run(("git", "rev-parse", "HEAD"), capture=True, cwd=path).stdout.strip()
    status = run(("git", "status", "--porcelain"), capture=True, cwd=path).stdout
    if status:
        raise SmokeFailure(f"Core checkout must be clean for an attributable build: {path}")
    return commit


def inspect_label(kind: str, name: str, token: str) -> None:
    if kind in {"volume", "network"}:
        actual = run(
            (
                "docker",
                kind,
                "inspect",
                name,
                "--format",
                f"{{{{index .Labels {json.dumps(LABEL_KEY)}}}}}",
            ),
            capture=True,
        ).stdout.strip()
    else:
        noun = "image" if kind == "image" else "container"
        actual = run(
            (
                "docker",
                noun,
                "inspect",
                name,
                "--format",
                f"{{{{index .Config.Labels {json.dumps(LABEL_KEY)}}}}}",
            ),
            capture=True,
        ).stdout.strip()
    if actual != token:
        raise SmokeFailure(f"refusing to delete unowned {kind} {name!r}: label={actual!r}")


def wait_healthy(container: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = run(
            (
                "docker",
                "inspect",
                container,
                "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}",
            ),
            check=False,
            capture=True,
        )
        status = result.stdout.strip() if result.returncode == 0 else "missing"
        if status == "healthy":
            return
        if status == "unhealthy":
            logs = run(("docker", "logs", container), check=False, capture=True)
            raise SmokeFailure(f"container became unhealthy\n{logs.stdout}\n{logs.stderr}")
        time.sleep(1)
    logs = run(("docker", "logs", container), check=False, capture=True)
    raise SmokeFailure(f"health timeout\n{logs.stdout}\n{logs.stderr}")


def exec_json(container: str, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    script = """
import json, sys, urllib.request
method, path, raw = sys.argv[1:4]
data = raw.encode() if raw else None
request = urllib.request.Request(
    'http://127.0.0.1:7860' + path,
    data=data,
    method=method,
    headers={'Content-Type': 'application/json'},
)
with urllib.request.urlopen(request, timeout=20) as response:
    print(response.read().decode())
""".strip()
    raw = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
    result = run(
        ("docker", "exec", container, "python", "-c", script, method, path, raw),
        capture=True,
    )
    return json.loads(result.stdout)


def run_container(name: str, image: str, volume: str, token: str) -> None:
    run(
        (
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--label",
            f"{LABEL_KEY}={token}",
            "--network",
            f"{token}-network",
            "--mount",
            f"type=volume,src={volume},dst=/data",
            "--env",
            "RKA_PORT=7860",
            "--env",
            "RKA_EMBEDDINGS_ENABLED=false",
            image,
        ),
        capture=True,
    )


@dataclass
class Resources:
    token: str
    core_image: str
    app_image: str
    volume: str
    network: str
    containers: list[str]

    def cleanup(self) -> None:
        for name in reversed(self.containers):
            result = run(("docker", "inspect", name), check=False, capture=True)
            if result.returncode == 0:
                inspect_label("container", name, self.token)
                run(("docker", "rm", "-f", name))
        result = run(("docker", "volume", "inspect", self.volume), check=False, capture=True)
        if result.returncode == 0:
            inspect_label("volume", self.volume, self.token)
            run(("docker", "volume", "rm", self.volume))
        result = run(("docker", "network", "inspect", self.network), check=False, capture=True)
        if result.returncode == 0:
            inspect_label("network", self.network, self.token)
            run(("docker", "network", "rm", self.network))
        for image in (self.app_image, self.core_image):
            result = run(("docker", "image", "inspect", image), check=False, capture=True)
            if result.returncode == 0:
                inspect_label("image", image, self.token)
                run(("docker", "image", "rm", image))


def assert_clean_exit(container: str) -> None:
    exit_code = run(
        ("docker", "container", "inspect", container, "--format", "{{.State.ExitCode}}"),
        capture=True,
    ).stdout.strip()
    if exit_code != "0":
        logs = run(("docker", "logs", container), check=False, capture=True)
        raise SmokeFailure(
            f"container did not stop cleanly (exit={exit_code})\n{logs.stdout}\n{logs.stderr}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-source", type=Path, required=True)
    parser.add_argument(
        "--app-source",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    core_source = args.core_source.expanduser().resolve()
    app_source = args.app_source.expanduser().resolve()
    if core_source == app_source:
        raise SmokeFailure("Core and App must be separate checkouts")

    run(("docker", "version"), capture=True)
    core_commit = assert_clean_checkout(core_source)
    token = f"rka-app-f0-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    resources = Resources(
        token=token,
        core_image=f"rka-core-foundation0:{token}",
        app_image=f"rka-app-foundation0:{token}",
        volume=f"{token}-data",
        network=f"{token}-network",
        containers=[],
    )
    before = protected_snapshot()
    project_name = f"Foundation 0 {uuid.uuid4().hex[:8]}"
    report: dict[str, Any] | None = None

    try:
        run(
            (
                "docker",
                "build",
                "--label",
                f"{LABEL_KEY}={token}",
                "--tag",
                resources.core_image,
                str(core_source),
            )
        )
        run(
            (
                "docker",
                "build",
                "--build-arg",
                f"RKA_CORE_IMAGE={resources.core_image}",
                "--label",
                f"{LABEL_KEY}={token}",
                "--tag",
                resources.app_image,
                str(app_source),
            )
        )
        consumed_core = run(
            (
                "docker",
                "image",
                "inspect",
                resources.app_image,
                "--format",
                '{{index .Config.Labels "org.rka.core.image-ref"}}',
            ),
            capture=True,
        ).stdout.strip()
        if consumed_core != resources.core_image:
            raise SmokeFailure(f"derived image lost its Core provenance: {consumed_core!r}")
        run(
            (
                "docker",
                "volume",
                "create",
                "--label",
                f"{LABEL_KEY}={token}",
                resources.volume,
            ),
            capture=True,
        )
        run(
            (
                "docker",
                "network",
                "create",
                "--label",
                f"{LABEL_KEY}={token}",
                resources.network,
            ),
            capture=True,
        )

        first = f"{token}-first"
        resources.containers.append(first)
        run_container(first, resources.app_image, resources.volume, token)
        wait_healthy(first)
        process_table = run(("docker", "top", first), capture=True).stdout
        if "rka serve" not in process_table or "rka worker" not in process_table:
            raise SmokeFailure(f"server/worker process evidence missing:\n{process_table}")

        created = exec_json(
            first,
            "POST",
            "/api/projects",
            {"name": project_name, "description": "Disposable Foundation 0 persistence proof"},
        )
        project_id = created["id"]
        exec_json(first, "GET", "/api/projects")
        run(("docker", "stop", "--timeout", "20", first))
        assert_clean_exit(first)
        inspect_label("container", first, token)
        run(("docker", "rm", first))
        resources.containers.remove(first)

        second = f"{token}-second"
        resources.containers.append(second)
        run_container(second, resources.app_image, resources.volume, token)
        wait_healthy(second)
        projects = exec_json(second, "GET", "/api/projects")
        if not any(
            row.get("id") == project_id and row.get("name") == project_name for row in projects
        ):
            raise SmokeFailure("project did not survive container replacement")
        run(("docker", "stop", "--timeout", "20", second))
        assert_clean_exit(second)

        report = {
            "status": "pass",
            "core_commit": core_commit,
            "test_namespace": token,
            "published_host_ports": [],
            "worker_observed": True,
            "persistence_after_container_replacement": True,
            "protected_live_unchanged": True,
        }
    finally:
        try:
            resources.cleanup()
        finally:
            after = protected_snapshot()
            if before != after:
                raise SmokeFailure(
                    "protected live RKA changed during smoke:\n"
                    + json.dumps({"before": before, "after": after}, indent=2, sort_keys=True)
                )

    if report is None:
        raise SmokeFailure("smoke ended without a report")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"FOUNDATION 0 SMOKE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
