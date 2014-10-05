from artiq import *
from artiq.devices import corecom_serial, core, dds_core, gpio_core


class DDSTest(AutoContext):
    parameters = "a b c d led"

    @kernel
    def run(self):
        for i in range(10000):
            if i & 0x200:
                self.led.set(1)
            else:
                self.led.set(0)
            with parallel:
                with sequential:
                    self.a.pulse(100*MHz + 4*i*kHz, 500*us)
                    self.b.pulse(120*MHz, 500*us)
                with sequential:
                    self.c.pulse(200*MHz, 100*us)
                    self.d.pulse(250*MHz, 200*us)
        self.led.set(0)


def main():
    with corecom_serial.CoreCom() as com:
        coredev = core.Core(com)
        exp = DDSTest(
            core=coredev,
            a=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                           reg_channel=0, rtio_channel=0),
            b=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                           reg_channel=1, rtio_channel=1),
            c=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                           reg_channel=2, rtio_channel=2),
            d=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                           reg_channel=3, rtio_channel=3),
            led=gpio_core.GPIOOut(core=coredev, channel=1)
        )
        exp.run()

if __name__ == "__main__":
    main()
