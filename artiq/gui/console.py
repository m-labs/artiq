from pyqtgraph import console, dockarea


_help = """
This is an interactive Python console.

The following functions are available:
    get_parameter(key)
    set_parameter(key, value) [asynchronous update]
    get_result(key) [real-time results only]

"""

class ConsoleDock(dockarea.Dock):
    def __init__(self, get_parameter, set_parameter, get_result):
        dockarea.Dock.__init__(self, "Console", size=(1000, 300))
        ns = {
            "get_parameter": get_parameter,
            "set_parameter": set_parameter,
            "get_result": get_result
        }
        c = console.ConsoleWidget(namespace=ns, text=_help)
        self.addWidget(c)
