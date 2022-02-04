#!/usr/bin/env python3

from PyQt5 import QtWidgets

from artiq.applets.simple import SimpleApplet


class NumberWidget(QtWidgets.QLCDNumber):
    def __init__(self, args):
        QtWidgets.QLCDNumber.__init__(self)
        self.setDigitCount(args.digit_count)
        self.dataset_name = args.dataset

    def data_changed(self, data, mods):
        try:
            n = float(data[self.dataset_name][1])
        except (KeyError, ValueError, TypeError):
            n = "---"
        self.display(n)


def main():
    applet = SimpleApplet(NumberWidget)
    applet.add_dataset("dataset", "dataset to show")
    applet.argparser.add_argument("--digit-count", type=int, default=10,
                                  help="total number of digits to show")
    applet.run()

if __name__ == "__main__":
    main()
