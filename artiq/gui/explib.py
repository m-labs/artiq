import asyncio as _aio


class BaseControls:
    def __init__(self, facilities):
        self.facilities = facilities

    @_aio.coroutine
    def build(self):
        self.finalize()

    def finalize(self):
        pass


class GladeControls(BaseControls):
    def __init__(self, facilities, glade_file, top_widget_name="top"):
        BaseControls.__init__(self, facilities)
        self.glade_file = glade_file
        self.top_widget_name = top_widget_name

    @_aio.coroutine
    def build(self):
        # lazy import GTK so that the artiq top-level
        # (which imports from us) can be imported on systems
        # without GTK installed
        from gi.repository import Gtk

        self.builder = Gtk.Builder()
        data = yield from self.facilities.get_data(self.glade_file)
        self.builder.add_from_string(data)
        self.finalize()

    def get_top_widget(self):
        return self.builder.get_object(self.top_widget_name)
