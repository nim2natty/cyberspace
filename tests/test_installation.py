"""Tests for launcher-safe uninstall behavior."""
from __future__ import annotations

import tempfile
import unittest
import re
from pathlib import Path

from cyberspace.uninstall import (
    MANAGED_MARKER, _schedule_executable_removal, remove_installation,
)


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.root = self.base / "cyberspace"
        (self.root / "cyberspace").mkdir(parents=True)
        (self.root / "cyberspace" / "__init__.py").write_text("")
        (self.root / "pyproject.toml").write_text("[project]\nname='cyberspace'\n")
        self.venv = self.root / ".venv"
        self.venv.mkdir()
        (self.venv / "installed").write_text("yes")
        self.launcher = self.base / "bin" / "cyberspace"
        self.launcher.parent.mkdir()
        self.launcher.write_text(f"#!/bin/sh\n{MANAGED_MARKER}\n")
        self.data = self.base / "data"
        self.data.mkdir()
        (self.data / "projects.json").write_text("keep")

    def test_default_keeps_source_and_data(self):
        actions = remove_installation(self.root, self.launcher, self.data)
        self.assertFalse(self.launcher.exists())
        self.assertFalse(self.venv.exists())
        self.assertTrue(self.root.exists())
        self.assertTrue(self.data.exists())
        self.assertTrue(any("removed launcher" in action for action in actions))

    def test_explicit_full_removal(self):
        remove_installation(self.root, self.launcher, self.data,
                            remove_source=True, purge_data=True)
        self.assertFalse(self.root.exists())
        self.assertFalse(self.data.exists())

    def test_standalone_executable_is_removed_only_after_process_exit(self):
        scheduled = []
        actions = remove_installation(
            self.root, self.launcher, self.data, standalone=True,
            deferred_remover=lambda path: scheduled.append(path))
        self.assertTrue(self.launcher.exists(), "running frozen executable was unlinked")
        self.assertEqual(scheduled, [self.launcher])
        self.assertTrue(any("scheduled executable removal" in action for action in actions))

    def test_posix_remover_passes_path_as_separate_argument(self):
        calls = []
        _schedule_executable_removal(
            self.launcher, platform_name="posix",
            popen=lambda command, **kwargs: calls.append((command, kwargs)))
        command, kwargs = calls[0]
        self.assertEqual(command[:3], ["sh", "-c", 'sleep 2; rm -f -- "$1"'])
        self.assertEqual(command[-1], str(self.launcher.resolve()))
        self.assertTrue(kwargs["start_new_session"])

    def test_installer_tells_current_shell_how_to_run_and_update(self):
        installer = Path(__file__).resolve().parents[1] / "installer" / "install.sh"
        text = installer.read_text()
        self.assertIn('${bin_dir}/cyberspace', text)
        self.assertIn("open a new terminal", text)
        self.assertIn("cyberspace update", text)

    def test_uninstall_help_uses_wipe_not_purge_data(self):
        from typer.testing import CliRunner
        from cyberspace.cli import app
        result = CliRunner().invoke(app, ["uninstall", "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("wipe", result.output)
        self.assertNotIn("purge-data", result.output)

    def test_package_and_runtime_versions_match(self):
        import cyberspace
        project = Path(__file__).resolve().parents[1] / "pyproject.toml"
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', project.read_text())
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), cyberspace.__version__)

    def test_unmanaged_launcher_is_preserved(self):
        self.launcher.write_text("#!/bin/sh\necho unrelated\n")
        actions = remove_installation(self.root, self.launcher, self.data)
        self.assertTrue(self.launcher.exists())
        self.assertTrue(any("kept unmanaged" in action for action in actions))

    def test_unknown_source_is_not_deleted(self):
        unknown = self.base / "unrelated"
        unknown.mkdir()
        with self.assertRaises(ValueError):
            remove_installation(unknown, self.base / "missing", self.data,
                                remove_source=True)
        self.assertTrue(unknown.exists())


if __name__ == "__main__":
    unittest.main()