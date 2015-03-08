import os

from artiq.protocols.sync_struct import Notifier
from artiq.tools import file_import
from artiq.language.experiment import is_experiment


def scan_experiments():
    r = dict()
    for f in os.listdir("repository"):
        if f.endswith(".py"):
            try:
                m = file_import(os.path.join("repository", f))
            except:
                continue
            for k, v in m.__dict__.items():
                if is_experiment(v):
                    if v.__doc__ is None:
                        name = k
                    else:
                        name = v.__doc__.splitlines()[0].strip()
                        if name[-1] == ".":
                            name = name[:-1]
                    entry = {
                        "file": os.path.join("repository", f),
                        "experiment": k,
                        "gui_file": getattr(v, "__artiq_gui_file__", None)
                    }
                    r[name] = entry
    return r


class Repository:
    def __init__(self):
        self.explist = Notifier(scan_experiments())

    def get_data(self, filename):
        with open(os.path.join("repository", filename)) as f:
            return f.read()
