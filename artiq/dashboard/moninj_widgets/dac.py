from artiq.dashboard.moninj_widgets import SimpleDisplayWidget


class DACWidget(SimpleDisplayWidget):
    def __init__(self, dm, spi_channel, channel, title):
        self.dm = dm
        self.spi_channel = spi_channel
        self.channel = channel
        self.cur_value = 0
        SimpleDisplayWidget.__init__(self, f"{title} ch{channel}")

    def refresh_display(self):
        self.value.setText(f'<font size="4">{self.cur_value * 100 / 2 ** 16:.3f}</font><font size="2"> %</font>')

    @property
    def sort_key(self):
        return self.spi_channel, self.channel

    def setup_monitoring(self, enable):
        if conn := self.dm.comm:
            conn.monitor_probe(enable, self.spi_channel, self.channel)

    def on_monitor(self, value):
        self.cur_value = value
        self.refresh_display()
