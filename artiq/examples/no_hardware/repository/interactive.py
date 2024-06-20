from artiq.experiment import *


class InteractiveDemo(EnvExperiment):
    def build(self):
        pass

    def run(self):
        print("Waiting for user input...")
        with self.interactive(title="Interactive Demo") as interactive:
            interactive.setattr_argument("pyon_value",
                                         PYONValue(self.get_dataset("foo", default=42)))
            interactive.setattr_argument("number", NumberValue(42e-6,
                                         unit="us",
                                         precision=4))
            interactive.setattr_argument("integer", NumberValue(42,
                                         step=1, precision=0))
            interactive.setattr_argument("string", StringValue("Hello World"))
            interactive.setattr_argument("scan", Scannable(global_max=400,
                                         default=NoScan(325),
                                         precision=6))
            interactive.setattr_argument("boolean", BooleanValue(True), "Group")
            interactive.setattr_argument("enum",
                                         EnumerationValue(["foo", "bar", "quux"], "foo"),
                                         "Group")
        print("Done! Values:")
        print(interactive.pyon_value)
        print(interactive.boolean)
        print(interactive.enum)
        print(interactive.number, type(interactive.number))
        print(interactive.integer, type(interactive.integer))
        print(interactive.string)
        for i in interactive.scan:
            print(i)
