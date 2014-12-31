from gi.repository import Gtk

from artiq.gui.tools import Window


class ParametersWindow(Window):
    def __init__(self):
        Window.__init__(self, title="Parameters")
        self.set_default_size(500, 500)

        self.parameters_store = Gtk.ListStore(str, str)
        tree = Gtk.TreeView(self.parameters_store)
        for i, title in enumerate(["Parameter", "Value"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.add(tree)
        self.add(scroll)
