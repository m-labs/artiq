import os

from gi.repository import Gtk


data_dir = os.path.abspath(os.path.dirname(__file__))

class Window(Gtk.Window):
    def __init__(self, *args, **kwargs):
        Gtk.Window.__init__(self, *args, **kwargs)
        self.set_wmclass("ARTIQ", "ARTIQ")
        self.set_icon_from_file(os.path.join(data_dir, "icon.png"))
        self.set_border_width(6)
