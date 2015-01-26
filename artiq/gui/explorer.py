import asyncio

from gi.repository import Gtk

from artiq.gui.tools import Window, getitem


_test_description = """
<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated with glade 3.18.3 -->
<interface>
  <requires lib="gtk+" version="3.12"/>
  <object class="GtkAdjustment" id="adjustment1">
    <property name="lower">1000</property>
    <property name="upper">2000</property>
    <property name="value">1500</property>
    <property name="step_increment">1</property>
    <property name="page_increment">10</property>
  </object>
  <object class="GtkBox" id="top">
    <property name="visible">True</property>
    <property name="can_focus">False</property>
    <child>
      <object class="GtkLabel" id="label1">
        <property name="visible">True</property>
        <property name="can_focus">False</property>
        <property name="label" translatable="yes">Simulated flopping frequency</property>
      </object>
      <packing>
        <property name="expand">False</property>
        <property name="fill">True</property>
        <property name="position">0</property>
      </packing>
    </child>
    <child>
      <object class="GtkSpinButton" id="spinbutton1">
        <property name="visible">True</property>
        <property name="can_focus">True</property>
        <property name="input_purpose">number</property>
        <property name="adjustment">adjustment1</property>
      </object>
      <packing>
        <property name="expand">False</property>
        <property name="fill">True</property>
        <property name="position">1</property>
      </packing>
    </child>
  </object>
</interface>
"""


class _ExperimentControls:
    def __init__(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_string(_test_description)

    def get_top_widget(self):
        return self.builder.get_object("top")

    def get_arguments(self):
        return {
            "F0": self.builder.get_object("adjustment1").get_value()
        }


class ExplorerWindow(Window):
    def __init__(self, schedule_ctl, layout_dict=dict()):
        self.schedule_ctl = schedule_ctl

        Window.__init__(self,
                        title="Explorer",
                        default_size=(800, 570),
                        layout_dict=layout_dict)

        topvbox = Gtk.VBox(spacing=6)
        self.add(topvbox)

        menubar = Gtk.MenuBar()
        topvbox.pack_start(menubar, False, False, 0)

        windows = Gtk.MenuItem("Windows")
        windows_menu = Gtk.Menu()
        scheduler = Gtk.MenuItem("Scheduler")
        parameters = Gtk.MenuItem("Parameters")
        quit = Gtk.MenuItem("Quit")
        windows_menu.append(scheduler)
        windows_menu.append(parameters)
        windows_menu.append(Gtk.SeparatorMenuItem())
        windows_menu.append(quit)
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

        self.controls = _ExperimentControls()
        self.pane.pack2(self.controls.get_top_widget())

    def get_layout_dict(self):
        r = Window.get_layout_dict(self)
        r["pane_position"] = self.pane.get_position()
        return r

    def run(self, widget):
        run_params = {
            "file": "flopping_f_simulation.py",
            "unit": None,
            "arguments": self.controls.get_arguments()
        }
        asyncio.Task(self.schedule_ctl.run_queued(run_params, None))
