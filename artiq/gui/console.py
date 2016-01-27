import asyncio

from quamash import QtCore
from pyqtgraph import console, dockarea


_help = """
This is an interactive Python console.

The following functions are available:
    get_dataset(key)
    set_dataset(key, value, persist=False) [asynchronous update]
    del_dataset(key) [asynchronous update]

"""

class ConsoleDock(dockarea.Dock):
    def __init__(self, dataset_sub, dataset_ctl):
        dockarea.Dock.__init__(self, "Console")
        self.setMinimumSize(QtCore.QSize(720, 300))
        self.dataset_sub = dataset_sub
        self.dataset_ctl = dataset_ctl
        ns = {
            "get_dataset": self.get_dataset,
            "set_dataset": self.set_dataset,
            "del_dataset": self.del_dataset
        }
        c = console.ConsoleWidget(namespace=ns, text=_help)
        self.addWidget(c)

    def get_dataset(self, k):
        if self.dataset_sub.model is None:
            raise IOError("Datasets not available yet")
        return self.dataset_sub.model.backing_store[k][1]

    def set_dataset(self, k, v):
        asyncio.ensure_future(self.dataset_ctl.set(k, v))

    def del_dataset(self, k):
        asyncio.ensure_future(self.dataset_ctl.delete(k))
