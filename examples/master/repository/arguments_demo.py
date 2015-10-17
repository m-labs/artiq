from artiq import *


class SubComponent1(HasEnvironment):
    def build(self):
        self.setattr_argument("sc1_scan", Scannable(default=NoScan(3250),
                                                    scale=1e3, unit="Hz"),
                              "Flux capacitor")
        self.setattr_argument("sc1_enum", EnumerationValue(["1", "2", "3"]),
                              "Flux capacitor")

    def do(self):
        print("SC1:")
        for i in self.sc1_scan:
            print(i)
        print(self.sc1_enum)


class SubComponent2(HasEnvironment):
    def build(self):
        self.setattr_argument("sc2_boolean", BooleanValue(False),
                              "Transporter")
        self.setattr_argument("sc2_scan", Scannable(default=NoScan(325)),
                              "Transporter")
        self.setattr_argument("sc2_enum", EnumerationValue(["3", "4", "5"]),
                              "Transporter")

    def do(self):
        print("SC2:")
        print(self.sc2_boolean)
        for i in self.sc2_scan:
            print(i)
        print(self.sc2_enum)


class ArgumentsDemo(EnvExperiment, LogExperiment):
    def build(self):
        self.init_logger()

        self.setattr_argument("free_value", FreeValue(None))
        self.setattr_argument("number", NumberValue(42e-6,
                                                    unit="s", scale=1e-6,
                                                    ndecimals=4))
        self.setattr_argument("string", StringValue("Hello World"))
        self.setattr_argument("scan", Scannable(global_max=400,
                                                default=NoScan(325),
                                                ndecimals=6))
        self.setattr_argument("boolean", BooleanValue(True), "Group")
        self.setattr_argument("enum", EnumerationValue(
            ["foo", "bar", "quux"], "foo"), "Group")

        self.sc1 = SubComponent1(parent=self)
        self.sc2 = SubComponent2(parent=self)

    def run(self):
        self.logger.error("logging test: error")
        self.logger.warning("logging test: warning")
        self.logger.info("logging test: info")
        self.logger.debug("logging test: debug")

        print(self.free_value)
        print(self.boolean)
        print(self.enum)
        print(self.number)
        print(self.string)
        for i in self.scan:
            print(i)
        self.sc1.do()
        self.sc2.do()
