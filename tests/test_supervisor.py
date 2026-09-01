from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, call, patch

from rka_app.supervisor import (
    Settings,
    _boolean,
    _health_ready,
    _port,
    _positive_float,
    supervise,
)


class QuietHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        status = 200 if self.path == "/api/health" else 404
        self.send_response(status)
        self.end_headers()

    def log_message(self, _format: str, *args: object) -> None:
        return


class SettingsTests(unittest.TestCase):
    def test_defaults_match_single_container_contract(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 7860)
        self.assertTrue(settings.worker_enabled)
        self.assertEqual(
            settings.server_command,
            ("rka", "serve", "--host", "0.0.0.0", "--port", "7860"),
        )
        self.assertEqual(settings.worker_command, ("rka", "worker"))

    def test_explicit_command_prefix_and_worker_disable(self) -> None:
        env = {
            "RKA_APP_RKA_COMMAND_JSON": json.dumps(["python", "-m", "fake_rka"]),
            "RKA_APP_WORKER_ENABLED": "false",
            "RKA_HOST": "127.0.0.1",
            "RKA_PORT": "12345",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env()
        self.assertFalse(settings.worker_enabled)
        self.assertEqual(settings.command_prefix, ("python", "-m", "fake_rka"))
        self.assertEqual(settings.health_url, "http://127.0.0.1:12345/api/health")

    def test_invalid_values_fail_closed(self) -> None:
        with patch.dict(os.environ, {"FLAG": "perhaps"}, clear=True):
            with self.assertRaisesRegex(ValueError, "must be true or false"):
                _boolean("FLAG", True)
        with patch.dict(os.environ, {"SECONDS": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "greater than zero"):
                _positive_float("SECONDS", 1.0)
        with patch.dict(os.environ, {"PORT": "70000"}, clear=True):
            with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
                _port("PORT", 7860)


class HealthTests(unittest.TestCase):
    def test_health_probe_requires_success_status(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            hostile_proxy = {
                "HTTP_PROXY": "http://127.0.0.1:9",
                "HTTPS_PROXY": "http://127.0.0.1:9",
                "NO_PROXY": "",
            }
            with patch.dict(os.environ, hostile_proxy, clear=False):
                self.assertTrue(_health_ready(f"http://127.0.0.1:{port}/api/health"))
                self.assertFalse(_health_ready(f"http://127.0.0.1:{port}/missing"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class LifecycleTests(unittest.TestCase):
    def test_worker_failure_stops_server_and_propagates_code(self) -> None:
        settings = Settings(
            host="127.0.0.1",
            port=17860,
            worker_enabled=True,
            startup_timeout=1,
            shutdown_timeout=2,
            health_interval=0.001,
            command_prefix=("rka",),
        )
        server = MagicMock(pid=101)
        server.poll.return_value = None
        worker = MagicMock(pid=102)
        worker.poll.return_value = 7

        with (
            patch("rka_app.supervisor.signal.signal"),
            patch("rka_app.supervisor._health_ready", return_value=True),
            patch("rka_app.supervisor._start", side_effect=[server, worker]),
            patch("rka_app.supervisor._stop") as stop,
        ):
            exit_code = supervise(settings)

        self.assertEqual(exit_code, 7)
        stop.assert_has_calls(
            [
                call(worker, "worker", settings.shutdown_timeout),
                call(server, "server", settings.shutdown_timeout),
            ]
        )


if __name__ == "__main__":
    unittest.main()
