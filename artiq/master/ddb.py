from artiq.protocols.sync_struct import Notifier
from artiq.protocols import pyon


class DDB:
    def __init__(self, backing_file):
        self.backing_file = backing_file
        self.data = Notifier(pyon.load_file(self.backing_file))

    def scan(self):
        new_data = pyon.load_file(self.backing_file)

        for k in list(self.data.read.keys()):
            if k not in new_data:
                del self.data[k]
        for k in new_data.keys():
            if k not in self.data.read or self.data.read[k] != new_data[k]:
                self.data[k] = new_data[k]

    def get_ddb(self):
        return self.data.read

    def get(self, key):
        return self.data.read[key]
