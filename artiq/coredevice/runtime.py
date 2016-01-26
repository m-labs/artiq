import os

from artiq import __artiq_dir__ as artiq_dir


class SourceLoader:
    def __init__(self, runtime_root):
        self.runtime_root = runtime_root

    def get_source(self, filename):
        with open(os.path.join(self.runtime_root, filename)) as f:
            return f.read()

source_loader = SourceLoader(os.path.join(artiq_dir, "soc", "runtime"))
