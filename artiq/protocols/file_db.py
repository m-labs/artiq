from time import time

from artiq.protocols import pyon
from artiq.protocols.sync_struct import Notifier


class FlatFileDB:
    def __init__(self, filename, default_data=None):
        self.filename = filename
        try:
            data = pyon.load_file(self.filename)
        except FileNotFoundError:
            if default_data is None:
                raise
            else:
                data = default_data
        self.data = Notifier(data)
        self.hooks = []

    def save(self):
        pyon.store_file(self.filename, self.data.read)

    def get(self, name):
        return self.data.read[name]

    def set(self, name, value):
        self.data[name] = value
        self.save()
        timestamp = time()
        for hook in self.hooks:
            hook.set(timestamp, name, value)

    def delete(self, name):
        del self.data[name]
        self.save()
        timestamp = time()
        for hook in self.hooks:
            hook.delete(timestamp, name)
