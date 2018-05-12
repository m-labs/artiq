import unittest

from migen import *

from artiq.gateware.serwb import packet
from artiq.gateware.serwb.phy import _SerdesMasterInit, _SerdesSlaveInit


class SerdesModel(Module):
    def __init__(self, taps, mode="slave"):
        self.tx_idle = Signal()
        self.tx_comma = Signal()
        self.rx_idle = Signal()
        self.rx_comma = Signal()

        self.rx_bitslip_value = Signal(6)
        self.rx_delay_rst = Signal()
        self.rx_delay_inc = Signal()

        self.valid_bitslip = Signal(6)
        self.valid_delays = Signal(taps)

        # # #

        delay = Signal(max=taps)
        bitslip = Signal(6)

        valid_delays = Array(Signal() for i in range(taps))
        for i in range(taps):
            self.comb += valid_delays[taps-1-i].eq(self.valid_delays[i])

        self.sync += [
            bitslip.eq(self.rx_bitslip_value),
            If(self.rx_delay_rst,
                delay.eq(0)
            ).Elif(self.rx_delay_inc,
                delay.eq(delay + 1)
            )
        ]

        if mode == "master":
            self.submodules.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
            self.comb += self.fsm.reset.eq(self.tx_idle)
            fsm.act("IDLE",
                If(self.tx_comma,
                    NextState("SEND_COMMA")
                ),
                self.rx_idle.eq(1)
            )
            fsm.act("SEND_COMMA",
                If(valid_delays[delay] &
                   (bitslip == self.valid_bitslip),
                        self.rx_comma.eq(1)
                ),
                If(~self.tx_comma,
                    NextState("READY")
                )
            )
            fsm.act("READY")
        elif mode == "slave":
            self.submodules.fsm = fsm = FSM(reset_state="IDLE")
            fsm.act("IDLE",
                self.rx_idle.eq(1),
                NextState("SEND_COMMA")
            )
            fsm.act("SEND_COMMA",
                If(valid_delays[delay] &
                   (bitslip == self.valid_bitslip),
                        self.rx_comma.eq(1)
                ),
                If(~self.tx_idle,
                    NextState("READY")
                )
            )
            fsm.act("READY")


class DUTMaster(Module):
    def __init__(self, taps=32):
        self.submodules.serdes = SerdesModel(taps, mode="master")
        self.submodules.init = _SerdesMasterInit(self.serdes, taps, timeout=1)


class DUTSlave(Module):
    def __init__(self, taps=32):
        self.submodules.serdes = SerdesModel(taps, mode="slave")
        self.submodules.init = _SerdesSlaveInit(self.serdes, taps, timeout=1)


def generator(test, dut, valid_bitslip, valid_delays, check_success):
    yield dut.serdes.valid_bitslip.eq(valid_bitslip)
    yield dut.serdes.valid_delays.eq(valid_delays)
    while not ((yield dut.init.ready) or 
               (yield dut.init.error)):
        yield
    if check_success:
        ready = (yield dut.init.ready)
        error = (yield dut.init.error)
        delay_min = (yield dut.init.delay_min)
        delay_max = (yield dut.init.delay_max)
        delay = (yield dut.init.delay)
        bitslip = (yield dut.init.bitslip)
        test.assertEqual(ready, 1)
        test.assertEqual(error, 0)
        test.assertEqual(delay_min, 4)
        test.assertEqual(delay_max, 9)
        test.assertEqual(delay, 6)
        test.assertEqual(bitslip, valid_bitslip)
    else:
        ready = (yield dut.init.ready)
        error = (yield dut.init.error)
        test.assertEqual(ready, 0)
        test.assertEqual(error, 1)


class TestSERWBInit(unittest.TestCase):
    def test_master_init_success(self):
        dut = DUTMaster()
        valid_bitslip = 2
        valid_delays = 0b10001111100000111110000011111000
        run_simulation(dut, generator(self, dut, valid_bitslip, valid_delays, True))

    def test_master_init_failure(self):
        # too small window
        dut = DUTMaster()
        valid_bitslip = 2
        valid_delays = 0b00000000000000010000000000000000
        run_simulation(dut, generator(self, dut, valid_bitslip, valid_delays, False))

    def test_slave_init_success(self):
        dut = DUTSlave()
        valid_bitslip = 2
        valid_delays = 0b10001111100000111110000011111000
        run_simulation(dut, generator(self, dut, valid_bitslip, valid_delays, True))

    def test_slave_init_failure(self):
        # too small window
        dut = DUTSlave()
        valid_bitslip = 2
        valid_delays = 0b00000000000000010000000000000000
        run_simulation(dut, generator(self, dut, valid_bitslip, valid_delays, False))
