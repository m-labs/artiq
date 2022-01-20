from artiq.dashboard.moninj_widgets import SimpleDisplayWidget


class DDSWidget(SimpleDisplayWidget):
    def __init__(self, dm, bus_channel, channel, title):
        self.dm = dm
        self.bus_channel = bus_channel
        self.channel = channel
        self.cur_frequency = 0
        super().__init__(title)

    def refresh_display(self):
        self.value.setText(f'<font size="4">{self.cur_frequency / 1e6:.7f}</font><font size="2"> MHz</font>')

    @property
    def sort_key(self):
        return self.bus_channel, self.channel

    def setup_monitoring(self, enable):
        if conn := self.dm.comm:
            conn.monitor_probe(enable, self.bus_channel, self.channel)

    def on_monitor(self, *, value, **_):
        self.cur_frequency = value * self.dm.dds_sysclk / 2 ** 32

    @staticmethod
    def extract_key(*, channel, probe, **_):
        return channel, probe
