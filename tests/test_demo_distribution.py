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

from rka_app import codespaces_autostart as auto
from rka_app import codespaces_bootstrap as boot
from rka_app import demo_distribution as dist
from rka_app.codespaces import MARKER, prepare_state
from rka_app.codespaces_privacy import PortNotRegistered, PrivatePortGuard
from rka_app.demo_seed import SHOWCASE, Sample, SeedError, write_receipt


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name).resolve()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "pack_format_version": 8,
                        "project": {"id": "prj_fixture", "name": "SYNTHETIC DEMO"},
                        "tables": {"journal": []},
                        "table_counts": {"journal": 0},
                    }
                ),
            )
        self.payload = buffer.getvalue()
        self.sample = Sample(
            hashlib.sha256(self.payload).hexdigest(), "SYNTHETIC DEMO", "prj_fixture"
        )

    def download(self, payload=None, status=200, url=dist.SAMPLE_URL):
        response = MagicMock(status=status, url=url)
        response.read1.side_effect = io.BytesIO(self.payload if payload is None else payload).read1
        response.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = response
        with (
            patch.object(dist, "PUBLIC_SAMPLE_ENABLED", True),
            patch.object(dist, "SHOWCASE", self.sample),
            patch.object(dist.urllib.request, "build_opener", return_value=opener) as build,
        ):
            result = dist.download_sample(self.state)
        return result, opener, build

    def test_disabled_release_does_not_download_or_write(self):
        with (
            patch.object(dist, "PUBLIC_SAMPLE_ENABLED", False),
            patch.object(dist.urllib.request, "build_opener") as build,
            self.assertRaises(SeedError),
        ):
            dist.download_sample(self.state)
        build.assert_not_called()
        self.assertEqual(list(self.state.iterdir()), [])

    def test_verified_download_and_cached_reuse_without_credentials(self):
        with patch.dict(
            os.environ, {"GH_TOKEN": "fixture-secret", "HTTPS_PROXY": "http://bad.invalid"}
        ):
            path, opener, build = self.download()
        self.assertEqual(path.read_bytes(), self.payload)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, dist.SAMPLE_URL)
        self.assertEqual(request.headers, {"Accept": "application/octet-stream"})
        self.assertEqual(build.call_args.args[0].proxies, {})
        path, opener, _ = self.download()
        opener.open.assert_not_called()
        self.assertEqual(list(self.state.iterdir()), [path])

    def test_corruption_truncation_oversize_http_and_final_url_refused(self):
        for payload, status, url in [
            (b"wrong", 200, dist.SAMPLE_URL),
            (self.payload[:-1], 200, dist.SAMPLE_URL),
            (b"x" * (dist.MAX_PACK_BYTES + 1), 200, dist.SAMPLE_URL),
            (self.payload, 206, dist.SAMPLE_URL),
            (self.payload, 200, "http://127.0.0.1:9712/"),
        ]:
            with self.subTest(status=status, url=url), self.assertRaises(SeedError):
                self.download(payload, status, url)
            self.assertEqual(list(self.state.iterdir()), [])

    def test_existing_corrupt_cache_is_not_overwritten(self):
        target = self.state / dist.SAMPLE_FILENAME
        target.write_bytes(b"user data")
        with self.assertRaises(SeedError):
            self.download()
        self.assertEqual(target.read_bytes(), b"user data")

    def test_symlink_cache_refused(self):
        target = self.state / "keep.txt"
        target.write_bytes(b"keep")
        try:
            (self.state / dist.SAMPLE_FILENAME).symlink_to(target)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaises(SeedError):
            self.download()
        self.assertEqual(target.read_bytes(), b"keep")

    def test_redirects_cannot_reach_other_origins_http_ports_or_credentials(self):
        approved = "https://release-assets.githubusercontent.com/github-production-release-asset/fixture?sig=fixture"
        self.assertTrue(dist.approved_url(approved))
        for url in [
            "http://release-assets.githubusercontent.com/fixture",
            "https://github.com/other/repo",
            "https://release-assets.githubusercontent.com.bad.invalid/fixture",
            "https://user:password@release-assets.githubusercontent.com/fixture",
            "https://release-assets.githubusercontent.com:8443/fixture",
            "file:///data/rka.db",
            "https://127.0.0.1:9712/",
            "https://release-assets.githubusercontent.com/fixture#fragment",
        ]:
            with self.subTest(url=url), self.assertRaises(SeedError):
                dist.AssetRedirect().redirect_request(
                    urllib.request.Request(dist.SAMPLE_URL), None, 302, "Found", {}, url
                )

    def test_total_time_budget_removes_only_own_temporary_file(self):
        keep = self.state / "keep.txt"
        keep.write_bytes(b"keep")
        with (
            patch.object(dist.time, "monotonic", side_effect=[0, 61]),
            self.assertRaisesRegex(SeedError, "time budget"),
        ):
            self.download()
        self.assertEqual(list(self.state.iterdir()), [keep])


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        patches = [
            patch.object(boot, "PUBLIC_DEMO_ENABLED", True),
            patch.object(auto, "STATE_ROOT", self.root),
            patch.object(auto, "runtime_available"),
            patch.object(boot, "namespace_lock"),
            patch.object(PrivatePortGuard, "wait_for_private"),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_unreleased_bootstrap_is_idle_without_state(self):
        with (
            patch.object(dist, "PUBLIC_SAMPLE_ENABLED", False),
            patch.object(auto, "start") as start,
        ):
            self.assertIn("preview only", boot.bootstrap("demo-1"))
        start.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_published_sample_does_not_enable_unreleased_runtime(self):
        with (
            patch.object(dist, "PUBLIC_SAMPLE_ENABLED", True),
            patch.object(boot, "PUBLIC_DEMO_ENABLED", False),
            patch.object(dist, "download_sample") as download,
            patch.object(auto, "start") as start,
        ):
            self.assertIn("preview only", boot.bootstrap("demo-1"))
        download.assert_not_called()
        start.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_fresh_bootstrap_fetches_once_before_start_and_resume_skips_fetch(self):
        state = self.root / "demo-1"
        with (
            patch.object(dist, "PUBLIC_SAMPLE_ENABLED", True),
            patch.object(
                dist, "download_sample", return_value=state / dist.SAMPLE_FILENAME
            ) as download,
            patch.object(auto, "start", return_value="running") as start,
        ):
            self.assertEqual(boot.bootstrap("demo-1"), "running")
            self.assertEqual(boot.bootstrap("demo-1"), "running")
        download.assert_called_once_with(state)
        self.assertEqual(start.call_count, 2)
        self.assertEqual(auto.load_config(state, "demo-1")["sha256"], SHOWCASE.sha256)

    def test_privacy_failure_cannot_create_state_fetch_or_start(self):
        with (
            patch.object(dist, "PUBLIC_SAMPLE_ENABLED", True),
            patch.object(
                PrivatePortGuard, "wait_for_private", side_effect=SeedError("not private")
            ),
            patch.object(dist, "download_sample") as download,
            patch.object(auto, "start") as start,
            self.assertRaises(SeedError),
        ):
            boot.bootstrap("demo-1")
        download.assert_not_called()
        start.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_fetch_failure_cannot_enable_and_can_be_retried_without_data_reset(self):
        with (
            patch.object(dist, "PUBLIC_SAMPLE_ENABLED", True),
            patch.object(dist, "download_sample", side_effect=SeedError("network")),
            self.assertRaises(SeedError),
        ):
            boot.bootstrap("demo-1")
        state = self.root / "demo-1"
        self.assertFalse((state / auto.CONFIG).exists())
        self.assertTrue((state / MARKER).exists())

    def test_disable_corrupt_config_or_ambiguous_state_never_reenables(self):
        state = prepare_state(self.root, "demo-1")
        (state / "demo-seed.json").write_text('{"phase":"importing"}')
        with patch.object(dist, "PUBLIC_SAMPLE_ENABLED", True), self.assertRaises(SeedError):
            boot.bootstrap("demo-1")
        self.assertFalse((state / auto.CONFIG).exists())
        write_receipt(
            state,
            {
                "format": 1,
                "codespace": "demo-1",
                "enabled": False,
                "sha256": SHOWCASE.sha256,
                "pack_path": str(state / "missing.zip"),
            },
            filename=auto.CONFIG,
        )
        with patch.object(dist, "download_sample") as download:
            self.assertIn("disabled", boot.bootstrap("demo-1"))
            (state / auto.CONFIG).write_text("broken")
            with self.assertRaises(SeedError):
                boot.bootstrap("demo-1")
        download.assert_not_called()


class PortRegistrationTests(unittest.TestCase):
    def test_absent_registration_retries_then_accepts_private(self):
        guard = PrivatePortGuard("demo-1", {})
        with (
            patch.object(guard, "check", side_effect=[PortNotRegistered("absent"), None]) as check,
            patch("rka_app.codespaces_privacy.time.sleep"),
        ):
            guard.wait_for_private()
        self.assertEqual(check.call_count, 2)

    def test_other_failures_never_retry(self):
        guard = PrivatePortGuard("demo-1", {})
        for reason in ["public", "org", "auth", "malformed", "timeout"]:
            with (
                patch.object(guard, "check", side_effect=SeedError(reason)) as check,
                self.assertRaises(SeedError),
            ):
                guard.wait_for_private()
            check.assert_called_once_with(force=True)

    def test_deadline_is_bounded_and_reports_recovery(self):
        guard = PrivatePortGuard("demo-1", {})
        with (
            patch.object(guard, "check", side_effect=PortNotRegistered("absent")),
            patch("rka_app.codespaces_privacy.time.monotonic", side_effect=[0, 61]),
            self.assertRaisesRegex(SeedError, "Ports panel"),
        ):
            guard.wait_for_private()


if __name__ == "__main__":
    unittest.main()
