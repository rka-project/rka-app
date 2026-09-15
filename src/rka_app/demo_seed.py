"""One-time, fail-closed sample import through released Core's public REST API.

No Core imports, database access, archive extraction, network downloads or reset.
The caller must hold the namespace lock for the entire runtime lifetime.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RECEIPT = "demo-seed.json"
MAX_PACK_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class Sample:
    sha256: str
    project_name: str
    source_project_id: str
    core_version: str = "3.0.0"


SHOWCASE = Sample(
    sha256="25f3b45396bdaa9dc3cff9d7a50c2e705204a8c6b2137cfb35927c6b2cc91a0f",
    project_name="UrbanHeat Research Showcase — SYNTHETIC DEMO",
    source_project_id="prj_01M2GSH6JN24MVDXBM56Q5Q3BM",
    core_version="3.0.1",
)


class SeedError(ValueError):
    """A safe refusal; retain all state for inspection."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SeedError("Core API redirects are refused")


class CoreAPI:
    """Only the adapter's loopback port; never use proxy or auth environment."""

    def __init__(self, port: int = 7860):
        if type(port) is not int or not 1 <= port <= 65535 or port in (9712, 9713):
            raise SeedError("Invalid or protected Core port")
        self.base = f"http://127.0.0.1:{port}"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(
        self, path: str, *, data: bytes | None = None, content_type: str | None = None
    ) -> Any:
        if not path.startswith("/api/") or any(c in path for c in "?#\\\r\n"):
            raise SeedError("Invalid Core API path")
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=30) as response:
                expected = 202 if data is not None else 200
                if response.status != expected:
                    raise SeedError("Unexpected Core API status")
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    raise SeedError("Core API response exceeds limit")
                return json.loads(payload)
        except urllib.error.HTTPError as exc:
            # Never echo response bodies, which may include user content.
            raise SeedError(f"Core API returned HTTP {exc.code}; state retained") from exc
        except (OSError, urllib.error.URLError, ValueError) as exc:
            raise SeedError("Core API request failed; state retained for inspection") from exc

    def import_pack(self, pack: bytes, project_id: str) -> Any:
        boundary = "rka-app-" + uuid.uuid4().hex
        body = (
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="project_id"\r\n'
                f"\r\n{project_id}\r\n--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="sample.rka-pack.zip"\r\n'
                "Content-Type: application/zip\r\n\r\n"
            ).encode()
            + pack
            + f"\r\n--{boundary}--\r\n".encode()
        )
        return self.request(
            "/api/projects/import",
            data=body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )


def read_regular(path: Path, limit: int) -> bytes:
    if not path.is_absolute() or path.resolve() != path:
        raise SeedError("Input path must be absolute and contain no symlinks")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise SeedError("Input must be a regular file")
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise SeedError("Input exceeds size limit")
    return payload


def verified_pack(path: Path, sample: Sample) -> tuple[bytes, dict[str, int]]:
    payload = read_regular(path, MAX_PACK_BYTES)
    if hashlib.sha256(payload).hexdigest() != sample.sha256:
        raise SeedError("Sample SHA-256 mismatch; no import attempted")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if archive.namelist() != ["manifest.json"]:
                raise SeedError("Sample must contain only manifest.json")
            if archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES:
                raise SeedError("Sample manifest exceeds size limit")
            manifest = json.loads(archive.read("manifest.json"))
        if (
            manifest["pack_format_version"] != 8
            or manifest["project"]["id"] != sample.source_project_id
            or manifest["project"]["name"] != sample.project_name
        ):
            raise SeedError("Sample identity or format mismatch")
        counts = {key: len(rows) for key, rows in manifest["tables"].items()}
        if not all(isinstance(rows, list) for rows in manifest["tables"].values()):
            raise SeedError("Malformed sample tables")
        if counts != manifest["table_counts"]:
            raise SeedError("Sample table counts mismatch")
        return payload, counts
    except (KeyError, TypeError, ValueError, zipfile.BadZipFile) as exc:
        raise SeedError("Invalid reviewed sample archive") from exc


