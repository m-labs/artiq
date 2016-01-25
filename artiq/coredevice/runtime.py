import os

class SourceLoader:
    def __init__(self, runtime_root):
        self.runtime_root = runtime_root

    def get_source(self, filename):
        with open(os.path.join(self.runtime_root, filename)) as f:
            return f.read()

artiq_root = os.path.join(os.path.dirname(__file__), "..", "..")
source_loader = SourceLoader(os.path.join(artiq_root, "soc", "runtime"))
