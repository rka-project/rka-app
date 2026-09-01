from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from rka_app.supervisor import Settings, _boolean, _health_ready, _port, _positive_float


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
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        fake_core = """
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

role = sys.argv[1]
if role == 'worker':
    raise SystemExit(7)
if role != 'serve':
    raise SystemExit(3)
port = int(sys.argv[sys.argv.index('--port') + 1])
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == '/api/health' else 404)
        self.end_headers()
    def log_message(self, _format, *args):
        return
ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
""".strip()

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            fake_path = Path(directory) / "fake_core.py"
            fake_path.write_text(fake_core, encoding="utf-8")
            env = {
                **os.environ,
                "PYTHONPATH": str(repo_root / "src"),
                "RKA_APP_RKA_COMMAND_JSON": json.dumps([sys.executable, str(fake_path)]),
                "RKA_HOST": "127.0.0.1",
                "RKA_PORT": str(port),
                "RKA_APP_STARTUP_TIMEOUT": "5",
                "RKA_APP_SHUTDOWN_TIMEOUT": "2",
                "RKA_APP_HEALTH_INTERVAL": "0.05",
            }
            result = subprocess.run(
                (sys.executable, "-m", "rka_app.supervisor"),
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
            )
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("worker exited unexpectedly with code 7", result.stderr)


if __name__ == "__main__":
    unittest.main()
