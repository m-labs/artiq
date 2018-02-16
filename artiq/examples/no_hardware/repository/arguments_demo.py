import logging

from artiq.experiment import *


class SubComponent1(HasEnvironment):
    def build(self):
        self.setattr_argument("sc1_scan",
            Scannable(default=[NoScan(3250), RangeScan(10, 20, 6, randomize=True)],
                      unit="kHz"),
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
        self.setattr_argument("sc2_scan", Scannable(
                                          default=RangeScan(200, 300, 49)),
                              "Transporter")
        self.setattr_argument("sc2_enum", EnumerationValue(["3", "4", "5"]),
                              "Transporter")

    def do(self):
        print("SC2:")
        print(self.sc2_boolean)
        for i in self.sc2_scan:
            print(i)
        print(self.sc2_enum)


class ArgumentsDemo(EnvExperiment):
    def build(self):
        # change the "foo" dataset and click the "recompute argument"
        # buttons.
        self.setattr_argument("pyon_value",
            PYONValue(self.get_dataset("foo", default=42)))
        self.setattr_argument("number", NumberValue(42e-6,
                                                    unit="us",
                                                    ndecimals=4))
        self.setattr_argument("integer", NumberValue(42,
                                                     step=1, ndecimals=0))
        self.setattr_argument("string", StringValue("Hello World"))
        self.setattr_argument("scan", Scannable(global_max=400,
                                                default=NoScan(325),
                                                ndecimals=6))
        self.setattr_argument("boolean", BooleanValue(True), "Group")
        self.setattr_argument("enum", EnumerationValue(
            ["foo", "bar", "quux"], "foo"), "Group")

        self.sc1 = SubComponent1(self)
        self.sc2 = SubComponent2(self)

    def run(self):
        logging.error("logging test: error")
        logging.warning("logging test: warning")
        logging.warning("logging test:" + " this is a very long message."*15)
        logging.info("logging test: info")
        logging.debug("logging test: debug")

        print(self.pyon_value)
        print(self.boolean)
        print(self.enum)
        print(self.number, type(self.number))
        print(self.integer, type(self.integer))
        print(self.string)
        for i in self.scan:
            print(i)
        self.sc1.do()
        self.sc2.do()
