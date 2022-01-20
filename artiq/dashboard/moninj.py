import asyncio
import logging
from collections import namedtuple
from itertools import chain

from PyQt5 import QtWidgets
from sipyco.sync_struct import Subscriber

from artiq.coredevice.comm_moninj import CommMonInj
from artiq.dashboard.moninj_widgets.dac import DACWidget
from artiq.dashboard.moninj_widgets.dds import DDSWidget
from artiq.dashboard.moninj_widgets.ttl import TTLWidget
from artiq.gui.flowlayout import FlowLayout

logger = logging.getLogger(__name__)


class _WidgetContainer:
    def __init__(self, setup_layout=lambda x: None):
        self.setup_layout = setup_layout
        self._widgets = dict()
        self._widgets_by_uid = dict()

    def remove_by_widget(self, widget):
        widget.deleteLater()
        widget.setup_monitoring(False)
        uid = next((uid for uid, wkey in self._widgets_by_uid.items() if
                    wkey == widget.sort_key), None)
        if uid is not None:
            del self._widgets_by_uid[uid]
        del self._widgets[widget.sort_key]
        self.setup_layout(self._widgets.values())

    def remove_by_key(self, key):
        self.remove_by_widget(self._widgets[key])

    def remove_by_uid(self, uid):
        self.remove_by_key(self._widgets_by_uid[uid])

    def add(self, uid, widget):
        self._widgets_by_uid[uid] = widget.sort_key
        self._widgets[widget.sort_key] = widget
        widget.setup_monitoring(True)
        self.setup_layout(self._widgets.values())

    def get_by_key(self, key):
        return self._widgets.get(key, None)

    def values(self):
        return self._widgets.values()


_WidgetDesc = namedtuple("_WidgetDesc", "uid comment cls arguments")


def setup_from_ddb(ddb):
    proxy_moninj_server = None
    proxy_moninj_port = None
    dds_sysclk = None
    description = set()

    for k, v in ddb.items():
        comment = None
        if "comment" in v:
            comment = v["comment"]
        try:
            if not isinstance(v, dict):
                continue
            if v["type"] == "controller" and k == "moninj":
                proxy_moninj_server = v["host"]
                proxy_moninj_port = v["port"]["proxy"]
            if v["type"] == "local":
                args, module_, class_ = v["arguments"], v["module"], v["class"]
                is_ad9914 = module_ == "artiq.coredevice.ad9914" and class_ == "AD9914"
                is_ad53xx = module_ == "artiq.coredevice.ad53xx" and class_ == "AD53XX"
                is_zotino = module_ == "artiq.coredevice.zotino" and class_ == "Zotino"
                if module_ == "artiq.coredevice.ttl":
                    channel = args["channel"]
                    description.add(_WidgetDesc(k, comment, TTLWidget, (
                        channel, class_ == "TTLOut", k)))
                elif is_ad9914:
                    dds_sysclk, bus_channel, channel = args["sysclk"], args[
                        "bus_channel"], args["channel"]
                    description.add(_WidgetDesc(k, comment, DDSWidget,
                                                (bus_channel, channel, k)))
                elif is_ad53xx or is_zotino:
                    spi_device = ddb[args["spi_device"]]
                    while isinstance(spi_device, str):
                        spi_device = ddb[spi_device]
                    spi_channel = spi_device["arguments"]["channel"]
                    for channel in range(32):
                        widget = _WidgetDesc((k, channel), comment,
                                             DACWidget,
                                             (spi_channel, channel, k))
                        description.add(widget)
        except KeyError:
            pass
    return proxy_moninj_server, proxy_moninj_port, dds_sysclk, description


