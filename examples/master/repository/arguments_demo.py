from artiq import *


class SubComponent1(HasEnvironment):
    def build(self):
        self.attr_argument("sc1_scan", Scannable(default=NoScan(325)),
                           "Flux capacitor")
        self.attr_argument("sc1_enum", EnumerationValue(["1", "2", "3"]),
                           "Flux capacitor")

    def do(self):
        print("SC1:")
        for i in self.sc1_scan:
            print(i)
        print(self.sc1_enum)


class SubComponent2(HasEnvironment):
    def build(self):
        self.attr_argument("sc2_boolean", BooleanValue(False),
                           "Transporter")
        self.attr_argument("sc2_scan", Scannable(default=NoScan(325)),
                           "Transporter")
        self.attr_argument("sc2_enum", EnumerationValue(["3", "4", "5"]),
                           "Transporter")

    def do(self):
        print("SC2:")
        print(self.sc2_boolean)
        for i in self.sc2_scan:
            print(i)
        print(self.sc2_enum)


class ArgumentsDemo(EnvExperiment):
    def build(self):
        self.attr_argument("free_value", FreeValue(None))
        self.attr_argument("number", NumberValue(42, unit="s", step=0.1))
        self.attr_argument("string", StringValue("Hello World"))
        self.attr_argument("scan", Scannable(global_max=400, default=NoScan(325)))
        self.attr_argument("boolean", BooleanValue(True), "Group")
        self.attr_argument("enum", EnumerationValue(
            ["foo", "bar", "quux"], "foo"), "Group")

        self.sc1 = SubComponent1(parent=self)
        self.sc2 = SubComponent2(parent=self)

    def run(self):
        print(self.free_value)
        print(self.boolean)
        print(self.enum)
        print(self.number)
        print(self.string)
        for i in self.scan:
            print(i)
        self.sc1.do()
        self.sc2.do()
