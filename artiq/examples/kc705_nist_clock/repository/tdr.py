# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

from artiq.experiment import *


class PulseNotReceivedError(Exception):
    pass


class TDR(EnvExperiment):
    """Time domain reflectometer.

    From ttl2 an impedance matched pulse is send onto a coax
    cable with an open end. pmt0 (very short stub, high impedance) also
    listens on the transmission line near ttl2.

    When the forward propagating pulse passes pmt0, the voltage is half of the
    logic voltage and does not register as a rising edge. Once the
    rising edge is reflected at an open end (same sign) and passes by pmt0 on
    its way back to ttl2, it is detected. Analogously, hysteresis leads to
    detection of the falling edge once the reflection reaches pmt0 after
    one round trip time.

    This works marginally and is just a proof of principle: it relies on
    hysteresis at FPGA inputs around half voltage and good impedance steps,
    as well as reasonably low loss cable. It does not work well for longer
    cables (>100 ns RTT). The default drive strength of 12 mA and 3.3 V would
    be ~300 Ω but it seems 40 Ω series impedance at the output matches
    the hysteresis of the input.

    This is also equivalent to a loopback tester or a delay measurement.
    """
    def build(self):
        self.setattr_device("core")
        self.setattr_device("pmt0")
        self.setattr_device("ttl2")

    def run(self):
        self.core.reset()
        n = 1000  # repetitions
        latency = 50e-9  # calibrated latency without a transmission line
        pulse = 1e-6  # pulse length, larger than rtt
        self.t = [0 for i in range(2)]
        try:
            self.many(n, self.core.seconds_to_mu(pulse))
        except PulseNotReceivedError:
            print("too few edges: cable too long or wiring bad")
        else:
            print(self.t)
            t_rise = mu_to_seconds(self.t[0], self.core)/n - latency
            t_fall = mu_to_seconds(self.t[1], self.core)/n - latency - pulse
            print("round trip times:")
            print("rising: {:5g} ns, falling {:5g} ns".format(
                t_rise/1e-9, t_fall/1e-9))

    @kernel
    def many(self, n, p):
        self.core.break_realtime()
        for i in range(n):
            self.one(p)

    @kernel
    def one(self, p):
        t0 = now_mu()
        with parallel:
            self.pmt0.gate_both_mu(2*p)
            self.ttl2.pulse_mu(p)
        for i in range(len(self.t)):
            ti = self.pmt0.timestamp_mu(now_mu())
            if ti <= 0:
                raise PulseNotReceivedError()
            self.t[i] = int(self.t[i] + ti - t0)
        self.pmt0.count(now_mu())  # flush
