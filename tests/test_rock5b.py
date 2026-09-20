"""Tests for design/rock5b/ (the Aquila font install tooling for the ROCK 5B).

There is nothing to unit-test in the usual sense here -- it's a fontconfig
XML file plus a bash script that edits system files. What's safe and useful
to check without a real ROCK 5B (or root, or mutating this container):

- The XML file is well-formed. It previously wasn't (see the fix in this
  same change): the header comment used a literal "--" as a typographic
  dash, which XML forbids inside comments except as the closing "-->".
  Depending on how strict a given fontconfig build's parser is, that could
  make it reject the file outright -- silently defeating the whole point of
  step 3 in install-aquila-font.sh.
- The script's bash syntax is valid (`bash -n`).
- The script's *dry-run* behavior (the default -- nothing is written unless
  --apply is passed) for argument handling: --help, an unknown flag, and
  --rollback with no backup present. --apply is never invoked here: as of
  this test run the container executes as root, so --apply would genuinely
  write to /etc/fonts/conf.d, /usr/local/share/fonts, and attempt apt-get --
  none of which is this container's fontconfig to change.
"""

import os
import shutil
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROCK5B_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "design", "rock5b"
)
FONTCONFIG_PATH = os.path.join(ROCK5B_DIR, "60-aquila.conf")
SCRIPT_PATH = os.path.join(ROCK5B_DIR, "install-aquila-font.sh")
BACKUP_ROOT = "/var/backups/aquila-font"  # hardcoded in the script, not overridable


def run_script(*args):
    return subprocess.run(
        [SCRIPT_PATH, *args],
        cwd=ROCK5B_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )


class FontconfigXmlTests(unittest.TestCase):
    def test_is_well_formed_xml(self):
        # Raises ParseError if not -- that's the whole test.
        ET.parse(FONTCONFIG_PATH)

    def test_prefers_aquila_before_fallbacks(self):
        root = ET.parse(FONTCONFIG_PATH).getroot()
        sans_serif_alias = next(
            alias
            for alias in root.findall("alias")
            if alias.findtext("family") == "sans-serif"
        )
        families = [f.text for f in sans_serif_alias.find("prefer").findall("family")]
        self.assertEqual(families, ["Aquila", "Atkinson Hyperlegible", "Lexend"])


class InstallScriptStaticTests(unittest.TestCase):
    def test_bash_syntax_is_valid(self):
        result = subprocess.run(
            ["bash", "-n", SCRIPT_PATH], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_is_executable(self):
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK))

    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck not installed")
    def test_shellcheck_clean(self):
        result = subprocess.run(
            ["shellcheck", SCRIPT_PATH], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout)


class InstallScriptDryRunTests(unittest.TestCase):
    """All of these deliberately never pass --apply -- see module docstring."""

    def test_default_dry_run_exits_zero_and_writes_nothing(self):
        result = run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertFalse(os.path.isdir(BACKUP_ROOT))

    def test_help_flag_prints_usage_and_exits_zero(self):
        result = run_script("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Usage:", result.stdout)

    def test_unknown_argument_is_rejected(self):
        result = run_script("--this-flag-does-not-exist")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown argument", result.stderr)

    @unittest.skipIf(
        os.path.isdir(BACKUP_ROOT),
        f"{BACKUP_ROOT} exists in this environment -- rollback behavior "
        "differs from the no-backup case this test checks",
    )
    def test_rollback_without_backup_fails_gracefully(self):
        result = run_script("--rollback")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No backup found", result.stderr)


if __name__ == "__main__":
    unittest.main()
