from PyQt5 import QtWidgets

from artiq.applets.simple import SimpleApplet


class DemoWidget(QtWidgets.QLabel):
    def __init__(self, args, ctl):
        QtWidgets.QLabel.__init__(self)
        self.dataset_name = args.dataset

    def data_changed(self, value, metadata, persist, mods):
        try:
            n = str(value[self.dataset_name])
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
