"""End-to-end tests of the standalone installers (bash and PowerShell) against a locally built release."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = "v1.2.0"
TOKEN = "fixture-token"


def find_bash():
    """Return a POSIX bash, ignoring the WSL launcher that Windows puts in System32."""
    found = shutil.which("bash")
    return found if found and "system32" not in found.lower() else None


def find_powershell():
    """Return pwsh or Windows PowerShell when installed."""
    return os.environ.get("AI_WATCH_TEST_POWERSHELL") or shutil.which("pwsh") or shutil.which("powershell")


BASH = find_bash()
POWERSHELL = find_powershell()
RELEASES = tempfile.TemporaryDirectory()


def setUpModule():
    """Build the release assets once, exactly as the release workflow does."""
    if not BASH:
        return
    assets = Path(RELEASES.name) / TAG
    subprocess.run([BASH, (ROOT / "release" / "assets.sh").as_posix()], check=True, capture_output=True,
                   env={**os.environ, "RELEASE_TAG": TAG, "ASSETS_DIR": assets.as_posix()})
    latest = Path(RELEASES.name) / "api" / "releases" / "latest"  # what GitHub answers for /releases/latest
    latest.parent.mkdir(parents=True)
    latest.write_text(json.dumps({"tag_name": TAG}), encoding="utf-8")


def tearDownModule():
    """Remove the locally built release."""
    RELEASES.cleanup()


class Receiver(BaseHTTPRequestHandler):
    """Minimal AI Watch server that records the (path, key accepted, status) of each POST."""
    events = []

    def do_POST(self):
        """Record the event and accept it."""
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Receiver.events.append((self.path, self.headers["X-Monitor-Key"] == TOKEN, payload["status"]))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        """Keep the test output clean."""


class InstallerTests:
    """Scenarios shared by both installers; subclasses say how to invoke one."""
    flags = {}

    def command(self, *args):
        raise NotImplementedError

    def setUp(self):
        Receiver.events = []
        self.server = HTTPServer(("127.0.0.1", 0), Receiver)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()  # expands Windows 8.3 short names such as RUNNER~1
        self.home = root / "home"
        (self.home / ".copilot").mkdir(parents=True)
        self.dir = root / "hooks"
        self.token = root / "token.txt"
        self.token.write_text(TOKEN, encoding="utf-8")
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.release = RELEASES.name

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def run_installer(self, *args, release=None):
        """Run the installer in an isolated home against the local release."""
        env = {**os.environ, "HOME": str(self.home), "USERPROFILE": str(self.home),
               "AI_WATCH_HOOKS_DIR": self.dir.as_posix(),
               "AI_WATCH_HOOKS_RELEASE_BASE": Path(release or self.release).as_uri(),
               "AI_WATCH_HOOKS_RELEASE_API": (Path(self.release) / "api").as_uri()}
        env.pop("AI_WATCH_TOKEN", None)
        return subprocess.run(self.command(*args), env=env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL)

    def install_args(self, *extra):
        f = self.flags
        return (f["version"], TAG, f["url"], self.url, f["token-file"], self.token.as_posix(),
                f["agent"], "copilot", *extra)

    def registration(self):
        return self.home / ".copilot" / "hooks" / "ai-watch.json"

    def test_install_registers_the_hooks_and_sends_a_test_event(self):
        result = self.run_installer(*self.install_args())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.dir / "VERSION").read_text().strip(), TAG)
        config = json.loads((self.dir / "bridge" / "config.local.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(config, {"url": self.url, "token": TOKEN})
        hook = (self.dir / "bridge" / "hook.py").as_posix()
        self.assertIn(hook, json.loads(self.registration().read_text())["hooks"]["Stop"][0]["bash"])
        self.assertEqual(Receiver.events, [("/api/events", True, "idle")])
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_a_second_run_changes_nothing_and_update_keeps_the_config(self):
        self.assertEqual(self.run_installer(*self.install_args()).returncode, 0)
        config = self.dir / "bridge" / "config.local.json"
        config.write_text(json.dumps({"url": self.url, "token": TOKEN, "keep": "me"}), encoding="utf-8")
        again = self.run_installer(self.flags["agent"], "copilot")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("already installed", again.stdout)
        update = self.run_installer(self.flags["update"], self.flags["agent"], "copilot")
        self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
        self.assertEqual(json.loads(config.read_text())["keep"], "me")
        self.assertEqual(len(list(self.registration().parent.glob("ai-watch.json*"))), 1)

    def test_a_tampered_bundle_is_rejected(self):
        tampered = self.dir.parent / "tampered"
        shutil.copytree(RELEASES.name, tampered)
        with (tampered / TAG / f"ai-watch-hooks-{TAG}.zip").open("ab") as archive:
            archive.write(b"tampered")
        result = self.run_installer(*self.install_args(), release=tampered)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum mismatch", result.stdout + result.stderr)
        self.assertFalse((self.dir / "VERSION").exists())
        self.assertFalse(self.registration().exists())

    def test_a_rejected_url_leaves_no_config(self):
        args = list(self.install_args())
        args[args.index(self.url)] = "http://example.org"
        result = self.run_installer(*args)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.dir / "bridge" / "config.local.json").exists())
        self.assertFalse(self.registration().exists())

    def test_uninstall_unregisters_and_keeps_the_config_until_purged(self):
        self.assertEqual(self.run_installer(*self.install_args()).returncode, 0)
        removed = self.run_installer(self.flags["uninstall"], self.flags["agent"], "copilot")
        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertFalse(self.registration().exists())
        self.assertTrue((self.dir / "bridge" / "config.local.json").exists())
        self.assertFalse((self.dir / "bridge" / "hook.py").exists())
        purged = self.run_installer(self.flags["uninstall"], self.flags["purge"])
        self.assertEqual(purged.returncode, 0, purged.stdout + purged.stderr)
        self.assertFalse(self.dir.exists())


@unittest.skipUnless(BASH, "bash is not available")
class BashInstallerTests(InstallerTests, unittest.TestCase):
    """The Linux, macOS and Git Bash installer."""
    flags = {"version": "--version", "url": "--url", "token-file": "--token-file", "agent": "--agent",
             "update": "--update", "uninstall": "--uninstall", "purge": "--purge"}

    def command(self, *args):
        return [BASH, (ROOT / "scripts" / "standalone" / "install.sh").as_posix(), *args]


@unittest.skipUnless(BASH and POWERSHELL, "bash or PowerShell is not available")
class PowerShellInstallerTests(InstallerTests, unittest.TestCase):
    """The Windows installer (also runs under PowerShell 7 on Linux and macOS)."""
    flags = {"version": "-Version", "url": "-Url", "token-file": "-TokenFile", "agent": "-Agent",
             "update": "-Update", "uninstall": "-Uninstall", "purge": "-Purge"}

    def command(self, *args):
        return [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(ROOT / "scripts" / "standalone" / "install.ps1"), *args]


if __name__ == "__main__":
    unittest.main()
