from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from rka_app.demo_runtime import namespace_lock, run_demo
from rka_app.demo_seed import (
    RECEIPT,
    CoreAPI,
    NoRedirect,
    Sample,
    SeedError,
    ensure_sample,
    read_regular,
    verified_pack,
)


class SeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name).resolve()
        self.pack = self.state / "fixture.zip"
        manifest = {
            "pack_format_version": 8,
            "project": {"id": "prj_fixture", "name": "SYNTHETIC DEMO"},
            "tables": {"journal": []},
            "table_counts": {"journal": 0},
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
        self.payload = buffer.getvalue()
        self.pack.write_bytes(self.payload)
        self.sample = Sample(
            hashlib.sha256(self.payload).hexdigest(), "SYNTHETIC DEMO", "prj_fixture"
        )
        self.projects = [{"id": "proj_default"}]
        self.api = MagicMock(spec=CoreAPI)

        def request(path: str):
            if path == "/api/health":
                return {"status": "ok", "version": "3.0.0"}
            self.assertEqual(path, "/api/projects")
            return list(self.projects)

        def import_pack(payload: bytes, project_id: str):
            self.assertEqual(payload, self.payload)
            intent = json.loads((self.state / RECEIPT).read_text())
            self.assertEqual(intent["phase"], "importing")
            self.assertEqual(intent["project_id"], project_id)
            self.projects.append({"id": project_id})
            return {
                "project_id": project_id,
                "project_name": self.sample.project_name,
                "source_project_id": self.sample.source_project_id,
                "imported_counts": {"journal": 0},
                "integrity_issues": [],
            }

        self.api.request.side_effect = request
        self.api.import_pack.side_effect = import_pack

    def seed(self):
        return ensure_sample(self.api, self.state, self.pack, self.sample)

    def test_one_import_then_reuse_even_if_zip_missing_or_project_renamed(self):
        project_id = self.seed()
        self.pack.unlink()  # Exact temporary fixture, not a real sample.
        self.projects[-1]["name"] = "my changed project"
        self.assertEqual(self.seed(), project_id)
        self.api.import_pack.assert_called_once()

    def test_uncertain_import_is_never_retried(self):
        self.api.import_pack.side_effect = TimeoutError("fixture timeout")
        with self.assertRaises(TimeoutError):
            self.seed()
        with self.assertRaisesRegex(SeedError, "uncertain"):
            self.seed()
        self.api.import_pack.assert_called_once()

    def test_readback_failure_keeps_intent_not_ready(self):
        self.api.request.side_effect = [
            {"status": "ok", "version": "3.0.0"},
            list(self.projects),
            [],
        ]
        with self.assertRaisesRegex(SeedError, "readback failed"):
            self.seed()
        self.assertEqual(json.loads((self.state / RECEIPT).read_text())["phase"], "importing")

    def test_integrity_warning_or_bad_result_is_not_declared_ready(self):
        self.api.import_pack.side_effect = None
        for response in ({}, [], {"project_id": "wrong"}):
            self.api.import_pack.return_value = response
            with self.assertRaisesRegex(SeedError, "needs inspection"):
                self.seed()
            (self.state / RECEIPT).unlink()  # Remove only this failed temporary fixture.

    def test_missing_project_is_not_recreated(self):
        self.seed()
        self.projects.pop()
        with self.assertRaisesRegex(SeedError, "missing"):
            self.seed()
        self.api.import_pack.assert_called_once()

    def test_existing_projects_without_receipt_are_not_adopted(self):
        self.projects.append({"id": "prj_existing"})
        with self.assertRaisesRegex(SeedError, "adoption refused"):
            self.seed()
        self.api.import_pack.assert_not_called()
        self.assertFalse((self.state / RECEIPT).exists())

    def test_bad_hash_cannot_write_intent_or_call_import(self):
        self.pack.write_bytes(b"not the pinned pack")
        with self.assertRaisesRegex(SeedError, "SHA-256"):
            self.seed()
        self.api.import_pack.assert_not_called()
        self.assertFalse((self.state / RECEIPT).exists())

    def test_wrong_core_version_cannot_import(self):
        self.api.request.side_effect = None
        self.api.request.return_value = {"status": "ok", "version": "2.8.1"}
        with self.assertRaisesRegex(SeedError, "version"):
            self.seed()
        self.api.import_pack.assert_not_called()

    def test_extra_empty_core_tables_are_allowed_but_nonzero_rows_are_not(self):
        original = self.api.import_pack.side_effect

        def with_empty_tables(pack, project_id):
            result = original(pack, project_id)
            result["imported_counts"]["audit_log"] = 0
            return result

        self.api.import_pack.side_effect = with_empty_tables
        self.seed()
        self.assertEqual(json.loads((self.state / RECEIPT).read_text())["phase"], "ready")

    def test_unexpected_nonzero_rows_and_integrity_warnings_fail_closed(self):
        original = self.api.import_pack.side_effect

        def with_warning(pack, project_id):
            result = original(pack, project_id)
            result["integrity_issues"] = [{"category": "index_check_incomplete"}]
            return result

        self.api.import_pack.side_effect = with_warning
        with self.assertRaisesRegex(SeedError, "inspection"):
            self.seed()
        self.assertEqual(json.loads((self.state / RECEIPT).read_text())["phase"], "importing")

    def test_extra_nonzero_count_is_refused(self):
        original = self.api.import_pack.side_effect

        def with_extra_rows(pack, project_id):
            result = original(pack, project_id)
            result["imported_counts"]["audit_log"] = 1
            return result

        self.api.import_pack.side_effect = with_extra_rows
        with self.assertRaisesRegex(SeedError, "inspection"):
            self.seed()

    @unittest.skipUnless(os.name == "posix", "POSIX FIFO")
    def test_fifo_is_refused_without_blocking(self):
        fifo = self.state / "pipe"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(SeedError, "regular file"):
            read_regular(fifo, 100)

    def test_corrupt_receipt_is_not_replaced(self):
        target = self.state / RECEIPT
        target.write_text("invalid json")
        with self.assertRaisesRegex(SeedError, "Cannot validate"):
            self.seed()
        self.assertEqual(target.read_text(), "invalid json")
        self.api.import_pack.assert_not_called()

    def test_input_limit_and_relative_paths(self):
        with self.assertRaisesRegex(SeedError, "size limit"):
            read_regular(self.pack, 2)
        with self.assertRaisesRegex(SeedError, "absolute"):
            read_regular(Path("fixture.zip"), 100)

    def test_archive_with_extra_path_cannot_be_imported(self):
        with zipfile.ZipFile(self.pack, "a") as archive:
            archive.writestr("../../extra", "bad")
        sample = Sample(hashlib.sha256(self.pack.read_bytes()).hexdigest(), "unused", "unused")
        with self.assertRaises(SeedError):
            verified_pack(self.pack, sample)

    @unittest.skipUnless(os.name == "posix", "Codespaces POSIX runtime")
    def test_receipt_and_pack_symlinks_are_refused(self):
        link = self.state / RECEIPT
        link.symlink_to(self.pack)
        with self.assertRaisesRegex(SeedError, "symlinks"):
            self.seed()
        self.assertEqual(self.pack.read_bytes(), self.payload)
        with self.assertRaisesRegex(SeedError, "symlinks"):
            verified_pack(link, self.sample)


class BoundaryTests(unittest.TestCase):
    def test_protected_ports_and_redirects_refused(self):
        for port in (9712, 9713, 0, 65536, True):
            with self.assertRaises(SeedError):
                CoreAPI(port)
        with self.assertRaisesRegex(SeedError, "redirects"):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")
        with self.assertRaisesRegex(SeedError, "path"):
            CoreAPI().request("https://example.invalid")

    def test_http_client_bounds_body_and_ignores_proxy(self):
        with patch.dict(os.environ, {"HTTP_PROXY": "http://fixture.invalid"}):
            api = CoreAPI(17860)
        # ProxyHandler({}) registers no proxy handlers; default env proxies absent.
        self.assertFalse(
            any(isinstance(h, urllib.request.ProxyHandler) for h in api.opener.handlers)
        )
        response = MagicMock()
        response.status = 200
        response.read.return_value = b"{}"
        with patch.object(api.opener, "open") as opened:
            opened.return_value.__enter__.return_value = response
            self.assertEqual(api.request("/api/health"), {})
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:17860/api/health")
        self.assertNotIn("Authorization", request.headers)

    @unittest.skipUnless(os.name == "posix", "Codespaces POSIX runtime")
    def test_lock_prevents_parallel_launch_and_recovers_on_release(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory).resolve()
            with namespace_lock(state):
                with self.assertRaisesRegex(SeedError, "already running"):
                    with namespace_lock(state):
                        self.fail("Second lock acquired")
            with namespace_lock(state):
                pass

    def test_occupied_port_does_not_launch_or_seed(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"RKA_HOST": "127.0.0.1", "RKA_PORT": "7860"}),
            patch("rka_app.demo_runtime.namespace_lock"),
            patch("rka_app.demo_runtime.socket.socket") as socket,
            patch("rka_app.demo_runtime.supervise") as launch,
        ):
            socket.return_value.__enter__.return_value.bind.side_effect = OSError("in use")
            with self.assertRaisesRegex(SeedError, "occupied"):
                run_demo(Path(directory), None)
            launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
