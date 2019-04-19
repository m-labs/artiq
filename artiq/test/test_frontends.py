"""Generic tests for frontend commands."""
import subprocess
import sys
import unittest


class TestFrontends(unittest.TestCase):
    def test_help(self):
        """Test --help as a simple smoke test against catastrophic breakage."""
        # Skip tests for GUI programs on headless CI environments.
        commands = {
            "aqctl": [
                "corelog"
            ],
            "artiq": [
                "client", "compile", "coreanalyzer", "coremgmt", "ctlmgr",
                "devtool", "flash", "influxdb", "master", "mkfs", "route",
                "rpctool", "rtiomon", "run", "session"
            ]
        }

        for module in (prefix + "_" + name
                       for prefix, names in commands.items()
                       for name in names):
            subprocess.check_call(
                [sys.executable, "-m", "artiq.frontend." + module, "--help"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT)
