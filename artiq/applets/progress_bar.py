#!/usr/bin/env python3

from PyQt5 import QtWidgets

from artiq.applets.simple import SimpleApplet


class ProgressWidget(QtWidgets.QProgressBar):
    def __init__(self, args, req):
        QtWidgets.QProgressBar.__init__(self)
        self.setMinimum(args.min)
        self.setMaximum(args.max)
        self.dataset_value = args.value

    def data_changed(self, value, metadata, persist, mods):
        try:
            val = round(value[self.dataset_value])
        except (KeyError, ValueError, TypeError):
            val = 0
        self.setValue(val)



def main():
    applet = SimpleApplet(ProgressWidget)
    applet.add_dataset("value", "counter")
    applet.argparser.add_argument("--min", type=int, default=0,
                                  help="minimum (left) value of the bar")
    applet.argparser.add_argument("--max", type=int, default=100,
                                  help="maximum (right) value of the bar")
    applet.run()

if __name__ == "__main__":
    main()
