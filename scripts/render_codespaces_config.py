#!/usr/bin/env python3
"""Render (to stdout) a digest-only visitor template after image publication.

This performs no publication, repository edit or package-visibility change.
The prebuilt image must already contain the declared features/App code and have
passed non-root tests. Anonymous pull and visitor tests remain release gates.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def render(image: str, source: dict) -> dict:
    if not re.fullmatch(r"ghcr\.io/rka-project/rka-demo@sha256:[a-f0-9]{64}", image):
        raise ValueError("Use the reviewed rka-demo digest, never a tag or private Core image")
    if source.get("remoteUser") != "codespace" or source.get("forwardPorts") != [7860]:
        raise ValueError("Unexpected source user/port policy")
    allowed = {
        "name",
        "overrideCommand",
        "remoteUser",
        "updateRemoteUserUID",
        "postStartCommand",
        "customizations",
        "forwardPorts",
        "portsAttributes",
        "otherPortsAttributes",
    }
    if set(source) - allowed - {"build", "features"}:
        raise ValueError("Unexpected source configuration; review before rendering")
    # Features are already built into the image with devcontainer metadata.
    # Do not rebuild apt, Core or feature layers on the visitor's billed machine.
    return {"image": image, **{key: value for key, value in source.items() if key in allowed}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".devcontainer/image/devcontainer.json",
    )
    args = parser.parse_args()
    print(json.dumps(render(args.image, json.loads(args.source.read_text())), indent=2))


if __name__ == "__main__":
    main()