class _DeviceManager:
    def __init__(self):
        self.reconnect_proxy = asyncio.Event()
        self.proxy_moninj_server = None
        self.proxy_moninj_port = None
        self.comm = None
        self.proxy_connector_task = asyncio.ensure_future(
            self.moninj_connector())

        self.ddb = dict()
        self.description = set()

        self.dds_sysclk = 0
        self.docks = dict()

    def init_ddb(self, ddb):
        self.ddb = ddb
        return ddb

    def notify(self, _mod):
        proxy_moninj_server, proxy_moninj_port, dds_sysclk, new_desc = \
            setup_from_ddb(self.ddb)
        self.dds_sysclk = dds_sysclk if dds_sysclk else 0
        if proxy_moninj_server != self.proxy_moninj_server:
            self.proxy_moninj_server = proxy_moninj_server
            self.proxy_moninj_port = proxy_moninj_port
            self.reconnect_proxy.set()
        for uid, _, klass, _ in self.description - new_desc:
            self.docks[klass].remove_by_uid(uid)
        for uid, comment, klass, arguments in new_desc - self.description:
            widget = klass(self, *arguments)
            if comment:
                widget.setToolTip(comment)
            self.docks[klass].add(uid, widget)
        self.description = new_desc

    def monitor_cb(self, channel, probe, value):
        if widget := self.docks[TTLWidget].get_by_key(channel):
            widget.on_monitor(probe, value)
        if widget := self.docks[DDSWidget].get_by_key((channel, probe)):
            widget.on_monitor(value)
        if widget := self.docks[DACWidget].get_by_key((channel, probe)):
            widget.on_monitor(value)

    def injection_status_cb(self, channel, override, value):
        if widget := self.docks[TTLWidget].get_by_key(channel):
            widget.on_injection_status(override, value)

    def disconnect_cb(self):
        logger.error("lost connection to moninj proxy")
        self.reconnect_proxy.set()

    async def moninj_connector(self):
        while True:
            await self.reconnect_proxy.wait()
            self.reconnect_proxy.clear()
            await self._reset_connection_state()
            # if there is no moninj server defined, just stop connecting
            if self.proxy_moninj_server is None:
                continue
            new_comm = CommMonInj(monitor_cb=self.monitor_cb,
                                  injection_status_cb=self.injection_status_cb,
                                  disconnect_cb=self.disconnect_cb)
            try:
                await new_comm.connect(self.proxy_moninj_server,
                                       self.proxy_moninj_port)
            except asyncio.CancelledError:
                logger.info("cancelled connection to moninj proxy")
                break
            except:
                logger.error("failed to connect to moninj proxy",
                             exc_info=True)
                await asyncio.sleep(10.)
                self.reconnect_proxy.set()
            else:
                logger.info("connected to moninj proxy")
                self.comm = new_comm
                for widget in self.widgets:
                    widget.setup_monitoring(True)
                    widget.setEnabled(True)

    async def close(self):
        self.proxy_connector_task.cancel()
        try:
            await asyncio.wait_for(self.proxy_connector_task, None)
        except asyncio.CancelledError:
            pass
        await self._reset_connection_state()

    async def _reset_connection_state(self):
        if self.comm is not None:
            await self.comm.close()
        self.comm = None
        for widget in self.widgets:
            widget.setEnabled(False)

    @property
    def widgets(self):
        return chain.from_iterable(x.values() for x in self.docks.values())


class _MonInjDock(QtWidgets.QDockWidget):
    def __init__(self, name):
        super().__init__(name)
        self.setObjectName(name)
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                         QtWidgets.QDockWidget.DockWidgetFloatable)

    def layout_widgets(self, widgets):
        scroll_area = QtWidgets.QScrollArea()
        self.setWidget(scroll_area)

        grid = FlowLayout()
        grid_widget = QtWidgets.QWidget()
        grid_widget.setLayout(grid)

        for widget in sorted(widgets):
            grid.addWidget(widget)

        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(grid_widget)


class MonInj:
    def __init__(self):
        self.ttl_dock = _MonInjDock("TTL")
        self.dds_dock = _MonInjDock("DDS")
        self.dac_dock = _MonInjDock("DAC")

        self.dm = _DeviceManager()
        self.dm.docks.update({
            TTLWidget: _WidgetContainer(
                lambda x: self.ttl_dock.layout_widgets(x)),
            DDSWidget: _WidgetContainer(
                lambda x: self.dds_dock.layout_widgets(x)),
            DACWidget: _WidgetContainer(
                lambda x: self.dac_dock.layout_widgets(x))
        })

        self.subscriber = Subscriber("devices", self.dm.init_ddb,
                                     self.dm.notify)

    async def start(self, server, port):
        await self.subscriber.connect(server, port)

    async def stop(self):
        await self.subscriber.close()
        if self.dm is not None:
            await self.dm.close()
