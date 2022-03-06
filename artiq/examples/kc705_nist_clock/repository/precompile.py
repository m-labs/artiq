from artiq.experiment import *


class Precompile(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.hello_str = "hello ARTIQ"

    def prepare(self):
    	self.precompiled = self.core.precompile(self.hello, "world")

    @kernel
    def hello(self, arg):
    	print(self.hello_str, arg)
    	self.hello_str = "nowriteback"

    def run(self):
        self.precompiled()
        self.hello_str = "noupdate"
        self.precompiled()
