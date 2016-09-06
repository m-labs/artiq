from PyQt5 import QtWidgets

from artiq.applets.simple import SimpleApplet


class DemoWidget(QtWidgets.QLabel):
    def __init__(self, args):
        QtWidgets.QLabel.__init__(self)
        self.dataset_name = args.dataset

    def data_changed(self, data, mods):
        try:
            n = str(data[self.dataset_name][1])
        except (KeyError, ValueError, TypeError):
            n = "---"
        n = "<font size=15>" + n + "</font>"
        self.setText(n)


def main():
    applet = SimpleApplet(DemoWidget)
    applet.add_dataset("dataset", "dataset to show")
    applet.run()

if __name__ == "__main__":
    main()
