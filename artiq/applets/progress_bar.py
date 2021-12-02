#!/usr/bin/env python3

from PyQt5 import QtWidgets

from artiq.applets.simple import SimpleApplet


class ProgressWidget(QtWidgets.QProgressBar):
    def __init__(self, args):
        QtWidgets.QProgressBar.__init__(self)
        self.setMaximum(args.max)
        self.setMinimum(args.min)
        self.dataset_n = args.n
        self.dataset_n_max = args.n_max

    def data_changed(self, data, mods):
        try:
            n = int(round(data[self.dataset_n][1]))
            n_max = int(round(data[self.dataset_n_max][1]))
        except (KeyError, ValueError, TypeError):
            n = 0
            n_max = 0
        self.setMaximum(n_max)
        self.setValue(n)


def main():
    applet = SimpleApplet(ProgressWidget)
    applet.add_dataset("n", "counter")
    applet.add_dataset("n_max", "maximimum counter")
    applet.argparser.add_argument("--min", type=int, default=0,
                                  help="minimum")
    applet.argparser.add_argument("--max", type=int, default=100,
                                  help="maximum")
    applet.run()

if __name__ == "__main__":
    main()