def write_receipt(state: Path, receipt: dict[str, Any], *, filename: str = RECEIPT) -> None:
    """Replace only our own receipt, with a durable intent before the API write."""
    if filename not in {RECEIPT, "autostart.json", "runtime-status.json"}:
        raise SeedError("Invalid App state document")
    target = state / filename
    if target.is_symlink():
        raise SeedError("Receipt symlink refused")
    fd, name = tempfile.mkstemp(prefix=".seed-receipt-", dir=state)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
        if os.name == "posix":
            directory_fd = os.open(state, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temp.unlink(missing_ok=True)  # Only this function's exact temporary file.


def ensure_sample(api: CoreAPI, state: Path, pack_path: Path, sample: Sample = SHOWCASE) -> str:
    """Reuse a verified receipt, or import once. Never overwrite or auto-retry ambiguity."""
    health = api.request("/api/health")
    if not isinstance(health, dict) or (health.get("status"), health.get("version")) != (
        "ok",
        sample.core_version,
    ):
        raise SeedError("Core version/readiness does not match the pinned sample contract")
    projects = api.request("/api/projects")
    if not isinstance(projects, list) or not all(
        isinstance(project, dict) and isinstance(project.get("id"), str) for project in projects
    ):
        raise SeedError("Unexpected project-list contract")
    path = state / RECEIPT
    if path.exists() or path.is_symlink():
        try:
            receipt = json.loads(read_regular(path, 65536))
            if (
                receipt["format"] != 1
                or receipt["sha256"] != sample.sha256
                or not re.fullmatch(r"prj_demo_[a-f0-9]{32}", receipt["project_id"])
            ):
                raise SeedError("Receipt identity mismatch; existing data retained")
            if receipt["phase"] != "ready":
                raise SeedError("Previous import outcome is uncertain; inspect before retrying")
            if not any(p["id"] == receipt["project_id"] for p in projects):
                raise SeedError("Imported project is missing; automatic reimport refused")
            # Do not require the ZIP, rename, or recheck edited counts.
            return receipt["project_id"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise SeedError("Cannot validate seed receipt; existing data retained") from exc

    if any(p["id"] != "proj_default" for p in projects):
        raise SeedError("Existing projects without a seed receipt; automatic adoption refused")
    pack, counts = verified_pack(pack_path, sample)
    receipt = {
        "format": 1,
        "phase": "importing",
        "sha256": sample.sha256,
        "project_id": "prj_demo_" + uuid.uuid4().hex,
    }
    write_receipt(state, receipt)
    result = api.import_pack(pack, receipt["project_id"])
    # Core also reports empty installation-local tables omitted from the pack.
    # Missing/extra zero rows are equivalent; any nonzero mismatch is a failure.
    actual_counts = result.get("imported_counts") if isinstance(result, dict) else None
    counts_match = (
        isinstance(actual_counts, dict)
        and all(type(value) is int and value >= 0 for value in actual_counts.values())
        and {key: value for key, value in actual_counts.items() if value}
        == {key: value for key, value in counts.items() if value}
    )
    if not isinstance(result, dict) or (
        result.get("project_id") != receipt["project_id"]
        or result.get("source_project_id") != sample.source_project_id
        or result.get("project_name") != sample.project_name
        or not counts_match
        or result.get("integrity_issues") != []
    ):
        raise SeedError("Import result needs inspection; automatic retry refused")
    projects = api.request("/api/projects")
    if not isinstance(projects, list) or not any(
        isinstance(p, dict) and p.get("id") == receipt["project_id"] for p in projects
    ):
        raise SeedError("Imported project readback failed; automatic retry refused")
    receipt["phase"] = "ready"
    write_receipt(state, receipt)
    return receipt["project_id"]
