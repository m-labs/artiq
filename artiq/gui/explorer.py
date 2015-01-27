import asyncio

from gi.repository import Gtk

from artiq.gui.tools import Window, getitem


class ExplorerWindow(Window):
    def __init__(self, exit_fn, schedule_ctl, repository, layout_dict=dict()):
        self.schedule_ctl = schedule_ctl
        self.repository = repository

        Window.__init__(self,
                        title="Explorer",
                        default_size=(800, 570),
                        layout_dict=layout_dict)
        self.connect("delete-event", exit_fn)

        topvbox = Gtk.VBox(spacing=6)
        self.add(topvbox)

        menubar = Gtk.MenuBar()
        topvbox.pack_start(menubar, False, False, 0)

        windows = Gtk.MenuItem("Windows")
        windows_menu = Gtk.Menu()
        menuitem = Gtk.MenuItem("Scheduler")
        windows_menu.append(menuitem)
        menuitem = Gtk.MenuItem("Parameters")
        windows_menu.append(menuitem)
        windows_menu.append(Gtk.SeparatorMenuItem())
        menuitem = Gtk.MenuItem("Quit")
        menuitem.connect("activate", exit_fn)
        windows_menu.append(menuitem)
        windows.set_submenu(windows_menu)
        menubar.append(windows)

        self.pane = Gtk.HPaned(
            position=getitem(layout_dict, "pane_position", 180))
        topvbox.pack_start(self.pane, True, True, 0)

        listvbox = Gtk.VBox(spacing=6)
        self.pane.pack1(listvbox)
        self.list_store = Gtk.ListStore(str)
        self.list_tree = Gtk.TreeView(self.list_store)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.list_tree)
        listvbox.pack_start(scroll, True, True, 0)
        button = Gtk.Button("Run")
        button.connect("clicked", self.run)
        listvbox.pack_start(button, False, False, 0)

    def get_layout_dict(self):
        r = Window.get_layout_dict(self)
        r["pane_position"] = self.pane.get_position()
        return r

    @asyncio.coroutine
    def load_controls(self):
        gui_mod_data = yield from self.repository.get_data(
            "flopping_f_simulation_gui.py")
        gui_mod = dict()
        exec(gui_mod_data, gui_mod)
        self.controls = gui_mod["Controls"]()
        yield from self.controls.build(self.repository.get_data)
        self.pane.pack2(self.controls.get_top_widget())

    def run(self, widget):
        run_params = {
            "file": "flopping_f_simulation.py",
            "unit": None,
            "arguments": self.controls.get_arguments()
        }
        asyncio.Task(self.schedule_ctl.run_queued(run_params, None))
