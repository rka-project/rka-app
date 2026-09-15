from __future__ import annotations

import importlib.util
import json
import tomllib
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
        self.assertNotIn("postStartCommand", result)
        for key in (
            "remoteUser",
            "updateRemoteUserUID",
            "forwardPorts",
            "portsAttributes",
        ):
            self.assertEqual(result[key], self.config[key])

    def test_active_visitor_uses_the_reviewed_image_and_matches_builder_policy(self):
        active = json.loads((REPO / ".devcontainer/devcontainer.json").read_text())
        self.assertEqual(
            active["image"],
            "ghcr.io/rka-project/rka-demo@sha256:"
            "aabf3c5f04ec01bc5adc3c31d9634e4db2f299c3b375fdddeddb5bd8ad7b14ae",
        )
        self.assertEqual(active, module.render(active["image"], self.config))

    def test_bootstrap_is_inherited_once_and_unexpected_hooks_are_refused(self):
        active = json.loads((REPO / ".devcontainer/devcontainer.json").read_text())
        # Dev Containers collects lifecycle hooks from the image and config.
        hooks = [entry["postStartCommand"] for entry in [self.config, active]
                 if "postStartCommand" in entry]
        self.assertEqual(hooks, [self.config["postStartCommand"]])
        for command in (None, "echo unreviewed", ["another", "command"]):
            with self.subTest(command=command), self.assertRaises(ValueError):
                module.render(active["image"], {**self.config, "postStartCommand": command})
        with self.assertRaises(ValueError):
            module.render(active["image"], {**self.config, "postCreateCommand": "unreviewed"})

    def test_published_consumer_ci_is_anonymous_and_uses_installed_runtime(self):
        workflow = (REPO / ".github/workflows/test.yml").read_text().split(
            "  published-demo-consumer:", 1
        )[1]
        active = json.loads((REPO / ".devcontainer/devcontainer.json").read_text())
        self.assertIn(f"DEMO_IMAGE: {active['image']}", workflow)
        self.assertIn('DOCKER_CONFIG=$RUNNER_TEMP/rka-demo-anonymous', workflow)
        self.assertNotIn("${{ runner.", workflow.split("    steps:", 1)[0])
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("login-action", workflow)
        self.assertNotIn("packages: write", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn('docker pull "$DEMO_IMAGE"', workflow)
        self.assertIn("--include-merged-configuration", workflow)
        self.assertIn('merged["postStartCommands"] == [builder["postStartCommand"]]', workflow)
        self.assertIn("--network none", workflow)
        self.assertIn("--user codespace", workflow)
        self.assertIn("--isolated-container", workflow)
        self.assertNotIn("PYTHONPATH=/verify/src", workflow)
        for line in workflow.splitlines():
            if "uses:" in line:
                self.assertRegex(line.rsplit("@", 1)[1], r"^[a-f0-9]{40}$")

    def test_app_provenance_does_not_inherit_the_core_revision(self):
        dockerfile = (REPO / ".devcontainer/Dockerfile").read_text()
        project = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]
        self.assertIn(f'org.opencontainers.image.version="{project["version"]}"', dockerfile)
        self.assertIn('org.opencontainers.image.revision="${RKA_APP_REVISION}"', dockerfile)
        self.assertEqual(
            self.config["build"]["args"]["RKA_APP_REVISION"],
            "${localEnv:GITHUB_SHA:unreleased}",
        )
        workflow = (REPO / ".github/workflows/demo-image.yml").read_text()
        self.assertIn('org.opencontainers.image.revision"}}\')" = "$GITHUB_SHA"', workflow)

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
