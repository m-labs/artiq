import os
import time

from artiq.experiment import *


# Do the applet source code path determination on import.
# ARTIQ imports the experiment, then changes the current
# directory to the results, then instantiates the experiment.
# In Python __file__ is a relative path which is not updated
# when the current directory is changed.
custom_applet = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                             "custom_applet.py"))


class CreateCodeApplet(EnvExperiment):
    def build(self):
        self.setattr_device("ccb")

    def run(self):
        with open(custom_applet) as f:
            self.ccb.issue("create_applet", "code_applet_example",
               "code_applet_dataset", code=f.read(), group="autoapplet")
            for i in reversed(range(10)):
                self.set_dataset("code_applet_dataset", i,
                                 broadcast=True, archive=False)
                time.sleep(1)
            self.ccb.issue("disable_applet", "code_applet_example",
                           group="autoapplet")
