from pyqtgraph import console, dockarea


_help = """
This is an interactive Python console.

The following functions are available:
    get_dataset(key)
    set_dataset(key, value, persist=False) [asynchronous update]
    del_dataset(key) [asynchronous update]

"""

class ConsoleDock(dockarea.Dock):
    def __init__(self, get_dataset, set_dataset, del_dataset):
        dockarea.Dock.__init__(self, "Console", size=(1000, 300))
        ns = {
            "get_dataset": get_dataset,
            "set_dataset": set_dataset,
            "del_dataset": del_dataset
        }
        c = console.ConsoleWidget(namespace=ns, text=_help)
        self.addWidget(c)
