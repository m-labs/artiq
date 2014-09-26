import unittest

from artiq.language.core import *
from artiq.language.units import *
from artiq.devices import corecom_serial, core, runtime_exceptions, rtio_core
from artiq.sim import devices as sim_devices


def _run_on_device(k_class, **parameters):
    with corecom_serial.CoreCom() as com:
        coredev = core.Core(com)
        k_inst = k_class(core=coredev, **parameters)
        k_inst.run()


def _run_on_host(k_class, **parameters):
    coredev = sim_devices.Core()
    k_inst = k_class(core=coredev, **parameters)
    k_inst.run()


class _Primes(AutoContext):
    parameters = "output_list max"

    @kernel
    def run(self):
        for x in range(1, self.max):
            d = 2
            prime = True
            while d*d <= x:
                if x % d == 0:
                    prime = False
                    break
                d += 1
            if prime:
                self.output_list.append(x)


class _PulseLogger(AutoContext):
    parameters = "name"

    def print_on(self, t, f):
        print("{} ON:{:4} @{}".format(self.name, f, t))

    def print_off(self, t):
        print("{}   OFF   @{}".format(self.name, t))

    @kernel
    def pulse(self, f, duration):
        self.print_on(int(now()), f)
        delay(duration)
        self.print_off(int(now()))


class _Pulses(AutoContext):
    def build(self):
        for name in "a", "b", "c", "d":
            pl = _PulseLogger(self, name=name)
            setattr(self, name, pl)

    @kernel
    def run(self):
        for i in range(3):
            with parallel:
                with sequential:
                    self.a.pulse(100+i, 20*us)
                    self.b.pulse(200+i, 20*us)
                with sequential:
                    self.c.pulse(300+i, 10*us)
                    self.d.pulse(400+i, 20*us)


class _MyException(Exception):
    pass


class _Exceptions(AutoContext):
    parameters = "trace"

    @kernel
    def run(self):
        for i in range(10):
            self.trace.append(i)
            if i == 4:
                try:
                    self.trace.append(10)
                    try:
                        self.trace.append(11)
                        break
                    except:
                        pass
                    else:
                        self.trace.append(12)
                    try:
                        self.trace.append(13)
                    except:
                        pass
                except _MyException:
                    self.trace.append(14)

        for i in range(4):
            try:
                self.trace.append(100)
                if i == 1:
                    raise _MyException
                elif i == 2:
                    raise IndexError
            except (TypeError, IndexError):
                self.trace.append(101)
                raise
            except:
                self.trace.append(102)
            else:
                self.trace.append(103)
            finally:
                self.trace.append(104)


class SimCompareCase(unittest.TestCase):
    def test_primes(self):
        l_device, l_host = [], []
        _run_on_device(_Primes, max=100, output_list=l_device)
        _run_on_host(_Primes, max=100, output_list=l_host)
        self.assertEqual(l_device, l_host)

    def test_pulses(self):
        # TODO: compare results on host and device
        # (this requires better unit management in the compiler)
        _run_on_device(_Pulses)

    def test_exceptions(self):
        t_device, t_host = [], []
        with self.assertRaises(IndexError):
            _run_on_device(_Exceptions, trace=t_device)
        with self.assertRaises(IndexError):
            _run_on_host(_Exceptions, trace=t_host)
        self.assertEqual(t_device, t_host)


class _RTIOLoopback(AutoContext):
    parameters = "i o npulses"

    def report(self, n):
        self.result = n

    @kernel
    def run(self):
        with parallel:
            with sequential:
                for i in range(self.npulses):
                    delay(25*ns)
                    self.o.pulse(25*ns)
            self.i.count_rising(10*us)
        self.report(self.i.sync())


class _RTIOUnderflow(AutoContext):
    parameters = "o"

    @kernel
    def run(self):
        while True:
            delay(25*ns)
            self.o.pulse(25*ns)


class RTIOCase(unittest.TestCase):
    def test_loopback(self):
        npulses = 4
        with corecom_serial.CoreCom() as com:
            coredev = core.Core(com)
            uut = _RTIOLoopback(
                core=coredev,
                i=rtio_core.RTIOCounter(core=coredev, channel=0),
                o=rtio_core.RTIOOut(core=coredev, channel=1),
                npulses=npulses
            )
            uut.run()
            self.assertEqual(uut.result, npulses)

    def test_underflow(self):
        with corecom_serial.CoreCom() as com:
            coredev = core.Core(com)
            uut = _RTIOUnderflow(
                core=coredev,
                o=rtio_core.RTIOOut(core=coredev, channel=1)
            )
            with self.assertRaises(runtime_exceptions.RTIOUnderflow):
                uut.run()
