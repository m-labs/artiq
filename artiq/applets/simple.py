import argparse
import asyncio

from quamash import QEventLoop, QtWidgets, QtGui, QtCore

from artiq.protocols.sync_struct import Subscriber
from artiq.protocols.pc_rpc import Client


class SimpleApplet:
    def __init__(self, main_widget_class, cmd_description=None,
                 default_update_delay=0.0):
        self.main_widget_class = main_widget_class

        self.argparser = argparse.ArgumentParser(description=cmd_description)
        self.argparser.add_argument("--update-delay", type=float,
            default=default_update_delay,
            help="time to wait after a mod (buffering other mods) "
                  "before updating (default: %(default).2f)")
        group = self.argparser.add_argument_group("data server")
        group.add_argument(
            "--server-notify", default="::1",
            help="hostname or IP to connect to for dataset notifications")
        group.add_argument(
            "--port-notify", default=3250, type=int,
            help="TCP port to connect to for dataset notifications")
        group = self.argparser.add_argument_group("GUI server")
        group.add_argument(
            "--server-gui", default="::1",
            help="hostname or IP to connect to for GUI control")
        group.add_argument(
            "--port-gui", default=6501, type=int,
            help="TCP port to connect to for GUI control")
        group.add_argument("--embed", default=None, type=int,
            help="embed main widget into existing window")
        self._arggroup_datasets = self.argparser.add_argument_group("datasets")
        self.dataset_args = set()

    def add_dataset(self, name, help=None, required=True):
        kwargs = dict()
        if help is not None:
            kwargs["help"] = help
        if required:
            self._arggroup_datasets.add_argument(name, **kwargs)
        else:
            self._arggroup_datasets.add_argument("--" + name, **kwargs)
        self.dataset_args.add(name)

    def args_init(self):
        self.args = self.argparser.parse_args()
        self.datasets = {getattr(self.args, arg.replace("-", "_"))
                         for arg in self.dataset_args}

    def quamash_init(self):
        app = QtWidgets.QApplication([])
        self.loop = QEventLoop(app)
        asyncio.set_event_loop(self.loop)

    def create_main_widget(self):
        self.main_widget = self.main_widget_class(self.args)
        # Qt window embedding is ridiculously buggy, and empirical testing
        # has shown that the following procedure must be followed exactly:
        # 1. applet creates widget
        # 2. applet creates native window without showing it, and get its ID
        # 3. applet sends the ID to host, host embeds the widget
        # 4. applet shows the widget
        # Doing embedding the other way around (using QWindow.setParent in the
        # applet) breaks resizing; furthermore the host needs to know our
        # window ID to request graceful termination by closing the window.
        if self.args.embed is not None:
            win_id = int(self.main_widget.winId())
            remote = Client(self.args.server_gui, self.args.port_gui, "applets")
            try:
                remote.embed(self.args.embed, win_id)
            finally:
                remote.close_rpc()
        self.main_widget.show()

    def sub_init(self, data):
        self.data = data
        return data

    def filter_mod(self, mod):
        if mod["action"] == "init":
            return True
        if mod["path"]:
            return mod["path"][0] in self.datasets
        elif mod["action"] in {"setitem", "delitem"}:
            return mod["key"] in self.datasets
        else:
            return False

    def flush_mod_buffer(self):
        self.main_widget.data_changed(self.data, self.mod_buffer)
        del self.mod_buffer

    def sub_mod(self, mod):
        if not self.filter_mod(mod):
            return

        if self.args.update_delay:
            if hasattr(self, "mod_buffer"):
                self.mod_buffer.append(mod)
            else:
                self.mod_buffer = [mod]
                asyncio.get_event_loop().call_later(self.args.update_delay,
                                                    self.flush_mod_buffer)
        else:
            self.main_widget.data_changed(self.data, [mod])

    def create_subscriber(self):
        self.subscriber = Subscriber("datasets",
                                     self.sub_init, self.sub_mod)
        self.loop.run_until_complete(self.subscriber.connect(
            self.args.server_notify, self.args.port_notify))

    def run(self):
        self.args_init()
        self.quamash_init()
        try:
            self.create_main_widget()
            self.create_subscriber()
            try:
                self.loop.run_forever()
            finally:
                self.loop.run_until_complete(self.subscriber.close())
        finally:
            self.loop.close()
