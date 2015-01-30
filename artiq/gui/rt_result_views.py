from gi.repository import Gtk
import cairoplot

from artiq.gui.tools import Window


class RawWindow(Window):
    def __init__(self, set_names):
        self.labels = dict()

        Window.__init__(self, title="Raw values",
                        default_size=(200, 150))

        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        self.add(grid)
        for i, name in enumerate(set_names):
            grid.attach(Gtk.Label(name), 0, i, 1, 1)
            label = Gtk.Label("-")
            self.labels[name] = label
            grid.attach(label, 1, i, 1, 1)

    def delete(self):
        self.close()

    def set_data(self, data):
        for name, label in self.labels.items():
            if name in data:
                label.set_text(str(data[name]))


class PlotWindow(Window):
    def __init__(self, set_names):
        self.set_names = set_names
        self.data = None

        Window.__init__(self, title="/".join(set_names),
                        default_size=(700, 500))

        self.darea = Gtk.DrawingArea()
        self.darea.set_size_request(100, 100)
        self.darea.connect("draw", self.on_draw)
        self.add(self.darea)

    def delete(self):
        self.close()


class XYWindow(PlotWindow):
    def on_draw(self, widget, ctx):
        if self.data is not None:
            data = self.filter_data()
            cairoplot.scatter_plot(
                ctx,
                data=data,
                width=widget.get_allocated_width(),
                height=widget.get_allocated_height(),
                x_bounds=(min(data[0])*0.98, max(data[0])*1.02),
                y_bounds=(min(data[1])*0.98, max(data[1])*1.02),
                border=20, axis=True, grid=True,
                dots=1, discrete=True,
                series_colors=[(0.0, 0.0, 0.0)],
                background="white"
            )

    def filter_data(self):
        return [
            self.data[self.set_names[0]],
            self.data[self.set_names[1]],
        ]

    def set_data(self, data):
        self.data = data
        if not self.data:
            return
        # The two axes are not updated simultaneously.
        # Redraw only after receiving a new point for each.
        x, y = self.filter_data()
        if len(x) == len(y):
            self.darea.queue_draw()
