import asyncio

from gi.repository import Gtk


class Controls:
    @asyncio.coroutine
    def build(self, get_data):
        self.builder = Gtk.Builder()
        data = yield from get_data("flopping_f_simulation_gui.glade")
        self.builder.add_from_string(data)

    def get_top_widget(self):
        return self.builder.get_object("top")

    def get_arguments(self):
        return {
            "F0": self.builder.get_object("F0").get_value()
        }
