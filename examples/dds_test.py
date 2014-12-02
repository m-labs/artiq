from artiq import *
from artiq.coredevice import comm_serial, core, dds, gpio


class DDSTest(AutoContext):
    a = Device("dds")
    b = Device("dds")
    c = Device("dds")
    d = Device("dds")
    led = Device("gpio_out")

    @kernel
    def run(self):
        for i in range(10000):
            if i & 0x200:
                self.led.on()
            else:
                self.led.off()
            with parallel:
                with sequential:
                    self.a.pulse(100*MHz + 4*i*kHz, 500*us)
                    self.b.pulse(120*MHz, 500*us)
                with sequential:
                    self.c.pulse(200*MHz, 100*us)
                    self.d.pulse(250*MHz, 200*us)
        self.led.off()


def main():
    with comm_serial.Comm() as comm:
        coredev = core.Core(comm)
        exp = DDSTest(
            core=coredev,
            a=dds.DDS(core=coredev, dds_sysclk=1*GHz,
                      reg_channel=0, rtio_switch=2),
            b=dds.DDS(core=coredev, dds_sysclk=1*GHz,
                      reg_channel=1, rtio_switch=3),
            c=dds.DDS(core=coredev, dds_sysclk=1*GHz,
                      reg_channel=2, rtio_switch=4),
            d=dds.DDS(core=coredev, dds_sysclk=1*GHz,
                      reg_channel=3, rtio_switch=5),
            led=gpio.GPIOOut(core=coredev, channel=0)
        )
        exp.run()

if __name__ == "__main__":
    main()
