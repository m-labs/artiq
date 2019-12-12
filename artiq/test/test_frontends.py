"""Generic tests for frontend commands."""
import subprocess
import sys
import unittest


class TestFrontends(unittest.TestCase):
    def test_help(self):
        """Test --help as a simple smoke test against catastrophic breakage."""
        commands = {
            "aqctl": [
                "corelog"
            ],
            "artiq": [
                "client", "compile", "coreanalyzer", "coremgmt",
                "netboot", "flash", "master", "mkfs", "route",
                "rtiomon", "run", "session", "browser", "dashboard"
            ]
        }

        for module in (prefix + "_" + name
                       for prefix, names in commands.items()
                       for name in names):
            subprocess.check_call(
                [sys.executable, "-m", "artiq.frontend." + module, "--help"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT)
