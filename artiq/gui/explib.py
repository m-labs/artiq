import asyncio

from gi.repository import Gtk


class BaseControls:
    def __init__(self, facilities):
        self.facilities = facilities

    @asyncio.coroutine
    def build(self):
        self.finalize()

    def finalize(self):
        pass


class GladeControls(BaseControls):
    def __init__(self, facilities, glade_file, top_widget_name="top"):
        BaseControls.__init__(self, facilities)
        self.glade_file = glade_file
        self.top_widget_name = top_widget_name

    @asyncio.coroutine
    def build(self):
        self.builder = Gtk.Builder()
        data = yield from self.facilities.get_data(self.glade_file)
        self.builder.add_from_string(data)
        self.finalize()

    def get_top_widget(self):
        return self.builder.get_object(self.top_widget_name)
