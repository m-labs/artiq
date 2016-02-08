import logging
import argparse
import asyncio

from quamash import QEventLoop, QtWidgets, QtGui, QtCore

from artiq.protocols.sync_struct import Subscriber, process_mod
from artiq.protocols import pyon
from artiq.protocols.pipe_ipc import AsyncioChildComm


logger = logging.getLogger(__name__)


class AppletIPCClient(AsyncioChildComm):
    def set_close_cb(self, close_cb):
        self.close_cb = close_cb

    def write_pyon(self, obj):
        self.write(pyon.encode(obj).encode() + b"\n")

    async def read_pyon(self):
        line = await self.readline()
        return pyon.decode(line.decode())

    async def embed(self, win_id):
        # This function is only called when not subscribed to anything,
        # so the only normal replies are embed_done and terminate.
        self.write_pyon({"action": "embed",
                         "win_id": win_id})
        reply = await self.read_pyon()
        if reply["action"] == "terminate":
            self.close_cb()
        elif reply["action"] != "embed_done":
            logger.error("unexpected action reply to embed request: %s",
                         action)
            self.close_cb()

    async def listen(self):
        data = None
        while True:
            obj = await self.read_pyon()
            try:
                action = obj["action"]
                if action == "terminate":
                    self.close_cb()
                    return
                elif action == "mod":
                    mod = obj["mod"]
                    if mod["action"] == "init":
                        data = self.init_cb(mod["struct"])
                    else:
                        process_mod(data, mod)
                    self.mod_cb(mod)
                else:
                    raise ValueError("unknown action in parent message")
            except:
                logger.error("error processing parent message",
                               exc_info=True)
                self.close_cb()

    def subscribe(self, datasets, init_cb, mod_cb):
        self.write_pyon({"action": "subscribe",
                         "datasets": datasets})
        self.init_cb = init_cb
        self.mod_cb = mod_cb
        asyncio.ensure_future(self.listen())


class SimpleApplet:
    def __init__(self, main_widget_class, cmd_description=None,
                 default_update_delay=0.0):
        self.main_widget_class = main_widget_class

        self.argparser = argparse.ArgumentParser(description=cmd_description)

        self.argparser.add_argument("--update-delay", type=float,
            default=default_update_delay,
            help="time to wait after a mod (buffering other mods) "
                  "before updating (default: %(default).2f)")

        self._arggroup_datasets = self.argparser.add_argument_group("datasets")

        subparsers = self.argparser.add_subparsers(dest="mode")
        subparsers.required = True

        parser_sa = subparsers.add_parser("standalone",
            help="run standalone, connect to master directly")
        parser_sa.add_argument(
            "--server", default="::1",
            help="hostname or IP to connect to")
        parser_sa.add_argument(
            "--port", default=3250, type=int,
            help="TCP port to connect to")

        parser_em = subparsers.add_parser("embedded",
            help="embed into GUI")
        parser_em.add_argument("ipc_address",
            help="address for pipe_ipc")

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

    def ipc_init(self):
        if self.args.mode == "standalone":
            # nothing to do
            pass
        elif self.args.mode == "embedded":
            self.ipc = AppletIPCClient(self.args.ipc_address)
            self.loop.run_until_complete(self.ipc.connect())
        else:
            raise NotImplementedError

    def ipc_close(self):
        if self.args.mode == "standalone":
            # nothing to do
            pass
        elif self.args.mode == "embedded":
            self.ipc.close()
        else:
            raise NotImplementedError

    def create_main_widget(self):
        self.main_widget = self.main_widget_class(self.args)
        # Qt window embedding is ridiculously buggy, and empirical testing
        # has shown that the following procedure must be followed exactly:
        # 1. applet creates widget
        # 2. applet creates native window without showing it, and get its ID
        # 3. applet sends the ID to host, host embeds the widget
        # 4. applet shows the widget
        # Doing embedding the other way around (using QWindow.setParent in the
        # applet) breaks resizing.
        if self.args.mode == "embedded":
            self.ipc.set_close_cb(self.main_widget.close)
            win_id = int(self.main_widget.winId())
            self.loop.run_until_complete(self.ipc.embed(win_id))
        self.main_widget.show()

    def sub_init(self, data):
        self.data = data
        return data

    def filter_mod(self, mod):
        if self.args.mode == "embedded":
            # the parent already filters for us
            return True

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

    def subscribe(self):
        if self.args.mode == "standalone":
            self.subscriber = Subscriber("datasets",
                                         self.sub_init, self.sub_mod)
            self.loop.run_until_complete(self.subscriber.connect(
                self.args.server_notify, self.args.port_notify))
        elif self.args.mode == "embedded":
            self.ipc.subscribe(self.datasets, self.sub_init, self.sub_mod)
        else:
            raise NotImplementedError

    def unsubscribe(self):
        if self.args.mode == "standalone":
            self.loop.run_until_complete(self.subscriber.close())
        elif self.args.mode == "embedded":
            # nothing to do
            pass
        else:
            raise NotImplementedError

    def run(self):
        self.args_init()
        self.quamash_init()
        try:
            self.ipc_init()
            try:
                self.create_main_widget()
                self.subscribe()
                try:
                    self.loop.run_forever()
                finally:
                    self.unsubscribe()
            finally:
                self.ipc_close()
        finally:
            self.loop.close()
