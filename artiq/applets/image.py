#!/usr/bin/env python3

import PyQt5  # make sure pyqtgraph imports Qt5
import pyqtgraph

from artiq.applets.simple import SimpleApplet


class Image(pyqtgraph.ImageView):
    def __init__(self, args):
        pyqtgraph.ImageView.__init__(self)
        self.args = args

    def data_changed(self, data, mods):
        try:
            img = data[self.args.img][1]
        except KeyError:
            return
        self.setImage(img)


def main():
    applet = SimpleApplet(Image)
    applet.add_dataset("img", "image data (2D numpy array)")
    applet.run()

if __name__ == "__main__":
    main()
