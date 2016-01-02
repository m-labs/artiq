import argparse
import asyncio

from quamash import QEventLoop, QtWidgets, QtCore

from artiq.protocols.sync_struct import Subscriber


class SimpleApplet:
    def __init__(self, main_widget_class, cmd_description=None):
        self.main_widget_class = main_widget_class

        self.argparser = argparse.ArgumentParser(description=cmd_description)
        group = self.argparser.add_argument_group("data server")
        group.add_argument(
            "--server", default="::1",
            help="hostname or IP to connect to")
        group.add_argument(
            "--port", default=3250, type=int,
            help="TCP port to connect to")
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
            self.args.server, self.args.port))

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
