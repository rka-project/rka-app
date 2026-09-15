from __future__ import annotations

import importlib.util
import io
import json
import tarfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ssh_smoke", REPO / "scripts/demo_ssh_smoke.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_tar(entries: dict[str, bytes]) -> io.BytesIO:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, value in entries.items():
            item = tarfile.TarInfo(name)
            item.size = len(value)
            archive.addfile(item, io.BytesIO(value))
    output.seek(0)
    return output


class SSHIdentityTests(unittest.TestCase):
    def test_private_and_public_build_identities_are_rejected(self):
        for suffix in ("rsa_key", "ecdsa_key.pub", "ed25519_key"):
            for prefix in ("", "./"):
                with self.subTest(suffix=suffix, prefix=prefix):
                    self.assertTrue(module.layer_has_host_keys(make_tar({
                        f"{prefix}etc/ssh/ssh_host_{suffix}": b"synthetic placeholder",
                    })))

    def test_configuration_and_keygen_binary_are_not_host_identities(self):
        self.assertFalse(module.layer_has_host_keys(make_tar({
            "etc/ssh/sshd_config": b"", "usr/bin/ssh-keygen": b"",
        })))

    def test_later_layer_deletion_cannot_hide_an_earlier_key(self):
        early = make_tar({"etc/ssh/ssh_host_rsa_key": b"synthetic placeholder"}).getvalue()
        later = make_tar({"etc/ssh/.wh.ssh_host_rsa_key": b""}).getvalue()
        archive = make_tar({
            "manifest.json": json.dumps([{"Layers": ["early.tar", "later.tar"]}]).encode(),
            "early.tar": early, "later.tar": later,
        })
        with self.assertRaisesRegex(ValueError, "containing SSH host key"):
            module.assert_no_layer_keys(archive)

    def test_clean_saved_image_layers_pass(self):
        archive = make_tar({
            "manifest.json": json.dumps([{"Layers": ["clean.tar"]}]).encode(),
            "clean.tar": make_tar({"etc/ssh/sshd_config": b""}).getvalue(),
        })
        module.assert_no_layer_keys(archive)

    def test_feature_order_startup_and_publication_gate_are_explicit(self):
        feature = REPO / ".devcontainer/features/ssh-host-identity"
        metadata = json.loads((feature / "devcontainer-feature.json").read_text())
        self.assertEqual(metadata["installsAfter"], ["ghcr.io/devcontainers/features/sshd"])
        install = (feature / "install.sh").read_text()
        self.assertIn("Refusing build-time SSH host identities", install)
        startup = (feature / "ssh-init.sh").read_text()
        self.assertIn("/usr/bin/ssh-keygen -A", startup)
        self.assertLess(startup.index("ssh-keygen -A"), startup.index("/etc/init.d/ssh start"))
        workflow = (REPO / ".github/workflows/demo-image.yml").read_text()
        self.assertLess(workflow.index("scripts/demo_ssh_smoke.py"), workflow.index("docker push"))


if __name__ == "__main__":
    unittest.main()
