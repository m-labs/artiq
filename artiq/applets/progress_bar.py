#!/usr/bin/env python3

from PyQt5 import QtWidgets

from artiq.applets.simple import SimpleApplet


class ProgressWidget(QtWidgets.QProgressBar):
    def __init__(self, args):
        QtWidgets.QProgressBar.__init__(self)
        self.setMinimum(args.min)
        self.setMaximum(args.max)
        self.dataset_value = args.value

    def data_changed(self, data, mods):
        try:
            value = round(data[self.dataset_value][1])
        except (KeyError, ValueError, TypeError):
            value = 0
        self.setValue(value)



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
