"""CLI wiring: every documented command parses (no network, no model)."""
import subprocess
import sys

import pytest

COMMANDS = ["discover", "select-sources", "fetch", "onboard", "review", "approve", "extract", "resolve",
            "compare-matchers", "profiles", "report", "restore-approved", "revalidate", "fullcheck", "stability"]


@pytest.mark.parametrize("cmd", COMMANDS)
def test_command_help(cmd):
    r = subprocess.run([sys.executable, "-m", "firmable.cli", cmd, "--help"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "usage" in r.stdout.lower()
