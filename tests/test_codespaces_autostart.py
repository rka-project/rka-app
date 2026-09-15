from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from rka_app import codespaces_autostart as auto
from rka_app.codespaces import prepare_state
from rka_app.codespaces_privacy import PrivatePortGuard
from rka_app.demo_runtime import AlreadyRunning, run_demo
from rka_app.demo_seed import SHOWCASE, SeedError, write_receipt


class PrivacyTests(unittest.TestCase):
    def probe(self, ports, code=0):
        guard = PrivatePortGuard(
            "demo-1",
            {"HTTP_PROXY": "http://bad.invalid", "GH_TOKEN": "fixture-token", "GH_DEBUG": "api"},
        )
        with (
            patch("rka_app.codespaces_privacy.shutil.which", return_value="/usr/bin/gh"),
            patch(
                "rka_app.codespaces_privacy.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    [], code, json.dumps(ports).encode(), b"private"
                ),
            ) as execute,
        ):
            guard.check()
        return guard, execute

    def test_private_port_query_uses_exact_target_and_sanitized_environment(self):
        guard, execute = self.probe([{"sourcePort": 7860, "visibility": "private"}])
        self.assertEqual(
            execute.call_args.args[0],
            [
                "/usr/bin/gh",
                "codespace",
                "ports",
                "-c",
                "demo-1",
                "--json",
                "sourcePort,visibility",
            ],
        )
        self.assertNotIn("HTTP_PROXY", execute.call_args.kwargs["env"])
        self.assertEqual(execute.call_args.kwargs["env"]["GH_DEBUG"], "")
        self.assertEqual(execute.call_args.kwargs["timeout"], 15)
        self.assertIsNotNone(guard.last_verified)

    def test_public_org_absent_duplicate_and_invalid_results_are_refused(self):
        for ports in (
            [],
            [{"sourcePort": 7860, "visibility": "public"}],
            [{"sourcePort": 7860, "visibility": "org"}],
            [{"sourcePort": "7860", "visibility": "private"}],
            [{"sourcePort": 7860, "visibility": "private"}] * 2,
            {"sourcePort": 7860, "visibility": "private"},
        ):
            with self.subTest(ports=ports), self.assertRaises(SeedError):
                self.probe(ports)

    def test_auth_failure_is_not_echoed_or_treated_as_private(self):
        with self.assertRaisesRegex(SeedError, "requires authorized gh") as result:
            self.probe([], code=1)
        self.assertNotIn("fixture-token", str(result.exception))
        self.assertNotIn("private", str(result.exception))

    def test_missing_cli_timeout_malformed_and_oversized_output(self):
        guard = PrivatePortGuard("demo-1", {})
        with patch("rka_app.codespaces_privacy.shutil.which", return_value=None):
            with self.assertRaisesRegex(SeedError, "missing"):
                guard.check()
        for output in (b"not JSON", b" " * 65537):
            with (
                patch("rka_app.codespaces_privacy.shutil.which", return_value="/usr/bin/gh"),
                patch(
                    "rka_app.codespaces_privacy.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, output, b""),
                ),
                self.assertRaises(SeedError),
            ):
                guard.check()
        with (
            patch("rka_app.codespaces_privacy.shutil.which", return_value="/usr/bin/gh"),
            patch(
                "rka_app.codespaces_privacy.subprocess.run",
                side_effect=subprocess.TimeoutExpired("fixture", 15),
            ),
            self.assertRaisesRegex(SeedError, "Cannot verify"),
        ):
            guard.check()

    def test_interval_does_not_mask_later_public_visibility(self):
        guard, _ = self.probe([{"sourcePort": 7860, "visibility": "private"}])
        verified = guard.last_verified
        with (
            patch("rka_app.codespaces_privacy.time.monotonic", return_value=verified + 5),
            patch("rka_app.codespaces_privacy.subprocess.run") as execute,
        ):
            guard.check()
            execute.assert_not_called()
        with (
            patch("rka_app.codespaces_privacy.time.monotonic", return_value=verified + 31),
            patch("rka_app.codespaces_privacy.shutil.which", return_value="/usr/bin/gh"),
            patch(
                "rka_app.codespaces_privacy.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    [], 0, b'[{"sourcePort":7860,"visibility":"public"}]', b""
                ),
            ),
            self.assertRaisesRegex(SeedError, "not verified Private"),
        ):
            guard.check()


class AutoStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root_patch = patch.object(auto, "STATE_ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def state(self, enabled=True):
        state = prepare_state(self.root, "demo-1")
        write_receipt(
            state,
            {
                "format": 1,
                "codespace": "demo-1",
                "enabled": enabled,
                "sha256": SHOWCASE.sha256,
                "pack_path": str(self.root / "fixture.zip"),
            },
            filename=auto.CONFIG,
        )
        return state

    def test_no_opt_in_starts_nothing_and_does_not_create_state(self):
        with patch.object(auto.subprocess, "Popen") as spawn:
            self.assertIn("disabled", auto.start("demo-1"))
        spawn.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_disabled_record_does_not_spawn(self):
        self.state(enabled=False)
        with patch.object(auto.subprocess, "Popen") as spawn:
            self.assertIn("disabled", auto.start("demo-1"))
        spawn.assert_not_called()

    def test_unknown_state_and_corrupt_config_are_preserved(self):
        state = self.root / "demo-1"
        state.mkdir()
        with self.assertRaisesRegex(ValueError, "not owned"):
            auto.start("demo-1")
        self.assertEqual(list(state.iterdir()), [])

    def test_invalid_config_is_refused_without_spawn(self):
        state = self.state()
        (state / auto.CONFIG).write_text("broken fixture")
        with patch.object(auto.subprocess, "Popen") as spawn, self.assertRaises(SeedError):
            auto.start("demo-1")
        spawn.assert_not_called()
        self.assertEqual((state / auto.CONFIG).read_text(), "broken fixture")

    def test_privacy_failure_cannot_enable_or_create_namespace(self):
        with (
            patch.object(auto, "runtime_available"),
            patch.object(auto, "verified_pack"),
            patch.object(auto.PrivatePortGuard, "check", side_effect=SeedError("auth unavailable")),
            self.assertRaisesRegex(SeedError, "auth unavailable"),
        ):
            auto.configure("demo-1", self.root / "fixture.zip")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_enable_verifies_pack_and_privacy_before_writing_opt_in(self):
        with (
            patch.object(auto, "runtime_available"),
            patch.object(auto, "namespace_lock"),
            patch.object(auto, "verified_pack") as verify,
            patch.object(auto.PrivatePortGuard, "check") as privacy,
        ):
            state = auto.configure("demo-1", self.root / "fixture.zip")
        verify.assert_called_once_with(self.root / "fixture.zip", SHOWCASE)
        privacy.assert_called_once_with(force=True)
        self.assertTrue(auto.load_config(state, "demo-1")["enabled"])
        with self.assertRaises(SeedError):
            auto.load_config(state, "another-demo")

    @unittest.skipUnless(os.name == "posix", "Codespaces POSIX runtime")
    def test_existing_runtime_is_not_started_again(self):
        state = self.state()
        with (
            auto.namespace_lock(state),
            patch.object(auto, "runtime_available"),
            patch.object(auto.subprocess, "Popen") as spawn,
        ):
            self.assertIn("already running", auto.start("demo-1"))
        spawn.assert_not_called()

    def test_local_invocation_has_no_side_effects(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.argv", ["auto", "start"]),
            patch.object(auto, "start") as start,
            self.assertRaises(SystemExit) as result,
        ):
            auto.main()
        self.assertEqual(result.exception.code, 2)
        start.assert_not_called()

    def test_control_auth_is_not_leaked_to_core_environment(self):
        self.state()
        with (
            patch.dict(
                os.environ,
                {"CODESPACES": "true", "CODESPACE_NAME": "demo-1", "GITHUB_TOKEN": "fixture-token"},
                clear=True,
            ),
            patch.object(auto, "runtime_available"),
            patch.object(auto.os, "chdir"),
            patch.object(PrivatePortGuard, "wait_for_private"),
            patch.object(auto, "run_demo", return_value=0) as runtime,
        ):
            self.assertEqual(auto.run_managed("demo-1", "a" * 32), 0)
            self.assertNotIn("GITHUB_TOKEN", os.environ)
            self.assertEqual(
                runtime.call_args.kwargs["guard"].__self__.env["GITHUB_TOKEN"], "fixture-token"
            )

    def test_background_start_ignores_stale_status(self):
        self.state()
        child = MagicMock(pid=123)
        child.poll.side_effect = [None, None, 2, 2]
        with (
            patch.object(auto, "runtime_available"),
            patch.object(auto, "namespace_lock"),
            patch.object(auto, "is_running", return_value=False),
            patch.object(auto.subprocess, "Popen", return_value=child),
            patch.object(
                auto, "read_status", return_value={"launch_id": "old", "phase": "running"}
            ),
            patch.object(auto.time, "sleep"),
            self.assertRaisesRegex(SeedError, "failed"),
        ):
            auto.start("demo-1")
        child.terminate.assert_not_called()  # It already exited, not a PID from the stale receipt.

    def test_background_start_requires_its_own_running_receipt(self):
        self.state()
        child = MagicMock(pid=123)
        child.poll.return_value = None
        with (
            patch.object(auto, "runtime_available"),
            patch.object(auto, "namespace_lock"),
            patch.object(auto, "is_running", return_value=False),
            patch.object(auto.subprocess, "Popen", return_value=child) as spawn,
            patch.object(auto.uuid, "uuid4", return_value=MagicMock(hex="a" * 32)),
            patch.object(
                auto,
                "read_status",
                return_value={
                    "launch_id": "a" * 32,
                    "phase": "running",
                },
            ),
        ):
            self.assertTrue(auto.start("demo-1").startswith("running:"))
        self.assertTrue(spawn.call_args.kwargs["start_new_session"])
        self.assertEqual(spawn.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn("shell", spawn.call_args.kwargs)
        child.terminate.assert_not_called()

    def test_start_timeout_stops_only_the_spawned_child(self):
        self.state()
        child = MagicMock(pid=123)
        child.poll.return_value = None
        with (
            patch.object(auto, "runtime_available"),
            patch.object(auto, "namespace_lock"),
            patch.object(auto, "is_running", return_value=False),
            patch.object(auto.subprocess, "Popen", return_value=child),
            patch.object(auto, "read_status", return_value=None),
            patch.object(auto.time, "monotonic", side_effect=[0, 181]),
            self.assertRaisesRegex(SeedError, "timed out"),
        ):
            auto.start("demo-1")
        child.terminate.assert_called_once_with()
        child.wait.assert_called_once_with(timeout=60)

    def test_disable_preserves_data_and_does_not_signal_processes(self):
        state = self.state()
        sentinel = state / "user-edit.txt"
        sentinel.write_text("keep this fixture")
        with (
            patch.dict(os.environ, {"CODESPACES": "true", "CODESPACE_NAME": "demo-1"}),
            patch("sys.argv", ["auto", "disable"]),
            patch.object(auto, "namespace_lock"),
            patch.object(auto, "stop_owned_launch") as stop,
            patch.object(auto.os, "umask"),
        ):
            auto.main()
        self.assertFalse(auto.load_config(state, "demo-1")["enabled"])
        self.assertEqual(sentinel.read_text(), "keep this fixture")
        stop.assert_not_called()

    def test_privacy_guard_failure_reports_failure_without_launching_core(self):
        state = self.state()
        report = MagicMock()
        with (
            patch.dict(os.environ, {"RKA_HOST": "127.0.0.1", "RKA_PORT": "7860"}),
            patch("rka_app.demo_runtime.namespace_lock"),
            patch("rka_app.demo_runtime.supervise") as launch,
            self.assertRaisesRegex(SeedError, "not private"),
        ):
            run_demo(
                state, None, guard=MagicMock(side_effect=SeedError("not private")), report=report
            )
        launch.assert_not_called()
        self.assertEqual([c.args[0] for c in report.call_args_list], ["starting", "failed"])

    def test_new_status_document_cannot_overwrite_other_names(self):
        with self.assertRaisesRegex(SeedError, "Invalid App state"):
            write_receipt(self.root, {}, filename="rka.db")

    @unittest.skipUnless(os.name == "posix", "Codespaces POSIX runtime")
    def test_startup_lock_prevents_two_concurrent_launchers(self):
        state = self.state()
        with (
            auto.namespace_lock(state, filename=".startup.lock"),
            patch.object(auto, "runtime_available"),
            patch.object(auto.subprocess, "Popen") as spawn,
            self.assertRaises(AlreadyRunning),
        ):
            auto.start("demo-1")
        spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
