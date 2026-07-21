"""Tests for launcher-safe uninstall behavior."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cyberspace.uninstall import MANAGED_MARKER, remove_installation


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