import os
from inspect import isclass

from artiq.protocols.sync_struct import Notifier
from artiq.tools import file_import


def scan_experiments():
    r = dict()
    for f in os.listdir("repository"):
        if f.endswith(".py"):
            try:
                m = file_import(os.path.join("repository", f))
            except:
                continue
            for k, v in m.__dict__.items():
                if isclass(v) and hasattr(v, "__artiq_unit__"):
                    entry = {
                        "file": os.path.join("repository", f),
                        "unit": k,
                        "gui_file": getattr(v, "__artiq_gui_file__", None)
                    }
                    r[v.__artiq_unit__] = entry
    return r


class Repository:
    def __init__(self):
        self.explist = Notifier(scan_experiments())

    def get_data(self, filename):
        with open(os.path.join("repository", filename)) as f:
            return f.read()
