"""Generic tests for frontend commands."""
import subprocess
import sys
import unittest


class TestFrontends(unittest.TestCase):
    def test_help(self):
        """Test --help as a simple smoke test against catastrophic breakage."""
        commands = {
            "aqctl": [
                "corelog", "korad_ka3005p", "lda", "novatech409b",
                "thorlabs_tcube"
            ],
            "artiq": [
                "client", "compile", "coreanalyzer", "coremgmt", "ctlmgr",
                "devtool", "flash", "influxdb", "master", "mkfs", "route",
                "rpctool", "rtiomon", "run", "session"
            ]
        }

        # Skip tests for GUI programs on headless CI environments.
        try:
            from PyQt5 import QtGui, QtWidgets
            commands["artiq"] += ["browser", "dashboard"]
        except ImportError:
            pass

        for module in (prefix + "_" + name
                       for prefix, names in commands.items()
                       for name in names):
            subprocess.check_call(
                [sys.executable, "-m", "artiq.frontend." + module, "--help"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT)
