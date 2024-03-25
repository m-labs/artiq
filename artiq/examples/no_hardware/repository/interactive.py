from artiq.experiment import *


class InteractiveDemo(EnvExperiment):
    def build(self):
        pass

    def run(self):
        print("Waiting for user input...")
        with self.interactive() as interactive:
            interactive.setattr_argument("number", NumberValue(42e-6,
                                                   unit="us",
                                                   precision=4))
            interactive.setattr_argument("integer", NumberValue(42,
                                                    step=1, precision=0))
            interactive.setattr_argument("string", StringValue("Hello World"))
        print("Done! Values:")
        print(interactive.number, type(interactive.number))
        print(interactive.integer, type(interactive.integer))
        print(interactive.string)
