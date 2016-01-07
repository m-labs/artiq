import argparse
import asyncio

from quamash import QEventLoop, QtWidgets, QtGui, QtCore

from artiq.protocols.sync_struct import Subscriber
from artiq.protocols.pc_rpc import Client


class SimpleApplet:
    def __init__(self, main_widget_class, cmd_description=None):
        self.main_widget_class = main_widget_class

        self.argparser = argparse.ArgumentParser(description=cmd_description)
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

    def add_dataset(self, name, help=None):
        if help is None:
            self._arggroup_datasets.add_argument(name)
        else:
            self._arggroup_datasets.add_argument(name, help=help)

    def args_init(self):
        self.args = self.argparser.parse_args()

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

    def sub_mod(self, mod):
        self.main_widget.data_changed(self.data, mod)

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
