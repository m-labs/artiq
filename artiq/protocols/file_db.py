from time import time

from artiq.protocols import pyon
from artiq.protocols.sync_struct import Notifier


class FlatFileDB:
    def __init__(self, filename):
        self.filename = filename
        self.data = Notifier(pyon.load_file(self.filename))
        self.hooks = []

    def save(self):
        pyon.store_file(self.filename, self.data.read)

    def get(self, key):
        return self.data.read[key]

    def set(self, key, value):
        self.data[key] = value
        self.save()
        timestamp = time()
        for hook in self.hooks:
            hook.set(timestamp, key, value)

    def delete(self, key):
        del self.data[key]
        self.save()
        timestamp = time()
        for hook in self.hooks:
            hook.delete(timestamp, key)
