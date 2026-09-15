from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rka_app.codespaces import (
    CORE_CLI,
    MARKER,
    codespace_name,
    demo_environment,
    main,
    prepare_state,
)
from rka_app.demo_seed import SHOWCASE
from rka_app.supervisor import Settings


class CodespacesTests(unittest.TestCase):
    def test_only_explicit_codespace_environment_is_accepted(self) -> None:
        self.assertEqual(
            codespace_name({"CODESPACES": "true", "CODESPACE_NAME": "rka-demo-123"}),
            "rka-demo-123",
        )
        for env in (
            {},
            {"CODESPACES": "false", "CODESPACE_NAME": "rka-demo"},
            {"CODESPACES": "true", "CODESPACE_NAME": "../../live"},
            {"CODESPACES": "true", "CODESPACE_NAME": "/data"},
        ):
            with self.subTest(env=env), self.assertRaises(ValueError):
                codespace_name(env)

    def test_state_is_reused_only_with_matching_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "demo"
            state = prepare_state(root, "demo-1")
            sentinel = state / "existing-record.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            self.assertEqual(prepare_state(root, "demo-1"), state)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
            (state / MARKER).write_text('{"owner":"someone-else"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                prepare_state(root, "demo-1")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")

    def test_unknown_state_is_not_adopted_or_changed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = root / "demo-1"
            state.mkdir()
            with self.assertRaisesRegex(ValueError, "not owned"):
                prepare_state(root, "demo-1")
            self.assertEqual(list(state.iterdir()), [])

    def test_symlink_and_path_traversal_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            protected = root / "protected"
            protected.mkdir()
            try:
                (root / "demo-1").symlink_to(protected, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "symlink"):
                prepare_state(root, "demo-1")
            with self.assertRaisesRegex(ValueError, "symlink"):
                prepare_state(root / "demo-1", "demo-2")
            with self.assertRaisesRegex(ValueError, "Invalid"):
                prepare_state(root, "../protected")
            self.assertEqual(list(protected.iterdir()), [])

    def test_marker_symlink_and_corrupt_marker_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = prepare_state(root, "demo-1")
            marker = state / MARKER
            marker.write_text("invalid JSON", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Cannot validate"):
                prepare_state(root, "demo-1")
            marker.unlink()  # Only the exact temporary fixture created above.
            target = root / "other-marker"
            target.write_text("{}", encoding="utf-8")
            try:
                marker.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"Symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "not owned"):
                prepare_state(root, "demo-1")

    def test_inherited_local_settings_cannot_redirect_demo(self) -> None:
        original = {
            "RKA_DB_PATH": "/live/rka.db",
            "RKA_DATA_DIR": "/live",
            "RKA_PORT": "9712",
            "RKA_HOST": "0.0.0.0",
            "RKA_LLM_API_KEY": "fixture-not-a-real-secret",
            "RKA_APP_RKA_COMMAND": "unexpected-command",
            "RKA_APP_RKA_COMMAND_JSON": '["unexpected-command"]',
            "RKA_EMBEDDINGS_ENABLED": "true",
            "PYTHONPATH": "/untrusted",
            "PYTHONHOME": "/untrusted",
            "GITHUB_TOKEN": "fixture-not-a-real-token",
            "AWS_SECRET_ACCESS_KEY": "fixture-not-a-real-secret",
            "HTTP_PROXY": "http://example.invalid",
            "PATH": "/usr/bin",
        }
        state = Path("/workspaces/.rka-codespaces-demo/demo-1")
        env = demo_environment(original, state)
        self.assertNotIn("RKA_LLM_API_KEY", env)
        self.assertNotIn("RKA_APP_RKA_COMMAND", env)
        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertNotIn("HTTP_PROXY", env)
        self.assertEqual(env["RKA_EMBEDDINGS_ENABLED"], "false")
        self.assertEqual(env["RKA_LLM_ENABLED"], "false")
        self.assertEqual(env["RKA_SERVER_FILE_ROOTS"], "[]")
        self.assertEqual(env["PYTHONPATH"], "/opt/rka-app")
        self.assertEqual(env["RKA_DB_PATH"], str(state / "rka.db"))
        self.assertEqual(original["RKA_DB_PATH"], "/live/rka.db")
        with patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env()
        self.assertEqual(
            settings.server_command,
            (
                str(CORE_CLI),
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                "7860",
            ),
        )

    def test_launch_without_confirmation_has_no_side_effects(self) -> None:
        with (
            patch.dict(os.environ, {"CODESPACES": "true", "CODESPACE_NAME": "demo-1"}),
            patch("sys.argv", ["codespaces"]),
            patch("rka_app.codespaces.prepare_state") as prepare,
            patch("rka_app.codespaces.run_demo") as execute,
            self.assertRaises(SystemExit) as result,
        ):
            main()
        self.assertEqual(result.exception.code, 2)
        prepare.assert_not_called()
        execute.assert_not_called()

    def test_local_launch_with_confirmation_still_has_no_side_effects(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.argv", ["codespaces", "--confirm-private-port"]),
            patch("rka_app.codespaces.prepare_state") as prepare,
            patch("rka_app.codespaces.run_demo") as execute,
            self.assertRaises(SystemExit) as result,
        ):
            main()
        self.assertEqual(result.exception.code, 2)
        prepare.assert_not_called()
        execute.assert_not_called()

    def test_launch_uses_runtime_cwd_and_controlled_supervisor_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            runtime = root / "python-fixture"
            runtime.touch()
            with (
                patch.dict(os.environ, {"CODESPACES": "true", "CODESPACE_NAME": "demo-1"}),
                patch("sys.argv", ["codespaces", "--confirm-private-port"]),
                patch("rka_app.codespaces.RUNTIME", runtime),
                patch("rka_app.codespaces.CORE_CLI", runtime),
                patch("rka_app.codespaces.RUNTIME_CWD", root),
                patch("rka_app.codespaces.STATE_ROOT", root / "data"),
                patch("rka_app.codespaces.os.umask"),
                patch("rka_app.codespaces.os.chdir") as chdir,
                patch("rka_app.codespaces.run_demo", return_value=0) as execute,
                self.assertRaises(SystemExit) as result,
            ):
                main()
            self.assertEqual(result.exception.code, 0)
            chdir.assert_called_once_with(root)
            execute.assert_called_once_with(root / "data/demo-1", None)

    def test_devcontainer_uses_opt_in_adapter_and_forwards_only_demo_port(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        config = json.loads((repo / ".devcontainer/image/devcontainer.json").read_text())
        self.assertTrue(config["overrideCommand"])
        self.assertEqual(config["forwardPorts"], [7860])
        self.assertEqual(
            config["postStartCommand"],
            [
                "/app/.venv/bin/python",
                "-m",
                "rka_app.codespaces_bootstrap",
            ],
        )
        self.assertEqual(
            config["features"]["ghcr.io/devcontainers/features/github-cli:1.1.2"],
            {"version": "2.98.0"},
        )
        self.assertNotIn("mounts", config)
        self.assertEqual(config["remoteUser"], "codespace")
        self.assertTrue(config["updateRemoteUserUID"])
        self.assertEqual(
            config["features"]["ghcr.io/devcontainers/features/common-utils:2.5.9"]["userUid"],
            "1000",
        )
        dockerfile = (repo / ".devcontainer/Dockerfile").read_text()
        self.assertEqual(SHOWCASE.core_version, "3.0.1")
        self.assertIn(
            "@sha256:19a7ac4098e536930d395a1730ad5b57b082f769e784b40221312bc93cad00f7",
            dockerfile,
        )
        self.assertIn('CMD ["sleep", "infinity"]', dockerfile)
        self.assertNotIn("COPY . ", dockerfile)

    @unittest.skipUnless(os.name == "posix", "OS ownership applies on Codespaces")
    def test_wrong_os_owner_and_insecure_existing_modes_are_not_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            state = prepare_state(root, "demo-1")
            before = (state / MARKER).read_bytes()
            with patch("rka_app.codespaces.os.geteuid", return_value=os.geteuid() + 1):
                with self.assertRaisesRegex(ValueError, "different OS user"):
                    prepare_state(root, "demo-1")
            state.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "not private"):
                prepare_state(root, "demo-1")
            self.assertEqual((state / MARKER).read_bytes(), before)
            self.assertEqual(state.stat().st_mode & 0o777, 0o755)


if __name__ == "__main__":
    unittest.main()
