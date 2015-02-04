from artiq.gui.explib import GladeControls


class Controls(GladeControls):
    def __init__(self, facilities):
        GladeControls.__init__(self, facilities,
                               "flopping_f_simulation_gui.glade")

    def finalize(self):
        getparam = self.builder.get_object("getparam")
        getparam.connect("clicked", self.getparam)

    def getparam(self, widget):
        F0 = self.facilities.get_parameter("flopping_freq")
        self.builder.get_object("F0").set_value(F0)

    def get_arguments(self):
        return {
            "F0": self.builder.get_object("F0").get_value()
        }
