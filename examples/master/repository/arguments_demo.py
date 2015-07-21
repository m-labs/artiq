from artiq import *


class ArgumentsDemo(EnvExperiment):
    def build(self):
        self.attr_argument("free_value", FreeValue(None))
        self.attr_argument("boolean", BooleanValue(True))
        self.attr_argument("enum", EnumerationValue(
            ["foo", "bar", "quux"], "foo"))
        self.attr_argument("number", NumberValue(42, unit="s", step=0.1))
        self.attr_argument("string", StringValue("Hello World"))
        self.attr_argument("scan", Scannable(global_max=400, default=NoScan(325)))

    def run(self):
        print(self.free_value)
        print(self.boolean)
        print(self.enum)
        print(self.number)
        print(self.string)
        for i in self.scan:
            print(i)
