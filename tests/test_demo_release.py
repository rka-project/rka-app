from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "render_config", REPO / "scripts/render_codespaces_config.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((REPO / ".devcontainer/image/devcontainer.json").read_text())

    def test_visitor_pulls_one_pinned_prebuilt_image_and_retains_privacy_policy(self):
        image = "ghcr.io/rka-project/rka-demo@sha256:" + "a" * 64
        result = module.render(image, self.config)
        self.assertEqual(result["image"], image)
        self.assertNotIn("build", result)
        self.assertNotIn("features", result)
        for key in (
            "remoteUser",
            "updateRemoteUserUID",
            "postStartCommand",
            "forwardPorts",
            "portsAttributes",
        ):
            self.assertEqual(result[key], self.config[key])

    def test_builder_and_operator_policy_do_not_drift(self):
        active = json.loads((REPO / ".devcontainer/devcontainer.json").read_text())
        if "image" in active:
            self.assertEqual(active, module.render(active["image"], self.config))
        else:
            self.assertEqual(
                {k: v for k, v in active.items() if k != "build"},
                {k: v for k, v in self.config.items() if k != "build"},
            )

    def test_image_publication_is_reviewed_and_tests_the_nonroot_runtime(self):
        workflow = (REPO / ".github/workflows/demo-image.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn('test "$EXPECTED_HEAD" = "$GITHUB_SHA"', workflow)
        self.assertIn("environment: demo-release", workflow)
        self.assertIn("push: never", workflow)
        self.assertIn("inheritEnv: false", workflow)
        self.assertIn("PUBLIC_SAMPLE_ENABLED and PUBLIC_DEMO_ENABLED", workflow)
        self.assertIn("--isolated-container", workflow)
        self.assertIn("--network none", workflow)
        self.assertIn("--user codespace", workflow)
        self.assertIn('test "$RUNNER_OS/$RUNNER_ARCH" = "Linux/X64"', workflow)
        self.assertNotIn("platform: linux/amd64", workflow)
        self.assertEqual(workflow.count("docker run --pull never"), 3)
        self.assertIn('docker image inspect "$DEMO_IMAGE"', workflow)
        self.assertIn("export PATH=/usr/local/bin:/usr/bin:/bin", workflow)
        self.assertIn("command -v gh", workflow)
        self.assertNotIn("test -x /usr/local/bin/gh", workflow)
        self.assertIn("-run-${{ github.run_id }}-${{ github.run_attempt }}", workflow)
        self.assertNotIn("rka-demo:latest", workflow)
        for line in workflow.splitlines():
            if "uses:" in line:
                self.assertRegex(line.rsplit("@", 1)[1], r"^[a-f0-9]{40}$")

    def test_tags_other_packages_and_unknown_policy_are_refused(self):
        for image in [
            "ghcr.io/rka-project/rka-demo:latest",
            "ghcr.io/rka-project/rka-core@sha256:" + "a" * 64,
            "ghcr.io/elsewhere/rka-demo@sha256:" + "a" * 64,
            "sha256:short",
        ]:
            with self.assertRaises(ValueError):
                module.render(image, self.config)
        with self.assertRaises(ValueError):
            module.render(
                "ghcr.io/rka-project/rka-demo@sha256:" + "a" * 64,
                {**self.config, "mounts": ["unreviewed"]},
            )


if __name__ == "__main__":
    unittest.main()
