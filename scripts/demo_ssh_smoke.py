#!/usr/bin/env python3
"""Check a CI-only demo image for baked SSH keys and unique startup identities.

Only disposable, network-disabled containers are started. No ports, volumes,
credentials or real Codespaces are used; private key contents are never read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tarfile
import tempfile

KEY_PATH = re.compile(r"^etc/ssh/ssh_host_[^/]+_key(?:\.pub)?$")


def layer_has_host_keys(payload) -> bool:
    with tarfile.open(fileobj=payload, mode="r|*") as layer:
        return any(KEY_PATH.fullmatch(item.name.removeprefix("./")) for item in layer)


def assert_no_layer_keys(archive_file) -> None:
    with tarfile.open(fileobj=archive_file, mode="r:*") as archive:
        manifests = json.load(archive.extractfile("manifest.json"))
        if len(manifests) != 1 or not manifests[0]["Layers"]:
            raise ValueError("Expected exactly one saved image with explicit layers")
        for name in manifests[0]["Layers"]:
            with archive.extractfile(name) as layer:
                if layer_has_host_keys(layer):
                    raise ValueError("Refusing an image layer containing SSH host key files")


def docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], check=True, text=True, capture_output=True, timeout=180
    ).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--run-label", required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("This root/SSH smoke is restricted to disposable GitHub Actions runners")
    if not re.fullmatch(r"[0-9]+-[0-9]+", args.run_label):
        parser.error("Expected the Actions run-attempt identifier")
    if not re.fullmatch(
        r"ghcr\.io/rka-project/rka-demo:sha-[a-f0-9]{40}-run-" + args.run_label, args.image
    ):
        parser.error("Use only this run's uniquely tagged local demo image")

    # Inspect saved layer directory entries, without extracting any file or
    # reading key contents. A later whiteout does not hide a key in an old layer.
    with tempfile.TemporaryFile() as archive:
        subprocess.run(
            ["docker", "image", "save", args.image], stdout=archive, check=True, timeout=180
        )
        archive.seek(0)
        assert_no_layer_keys(archive)
    print("PASS: no SSH host key files in any published image layer")

    fingerprints = []
    for cycle in (1, 2):
        result = docker(
            "run", "--pull", "never", "--rm", "--network", "none", "--user", "root",
            "--label", f"org.rka.demo.ci={args.run_label}-ssh-{cycle}",
            "--entrypoint", "/bin/bash", args.image, "-c", r'''
set -euo pipefail
test -z "$(find /etc/ssh -maxdepth 1 -name 'ssh_host_*_key*' -print)"
/usr/local/share/ssh-init.sh /bin/true
fingerprint() {
    /usr/bin/ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub | /usr/bin/awk '{print $2}'
}
before="$(fingerprint)"
/usr/local/share/ssh-init.sh /bin/true
test "$before" = "$(fingerprint)"
effective="$(/usr/sbin/sshd -T)"
grep -Fxq 'passwordauthentication no' <<< "$effective"
grep -Fxq 'kbdinteractiveauthentication no' <<< "$effective"
grep -Fxq 'gatewayports no' <<< "$effective"
printf 'PUBLIC_IDENTITY=%s\n' "$before"
''',
        )
        lines = [line for line in result.splitlines() if line.startswith("PUBLIC_IDENTITY=")]
        if len(lines) != 1 or not re.fullmatch(r"PUBLIC_IDENTITY=SHA256:[A-Za-z0-9+/]+", lines[0]):
            raise ValueError("Missing unique public fingerprint readback")
        fingerprints.append(lines[0])
    if fingerprints[0] == fingerprints[1]:
        raise ValueError("Separate containers reused one SSH host identity")
    print("PASS: distinct container identities; repeat startup retains keys; SSH policy unchanged")


if __name__ == "__main__":
    main()
