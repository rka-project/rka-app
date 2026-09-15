"""Opt-in real CLI/REST smoke; only disposable state and ephemeral loopback ports.

Requires a released Core CLI and an explicitly supplied reviewed sample ZIP.
Never imports Core or opens its DB. Protected Docker runtime is read-only.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from rka_app.codespaces import demo_environment
from rka_app.demo_runtime import namespace_lock
from rka_app.demo_seed import SHOWCASE, CoreAPI, ensure_sample, verified_pack


def protected_snapshot() -> list[dict]:
    inventory = subprocess.run(
        ["docker", "ps", "--all", "--format", "{{.Names}}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    names = sorted(set(inventory.stdout.splitlines()) & {"rka-server", "rka-worker"})
    if not names:
        return []
    result = subprocess.run(
        ["docker", "inspect", *names],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    # Never print/store container environment, which may contain credentials.
    return [
        {
            "id": c["Id"],
            "image": c["Image"],
            "mounts": c["Mounts"],
            "started": c["State"]["StartedAt"],
            "status": c["State"]["Status"],
            "health": c["State"].get("Health", {}).get("Status"),
            "ports": c["NetworkSettings"]["Ports"],
        }
        for c in json.loads(result.stdout)
    ]


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-cli", type=Path, required=True)
    parser.add_argument("--sample-pack", type=Path, required=True)
    parser.add_argument(
        "--isolated-container",
        action="store_true",
        help="Run only in a disposable non-root Docker container; no host Docker socket",
    )
    parser.add_argument(
        "--sqlite-vec",
        type=Path,
        help="Optional existing sqlite-vec shared library for this test only",
    )
    args = parser.parse_args()
    if not args.core_cli.is_absolute() or not args.core_cli.is_file():
        parser.error("Supply an absolute released Core executable")
    _, expected_counts = verified_pack(args.sample_pack, SHOWCASE)
    if args.isolated_container and (
        not Path("/.dockerenv").is_file()
        or not hasattr(os, "geteuid")
        or os.geteuid() == 0
    ):
        parser.error("Isolated-container mode requires a non-root Docker container")
    baseline = None if args.isolated_container else protected_snapshot()
    try:
        with tempfile.TemporaryDirectory(prefix="rka-app-seed-smoke-") as directory:
            state = Path(directory).resolve()
            env = demo_environment(os.environ, state)
            # This test intentionally uses the installed public CLI, not image paths.
            env.pop("PYTHONPATH", None)
            env.pop("RKA_SQLITE_VEC_PATH", None)
            if args.sqlite_vec:
                if not args.sqlite_vec.is_absolute() or not args.sqlite_vec.is_file():
                    parser.error("sqlite-vec must be an absolute existing shared library")
                env["RKA_SQLITE_VEC_PATH"] = str(args.sqlite_vec)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            project_id = None
            for cycle in (1, 2):
                with socket.socket() as reserve:
                    reserve.bind(("127.0.0.1", 0))
                    port = reserve.getsockname()[1]
                api = CoreAPI(port)  # Refuses protected production ports.
                env["RKA_PORT"] = str(port)
                log_path = state / f"cycle-{cycle}.log"
                with namespace_lock(state), log_path.open("wb") as log:
                    server = subprocess.Popen(
                        [str(args.core_cli), "serve", "--host", "127.0.0.1", "--port", str(port)],
                        env=env,
                        cwd=state,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                    worker = None
                    try:
                        deadline = time.monotonic() + 60
                        while True:
                            if server.poll() is not None or time.monotonic() > deadline:
                                raise RuntimeError("Disposable Core did not become ready")
                            try:
                                if api.request("/api/health").get("status") == "ok":
                                    break
                            except ValueError:
                                time.sleep(0.2)

                        def import_with_diagnostics(pack, project_id, api=api):
                            result = CoreAPI.import_pack(api, pack, project_id)
                            if result.get("imported_counts") != expected_counts:
                                actual = result.get("imported_counts", {})
                                differences = {
                                    key: [expected_counts.get(key), actual.get(key)]
                                    for key in expected_counts.keys() | actual.keys()
                                    if expected_counts.get(key) != actual.get(key)
                                }
                                print("Sample count differences (expected, actual):", differences)
                            if result.get("integrity_issues"):
                                print(
                                    "Sample integrity categories:",
                                    [issue.get("category") for issue in result["integrity_issues"]],
                                )
                            return result

                        api.import_pack = import_with_diagnostics
                        imported = ensure_sample(api, state, args.sample_pack)
                        capabilities = api.request("/api/capabilities")
                        assert capabilities["schema_version"] == "rka.core-capabilities/v1"
                        assert capabilities["embedding"]["available"] is False
                        assert capabilities["embedding"]["search_mode"] == "lexical"
                        if cycle == 1:
                            project_id = imported
                        assert project_id == imported, "Restart changed imported project identity"
                        worker = subprocess.Popen(
                            [str(args.core_cli), "worker"],
                            env=env,
                            cwd=state,
                            stdout=log,
                            stderr=subprocess.STDOUT,
                        )
                        headers = {"X-RKA-Project": project_id, "Content-Type": "application/json"}

                        def scoped(path, *, data=None, method=None, api=api, headers=headers):
                            request = urllib.request.Request(
                                api.base + path,
                                data=data,
                                headers=headers,
                                method=method,
                            )
                            with api.opener.open(request, timeout=30) as response:
                                return response.read(8 * 1024 * 1024)

                        graph = json.loads(scoped("/api/graph?limit=2000"))
                        research_map = json.loads(scoped("/api/research-map"))
                        missions = json.loads(scoped("/api/missions?limit=200"))
                        matches = json.loads(
                            scoped(
                                "/api/search",
                                method="POST",
                                data=json.dumps(
                                    {
                                        "query": "calibration",
                                        "keyword_weight": 1,
                                        "semantic_weight": 0,
                                    }
                                ).encode(),
                            )
                        )
                        assert isinstance(matches, list) and matches, (
                            "Keyword search returned no data"
                        )
                        if cycle == 1:
                            initial = (graph, research_map, missions)
                            scoped(
                                "/api/status",
                                method="PUT",
                                data=json.dumps(
                                    {
                                        "summary": "[SYNTHETIC DEMO] smoke edit to preserve",
                                    }
                                ).encode(),
                            )
                        else:
                            assert initial == (graph, research_map, missions)
                            status = json.loads(scoped("/api/status"))
                            assert status["summary"].endswith("smoke edit to preserve")
                        archive_bytes = scoped("/api/projects/export")
                        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                            assert archive.testzip() is None
                            manifest = json.loads(archive.read("manifest.json"))
                        assert manifest["project"]["id"] == project_id
                        assert len(manifest["tables"]["missions"]) == 20
                        assert len(manifest["tables"]["claims"]) == 60
                        time.sleep(1)
                        assert worker.poll() is None, "Disposable worker exited"
                        print(
                            f"cycle {cycle}: Core {SHOWCASE.core_version}, lexical mode, "
                            "import/reuse, API views and export OK"
                        )
                    finally:
                        if worker is not None:
                            stop(worker)
                        stop(server)
    finally:
        if baseline is not None and protected_snapshot() != baseline:
            raise RuntimeError("Protected runtime snapshot changed; inspect independently")
    isolation = (
        "disposable non-root container" if baseline is None else "protected containers unchanged"
    )
    print(f"PASS: edited content survives restart; {isolation}")


if __name__ == "__main__":
    main()
