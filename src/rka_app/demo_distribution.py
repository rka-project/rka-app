"""Credential-free, checksum-pinned fictional sample distribution.

Publication is a separate reviewed release gate. Never use a URL supplied by a
visitor or fetch the historical development pack. No archive extraction.
"""

from __future__ import annotations

import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from rka_app.demo_seed import MAX_PACK_BYTES, SHOWCASE, SeedError, verified_pack

# Approved exact asset published and anonymously verified on 2026-09-15 UTC.
# This permits sample fetching, not public runtime release or automatic startup.
PUBLIC_SAMPLE_ENABLED = True
SAMPLE_URL = (
    "https://github.com/rka-project/rka-app/releases/download/"
    "demo-showcase-v1/rka-research-showcase.rka-pack.zip"
)
SAMPLE_FILENAME = "reviewed-showcase.rka-pack.zip"


def approved_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(url)
        return (
            parts.scheme == "https"
            and parts.username is None
            and parts.password is None
            and parts.port in (None, 443)
            and not parts.fragment
            and (url == SAMPLE_URL or parts.hostname == "release-assets.githubusercontent.com")
        )
    except ValueError:
        return False


class AssetRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not approved_url(newurl):
            raise SeedError("Sample redirect destination is not approved")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_sample(state: Path) -> Path:
    """Caller holds the startup lock; never overwrite a cached or user file."""
    if not PUBLIC_SAMPLE_ENABLED:
        raise SeedError("Public sample distribution has not been released")
    target = state / SAMPLE_FILENAME
    if target.exists() or target.is_symlink():
        verified_pack(target, SHOWCASE)
        return target
    if not state.is_absolute() or state.resolve() != state or not state.is_dir():
        raise SeedError("Invalid sample cache directory")
    # No environment proxies, Authorization, cookies, .netrc or GitHub CLI auth.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), AssetRedirect())
    request = urllib.request.Request(SAMPLE_URL, headers={"Accept": "application/octet-stream"})
    fd, name = tempfile.mkstemp(prefix=".sample-download-", dir=state)
    temporary = Path(name)
    try:
        deadline = time.monotonic() + 60
        with os.fdopen(fd, "wb") as output:
            with opener.open(request, timeout=10) as response:
                if response.status != 200 or not approved_url(response.url):
                    raise SeedError("Unexpected sample download response")
                size = 0
                while True:
                    if time.monotonic() >= deadline:
                        raise SeedError("Sample download exceeded its time budget")
                    block = response.read1(min(65536, MAX_PACK_BYTES + 1 - size))
                    if not block:
                        break
                    size += len(block)
                    if size > MAX_PACK_BYTES:
                        raise SeedError("Sample download exceeds size limit")
                    output.write(block)
            output.flush()
            os.fsync(output.fileno())
        verified_pack(temporary, SHOWCASE)
        # Atomic no-clobber publication on Codespaces' persistent filesystem.
        os.link(temporary, target)
        return target
    except (OSError, urllib.error.URLError) as exc:
        # Do not echo signed redirect URLs, response bodies or credentials.
        raise SeedError(
            "Sample download failed; existing data retained. Retry when online."
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)  # Only this invocation's exact temp file.
