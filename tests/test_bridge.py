"""Provider-free tests; no HTTP, keyring access, or real coding agent."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1]
HELPER = PLUGIN / "scripts" / "hormuz_plugin.py"
spec = importlib.util.spec_from_file_location("omarchy_bridge", HELPER)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def report() -> dict:
    return {
        "schema_id": "hormuz.personal-benefit", "schema_version": 1,
        "profile": "personal-codex", "optimization_enabled": True,
        "content_retained": False,
        "traffic": {"total_requests": 12, "eligible_requests": 5, "transformed_requests": 4},
        "estimated_token_reduction": {"all_captured_traffic": {"tokens": 320, "percent": 8.1, "complete": True}},
        "request_byte_reduction": {"all_captured_traffic": {"bytes": 2400, "percent": 10.2, "complete": True}},
        "provider_reported": {"cache_read_tokens": {"total": None, "observed": 0}},
        "unexpected_secret": "must-not-reach-shell",
    }


@unittest.skipUnless(os.name == "posix", "Omarchy integration requires Unix")
class BridgeTests(unittest.TestCase):
    def test_projects_only_named_scalars(self):
        projected = bridge.project_report(json.dumps(report()).encode(), "personal-codex")
        self.assertEqual((projected["requests"], projected["tokensSaved"], projected["bytesSaved"]), (12, 320, 2400))
        self.assertNotIn("must-not-reach-shell", json.dumps(projected))
        self.assertIsNone(projected["cacheReadTokens"])

    def test_missing_observations_stay_missing(self):
        value = report()
        value["estimated_token_reduction"]["all_captured_traffic"] = {"tokens": 500, "percent": 10, "complete": False}
        projected = bridge.project_report(json.dumps(value).encode(), "personal-codex")
        self.assertIsNone(projected["tokensSaved"])
        self.assertIsNone(projected["tokenPercent"])

    def test_provider_cache_zero_is_observed_zero(self):
        value = report()
        value["provider_reported"]["cache_read_tokens"] = {"total": 0, "observed": 2}
        self.assertEqual(bridge.project_report(json.dumps(value).encode(), "personal-codex")["cacheReadTokens"], 0)

    def test_incompatible_or_untrusted_reports_are_rejected(self):
        for key, replacement in [
            ("profile", "another-profile"), ("schema_version", True),
            ("schema_version", 2), ("optimization_enabled", "true"),
            ("content_retained", True), ("schema_id", "another-report"),
        ]:
            with self.subTest(key=key, replacement=replacement):
                value = report()
                value[key] = replacement
                with self.assertRaises(bridge.PluginError):
                    bridge.project_report(json.dumps(value).encode(), "personal-codex")
        for value in [[], {}, None, "not-json"]:
            with self.subTest(value=value), self.assertRaises(bridge.PluginError):
                bridge.project_report(json.dumps(value).encode(), "personal-codex")

    def test_invalid_or_inconsistent_numbers_are_rejected(self):
        for count in [-1, True, "12", float("nan"), 10**19]:
            with self.subTest(count=count):
                value = report()
                value["traffic"]["total_requests"] = count
                with self.assertRaises(bridge.PluginError):
                    bridge.project_report(json.dumps(value).encode(), "personal-codex")
        value = report()
        value["traffic"]["eligible_requests"] = 20
        with self.assertRaises(bridge.PluginError):
            bridge.project_report(json.dumps(value).encode(), "personal-codex")

    def test_invalid_reduction_is_rejected(self):
        for number in [float("nan"), float("inf"), -1, "320"]:
            value = report()
            value["estimated_token_reduction"]["all_captured_traffic"]["tokens"] = number
            with self.subTest(number=number), self.assertRaises(bridge.PluginError):
                bridge.project_report(json.dumps(value).encode(), "personal-codex")

    def test_arguments_are_literal_and_settings_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "cli with spaces"
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o700)
            resolved, state = bridge.settings(str(executable), "personal-codex", temporary)
            self.assertEqual(bridge.cli_arguments(resolved, "personal-codex", state, "benefit"),
                             [str(executable), "personal", "benefit", "--profile", "personal-codex", "--state-directory", temporary, "--json"])
            for profile in ["../escape", "-flag", "UPPER", "a;command", "a\n", "a" * 65]:
                with self.subTest(profile=profile), self.assertRaises(bridge.PluginError):
                    bridge.settings(str(executable), profile, temporary)
            with self.assertRaises(bridge.PluginError):
                bridge.settings(str(executable), "personal-codex", "relative/path")

    def test_missing_cli_returns_fixed_diagnostic(self):
        result = subprocess.run([sys.executable, str(HELPER), "status", "--cli", "hormuz-impossible-missing"],
                                capture_output=True, text=True, timeout=3)
        value = json.loads(result.stdout)
        self.assertEqual((result.returncode, value["error"]), (1, "cli_unavailable"))

    def test_failed_cli_does_not_expose_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "failed-cli"
            executable.write_text("#!/bin/sh\necho secret-sentinel\necho stderr-sentinel >&2\nexit 1\n")
            executable.chmod(0o700)
            result = subprocess.run([sys.executable, str(HELPER), "status", "--cli", str(executable)],
                                    capture_output=True, text=True, timeout=3)
            self.assertEqual(json.loads(result.stdout)["error"], "cli_failed")
            self.assertNotIn("sentinel", result.stdout + result.stderr)

    def test_capture_bounds_output(self):
        with self.assertRaisesRegex(bridge.PluginError, "output_too_large"):
            bridge.capture([sys.executable, "-c", "import sys; sys.stdout.write('a'*300000); sys.stdout.flush()"])

    def test_timeout_stops_and_reaps_its_process(self):
        start = time.monotonic()
        with self.assertRaisesRegex(bridge.PluginError, "timeout"):
            bridge.capture([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.15)
        self.assertLess(time.monotonic() - start, 2)

    def test_timeout_cleans_up_a_descendant_ignoring_sigterm(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "pid"
            child_code = "import os,signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path(" + repr(str(marker)) + ").write_text(str(os.getpid())); time.sleep(30)"
            parent_code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child_code) + "]); time.sleep(30)"
            with self.assertRaisesRegex(bridge.PluginError, "timeout"):
                bridge.capture([sys.executable, "-c", parent_code], timeout=0.5)
            pid = int(marker.read_text())
            process = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=2)
            self.assertTrue(process.returncode != 0 or process.stdout.strip().startswith("Z"), process.stdout)

    def test_widget_termination_cleans_up_cli_descendants(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "child-pid"
            child_code = "import os,signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path(" + repr(str(marker)) + ").write_text(str(os.getpid())); time.sleep(30)"
            executable = Path(temporary) / "blocking-cli"
            executable.write_text("#!" + sys.executable + "\nimport subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c'," + repr(child_code) + "])\ntime.sleep(30)\n")
            executable.chmod(0o700)
            helper = subprocess.Popen([sys.executable, str(HELPER), "status", "--cli", str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 3
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists(), "CLI descendant did not start")
                helper.terminate()
                stdout, stderr = helper.communicate(timeout=3)
                self.assertEqual(helper.returncode, 1, stderr)
                self.assertEqual(json.loads(stdout)["error"], "interrupted")
                pid = int(marker.read_text())
                process = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=2)
                self.assertTrue(process.returncode != 0 or process.stdout.strip().startswith("Z"), process.stdout)
            finally:
                if helper.poll() is None:
                    helper.terminate()
                    helper.communicate(timeout=3)

    def test_toggle_rereads_report_only_after_success(self):
        with patch.object(bridge, "capture", side_effect=[b"", json.dumps(report()).encode()]) as capture:
            value = bridge.status("/path/cli", "personal-codex", "", "on")
        self.assertTrue(value["enabled"])
        self.assertEqual([call.args[0][2] for call in capture.call_args_list], ["on", "benefit"])
        with patch.object(bridge, "capture", side_effect=bridge.PluginError("cli_failed")) as capture:
            with self.assertRaises(bridge.PluginError):
                bridge.status("/path/cli", "personal-codex", "", "off")
            self.assertEqual(capture.call_count, 1)

    def test_launch_requires_private_runtime(self):
        with patch.dict(os.environ, {"XDG_RUNTIME_DIR": ""}):
            with self.assertRaisesRegex(bridge.PluginError, "runtime_unavailable"):
                bridge.launch("/path/cli", "personal-codex", "")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            root.mkdir(mode=0o755)
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(root)}):
                with self.assertRaisesRegex(bridge.PluginError, "runtime_unavailable"):
                    bridge.launch("/path/cli", "personal-codex", "")

    def test_launch_refuses_duplicate_then_releases_lock_on_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "interactive-cli"
            executable.write_text("#!" + sys.executable + "\nimport sys\nprint('ready',flush=True)\nsys.stdin.readline()\n")
            executable.chmod(0o700)
            args = [sys.executable, str(HELPER), "launch", "--cli", str(executable)]
            environment = dict(os.environ, XDG_RUNTIME_DIR=temporary)
            first = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(first.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(timeout=3), "first launch did not become ready")
                self.assertEqual(first.stdout.readline(), b"ready\n")
                second = subprocess.run(args, capture_output=True, env=environment, timeout=3)
                self.assertEqual(second.returncode, 1)
                self.assertIn(b"already has an agent session", second.stderr)
                first.communicate(input=b"\n", timeout=3)
                self.assertEqual(first.returncode, 0)
                third = subprocess.run(args, input=b"\n", capture_output=True, env=environment, timeout=3)
                self.assertEqual((third.returncode, third.stdout), (0, b"ready\n"))
            finally:
                if first.poll() is None:
                    first.terminate()
                first.communicate(timeout=3)

    def test_plugin_has_root_metadata_and_safe_entry_points(self):
        manifest = json.loads((PLUGIN / "manifest.json").read_text())
        self.assertEqual(manifest["id"], "io.hormuz.optimizer")
        for name in ["README.md", "LICENSE", *manifest["entryPoints"].values()]:
            self.assertTrue((PLUGIN / name).is_file(), name)
        self.assertFalse(any(path.is_symlink() for path in PLUGIN.rglob("*") if ".git" not in path.parts))


@unittest.skipIf(os.name != "posix" or getattr(os, "getuid", lambda: 0)() == 0,
                 "installer requires a non-root Unix user")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="omarchy-installer-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.plugins = self.root / "plugins"
        self.environment = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                                HORMUZ_OMARCHY_PLUGIN_ROOT=str(self.plugins),
                                TEST_INSTALL_LOG=str(self.root / "actions"))
        for name, body in {
            "uname": "#!/bin/sh\necho Linux\n",
            "timeout": '#!/bin/sh\nshift\nexec "$@"\n',
            "omarchy": '#!/bin/sh\necho "$*" >> "$TEST_INSTALL_LOG"\nif [ "$2" = validate ] && [ "${TEST_VALIDATION_FAILURE:-}" = 1 ]; then exit 1; fi\n',
            "omarchy-shell": '''#!/bin/sh
echo "shell $*" >> "$TEST_INSTALL_LOG"
if [ "${TEST_RESCAN_FAILURE:-}" = 1 ]; then exit 1; fi
if [ "$2" = listPlugins ]; then
  if [ "${TEST_CATALOG_UNAVAILABLE:-}" = 1 ]; then echo '[]'; exit; fi
  if [ "${TEST_CATALOG_DELAY:-}" = 1 ] && [ ! -e "$TEST_INSTALL_LOG.ready" ]; then
    touch "$TEST_INSTALL_LOG.ready"; echo '[]'; exit
  fi
  echo '[{"id":"io.hormuz.optimizer"}]'
fi
''',
            "sleep": '#!/bin/sh\nexit 0\n',
        }.items():
            command = self.bin / name
            command.write_text(body)
            command.chmod(0o700)
        # macOS lacks GNU mv -T; the test mock preserves its no-nesting contract.
        if sys.platform == "darwin":
            command = self.bin / "mv"
            command.write_text("#!" + sys.executable + "\nimport os,sys\nassert sys.argv[1:3]==['-T','--']\nos.rename(sys.argv[3],sys.argv[4])\n")
            command.chmod(0o700)

    def install(self):
        return subprocess.run(["bash", str(PLUGIN / "scripts/install.sh")], env=self.environment,
                              capture_output=True, text=True, timeout=5)

    def test_stages_validates_and_enables_one_folder(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        destination = self.plugins / "io.hormuz.optimizer"
        self.assertEqual(json.loads((destination / "manifest.json").read_text())["id"], "io.hormuz.optimizer")
        self.assertEqual([path.name for path in self.plugins.iterdir()], ["io.hormuz.optimizer"])
        actions = (self.root / "actions").read_text().splitlines()
        self.assertTrue(actions[0].startswith("plugin validate "))
        self.assertEqual(actions[1:], ["shell shell rescanPlugins", "shell shell listPlugins", "plugin enable io.hormuz.optimizer"])

    def test_waits_for_asynchronous_catalog_before_enabling(self):
        self.environment["TEST_CATALOG_DELAY"] = "1"
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        actions = (self.root / "actions").read_text().splitlines()
        self.assertEqual(actions[1:], ["shell shell rescanPlugins", "shell shell listPlugins",
                                      "shell shell listPlugins", "plugin enable io.hormuz.optimizer"])

    def test_unavailable_catalog_stops_after_bounded_wait(self):
        self.environment["TEST_CATALOG_UNAVAILABLE"] = "1"
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        actions = (self.root / "actions").read_text()
        self.assertEqual(actions.count("shell shell listPlugins"), 6)
        self.assertNotIn("plugin enable", actions)
        self.assertTrue((self.plugins / "io.hormuz.optimizer/manifest.json").is_file())

    def test_existing_folder_is_not_overwritten(self):
        destination = self.plugins / "io.hormuz.optimizer"
        destination.mkdir(parents=True)
        (destination / "sentinel").write_text("preserve")
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual((destination / "sentinel").read_text(), "preserve")
        self.assertFalse((self.root / "actions").exists())

    def test_failed_validation_cleans_staging_before_shell_changes(self):
        self.environment["TEST_VALIDATION_FAILURE"] = "1"
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(list(self.plugins.iterdir()), [])
        self.assertEqual(len((self.root / "actions").read_text().splitlines()), 1)

    def test_failed_rescan_retains_validated_folder_and_reports_failure(self):
        self.environment["TEST_RESCAN_FAILURE"] = "1"
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.plugins / "io.hormuz.optimizer/manifest.json").is_file())
        self.assertIn("Start the Omarchy shell", result.stderr)
        self.assertNotIn("plugin enable", (self.root / "actions").read_text())


if __name__ == "__main__":
    unittest.main()
