import unittest
from operator import itemgetter
import os

from artiq import *
from artiq.coredevice import comm_serial, core, runtime_exceptions, rtio
from artiq.sim import devices as sim_devices


no_hardware = bool(os.getenv("ARTIQ_NO_HARDWARE"))


def _run_on_device(k_class, **parameters):
    with comm_serial.Comm() as comm:
        coredev = core.Core(comm)
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


class _Attributes(AutoContext):
    def build(self):
        self.input = 84

    @kernel
    def run(self):
        self.result = self.input//2


class _PulseLogger(AutoContext):
    parameters = "output_list name"

    def _append(self, t, l, f):
        if not hasattr(self, "first_timestamp"):
            self.first_timestamp = t
        self.output_list.append((self.name, t-self.first_timestamp, l, f))

    def on(self, t, f):
        self._append(t, True, f)

    def off(self, t):
        self._append(t, False, 0)

    @kernel
    def pulse(self, f, duration):
        self.on(int(now().amount*1000000000), f)
        delay(duration)
        self.off(int(now().amount*1000000000))


class _Pulses(AutoContext):
    parameters = "output_list"

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


@unittest.skipIf(no_hardware, "no hardware")
class ExecutionCase(unittest.TestCase):
    def test_primes(self):
        l_device, l_host = [], []
        _run_on_device(_Primes, max=100, output_list=l_device)
        _run_on_host(_Primes, max=100, output_list=l_host)
        self.assertEqual(l_device, l_host)

    def test_attributes(self):
        with comm_serial.Comm() as comm:
            coredev = core.Core(comm)
            uut = _Attributes(core=coredev)
            uut.run()
            self.assertEqual(uut.result, 42)

    def test_pulses(self):
        l_device, l_host = [], []
        _run_on_device(_Pulses, output_list=l_device)
        _run_on_host(_Pulses, output_list=l_host)
        l_host = sorted(l_host, key=itemgetter(1))
        for channel in "a", "b", "c", "d":
            c_device = [x for x in l_device if x[0] == channel]
            c_host = [x for x in l_host if x[0] == channel]
            self.assertEqual(c_device, c_host)

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
            self.i.gate_rising(10*us)
        self.report(self.i.count())


class _RTIOUnderflow(AutoContext):
    parameters = "o"

    @kernel
    def run(self):
        while True:
            delay(25*ns)
            self.o.pulse(25*ns)


class _RTIOSequenceError(AutoContext):
    parameters = "o"

    @kernel
    def run(self):
        t = now()
        self.o.pulse(25*us)
        at(t)
        self.o.pulse(25*us)


@unittest.skipIf(no_hardware, "no hardware")
class RTIOCase(unittest.TestCase):
    # Connect channels 0 and 1 together for this test
    # (C11 and C13 on Papilio Pro)
    def test_loopback(self):
        npulses = 4
        with comm_serial.Comm() as comm:
            coredev = core.Core(comm)
            uut = _RTIOLoopback(
                core=coredev,
                i=rtio.RTIOIn(core=coredev, channel=0),
                o=rtio.RTIOOut(core=coredev, channel=1),
                npulses=npulses
            )
            uut.run()
            self.assertEqual(uut.result, npulses)

    def test_underflow(self):
        with comm_serial.Comm() as comm:
            coredev = core.Core(comm)
            uut = _RTIOUnderflow(
                core=coredev,
                o=rtio.RTIOOut(core=coredev, channel=1)
            )
            with self.assertRaises(runtime_exceptions.RTIOUnderflow):
                uut.run()

    def test_sequence_error(self):
        with comm_serial.Comm() as comm:
            coredev = core.Core(comm)
            uut = _RTIOSequenceError(
                core=coredev,
                o=rtio.RTIOOut(core=coredev, channel=1)
            )
            with self.assertRaises(runtime_exceptions.RTIOSequenceError):
                uut.run()
