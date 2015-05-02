from artiq import *


class Handover(Experiment, AutoDB):
    class DBKeys:
        core = Device()
        led = Device()

    @kernel
    def blink_once(self):
        self.led.pulse(250*ms)
        delay(250*ms)

    def run(self):
        while True:
            self.blink_once()
