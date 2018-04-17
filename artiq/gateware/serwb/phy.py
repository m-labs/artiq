from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.misc import WaitTimer

from misoc.interconnect import stream
from misoc.interconnect.csr import *

from artiq.gateware.serwb.scrambler import Scrambler, Descrambler
from artiq.gateware.serwb.kusphy import KUSSerdes
from artiq.gateware.serwb.s7phy import S7Serdes


# Master <--> Slave synchronization:
# 1) Master sends idle pattern (zeroes) to reset Slave.
# 2) Master sends K28.5 commas to allow Slave to calibrate, Slave sends idle pattern.
# 3) Slave sends K28.5 commas to allow Master to calibrate, Master sends K28.5 commas.
# 4) Master stops sending K28.5 commas.
# 5) Slave stops sending K28.5 commas.
# 6) Physical link is ready.


@ResetInserter()
class _SerdesMasterInit(Module):
    def __init__(self, serdes, taps, timeout=2**14):
        self.ready = Signal()
        self.error = Signal()

        # # #

        self.delay = delay = Signal(max=taps)
        self.delay_min = delay_min = Signal(max=taps)
        self.delay_min_found = delay_min_found = Signal()
        self.delay_max = delay_max = Signal(max=taps)
        self.delay_max_found = delay_max_found = Signal()
        self.bitslip = bitslip = Signal(max=40)

        self.submodules.timer = timer = WaitTimer(timeout)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(delay, 0),
            NextValue(delay_min, 0),
            NextValue(delay_min_found, 0),
            NextValue(delay_max, 0),
            NextValue(delay_max_found, 0),
            serdes.rx_delay_rst.eq(1),
            NextValue(bitslip, 0),
            NextState("RESET_SLAVE"),
            serdes.tx_idle.eq(1)
        )
        fsm.act("RESET_SLAVE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("SEND_PATTERN")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("SEND_PATTERN",
            If(~serdes.rx_idle,
                NextState("WAIT_STABLE")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("WAIT_STABLE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CHECK_PATTERN")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("CHECK_PATTERN",
            If(~delay_min_found,
                If(serdes.rx_comma,
                    timer.wait.eq(1),
                    If(timer.done,
                        timer.wait.eq(0),
                        NextValue(delay_min, delay),
                        NextValue(delay_min_found, 1)
                    )
                ).Else(
                    NextState("INC_DELAY_BITSLIP")
                ),
            ).Else(
                If(~serdes.rx_comma,
                    NextValue(delay_max, delay),
                    NextValue(delay_max_found, 1),
                    NextState("CHECK_SAMPLING_WINDOW")
                ).Else(
                    NextState("INC_DELAY_BITSLIP")
                )
            ),
            serdes.tx_comma.eq(1)
        )
        self.comb += serdes.rx_bitslip_value.eq(bitslip)
        fsm.act("INC_DELAY_BITSLIP",
            NextState("WAIT_STABLE"),
            If(delay == (taps - 1),
                If(bitslip == (40 - 1),
                    NextState("ERROR")
                ).Else(
                    NextValue(delay_min_found, 0),
                    NextValue(bitslip, bitslip + 1)
                ),
                NextValue(delay, 0),
                serdes.rx_delay_rst.eq(1)
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_inc.eq(1)
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("CHECK_SAMPLING_WINDOW",
            If((delay_min == 0) |
               (delay_max == (taps - 1)) |
               ((delay_max - delay_min) < taps//16),
               NextValue(delay_min_found, 0),
               NextValue(delay_max_found, 0),
               NextState("WAIT_STABLE")
            ).Else(
                NextState("CONFIGURE_SAMPLING_WINDOW")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("CONFIGURE_SAMPLING_WINDOW",
            If(delay == (delay_min + (delay_max - delay_min)[1:]),
                NextState("READY")
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_inc.eq(1),
                NextState("WAIT_SAMPLING_WINDOW")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("WAIT_SAMPLING_WINDOW",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CONFIGURE_SAMPLING_WINDOW")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("READY",
            self.ready.eq(1)
        )
        if hasattr(serdes, "rx_delay_en_vtc"):
            self.comb += serdes.rx_delay_en_vtc.eq(self.ready)
        fsm.act("ERROR",
            self.error.eq(1)
        )


@ResetInserter()
class _SerdesSlaveInit(Module, AutoCSR):
    def __init__(self, serdes, taps, timeout=2**14):
        self.ready = Signal()
        self.error = Signal()

        # # #

        self.delay = delay = Signal(max=taps)
        self.delay_min = delay_min = Signal(max=taps)
        self.delay_min_found = delay_min_found = Signal()
        self.delay_max = delay_max = Signal(max=taps)
        self.delay_max_found = delay_max_found = Signal()
        self.bitslip = bitslip = Signal(max=40)

        self.submodules.timer = timer = WaitTimer(timeout)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        # reset
        fsm.act("IDLE",
            NextValue(delay, 0),
            NextValue(delay_min, 0),
            NextValue(delay_min_found, 0),
            NextValue(delay_max, 0),
            NextValue(delay_max_found, 0),
            serdes.rx_delay_rst.eq(1),
            NextValue(bitslip, 0),
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("WAIT_STABLE"),
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("WAIT_STABLE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CHECK_PATTERN")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("CHECK_PATTERN",
            If(~delay_min_found,
                If(serdes.rx_comma,
                    timer.wait.eq(1),
                    If(timer.done,
                        timer.wait.eq(0),
                        NextValue(delay_min, delay),
                        NextValue(delay_min_found, 1)
                    )
                ).Else(
                    NextState("INC_DELAY_BITSLIP")
                ),
            ).Else(
                If(~serdes.rx_comma,
                    NextValue(delay_max, delay),
                    NextValue(delay_max_found, 1),
                    NextState("CHECK_SAMPLING_WINDOW")
                ).Else(
                    NextState("INC_DELAY_BITSLIP")
                )
            ),
            serdes.tx_idle.eq(1)
        )
        self.comb += serdes.rx_bitslip_value.eq(bitslip)
        fsm.act("INC_DELAY_BITSLIP",
            NextState("WAIT_STABLE"),
            If(delay == (taps - 1),
                If(bitslip == (40 - 1),
                    NextState("ERROR")
                ).Else(
                    NextValue(delay_min_found, 0),
                    NextValue(bitslip, bitslip + 1)
                ),
                NextValue(delay, 0),
                serdes.rx_delay_rst.eq(1)
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_inc.eq(1)
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("CHECK_SAMPLING_WINDOW",
            If((delay_min == 0) |
               (delay_max == (taps - 1)) |
               ((delay_max - delay_min) < taps//16),
               NextValue(delay_min_found, 0),
               NextValue(delay_max_found, 0),
               NextState("WAIT_STABLE")
            ).Else(
                NextState("CONFIGURE_SAMPLING_WINDOW")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("CONFIGURE_SAMPLING_WINDOW",
            If(delay == (delay_min + (delay_max - delay_min)[1:]),
                NextState("SEND_PATTERN")
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_inc.eq(1),
                NextState("WAIT_SAMPLING_WINDOW")
            )
        )
        fsm.act("WAIT_SAMPLING_WINDOW",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CONFIGURE_SAMPLING_WINDOW")
            )
        )
        fsm.act("SEND_PATTERN",
            timer.wait.eq(1),
            If(timer.done,
                If(~serdes.rx_comma,
                    NextState("READY")
                )
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("READY",
            self.ready.eq(1)
        )
        if hasattr(serdes, "rx_delay_en_vtc"):
            self.comb += serdes.rx_delay_en_vtc.eq(self.ready)
        fsm.act("ERROR",
            self.error.eq(1)
        )


class _SerdesControl(Module, AutoCSR):
    def __init__(self, serdes, init, mode="master"):
        if mode == "master":
            self.reset = CSR()
        self.ready = CSRStatus()
        self.error = CSRStatus()

        self.delay = CSRStatus(9)
        self.delay_min_found = CSRStatus()
        self.delay_min = CSRStatus(9)
        self.delay_max_found = CSRStatus()
        self.delay_max = CSRStatus(9)
        self.bitslip = CSRStatus(6)

        self.scrambling_enable = CSRStorage()

        self.prbs_error = Signal()
        self.prbs_start = CSR()
        self.prbs_cycles = CSRStorage(32)
        self.prbs_errors = CSRStatus(32)

        # # #

        if mode == "master":
            # In Master mode, reset is coming from CSR,
            # it resets the Master that will also reset
            # the Slave by putting the link in idle.
            self.sync += init.reset.eq(self.reset.re)
        else:
            # In Slave mode, reset is coming from link,
            # Master reset the Slave by putting the link
            # in idle.
            self.sync += [
                init.reset.eq(serdes.rx_idle),
                serdes.reset.eq(serdes.rx_idle)
            ]
        self.comb += [
            self.ready.status.eq(init.ready),
            self.error.status.eq(init.error),
            self.delay.status.eq(init.delay),
            self.delay_min_found.status.eq(init.delay_min_found),
            self.delay_min.status.eq(init.delay_min),
            self.delay_max_found.status.eq(init.delay_max_found),
            self.delay_max.status.eq(init.delay_max),
            self.bitslip.status.eq(init.bitslip)
        ]

        # prbs
        prbs_cycles = Signal(32)
        prbs_errors = self.prbs_errors.status
        prbs_fsm = FSM(reset_state="IDLE")
        self.submodules += prbs_fsm
        prbs_fsm.act("IDLE",
            NextValue(prbs_cycles, 0),
            If(self.prbs_start.re,
                NextValue(prbs_errors, 0),
                NextState("CHECK")
            )
        )
        prbs_fsm.act("CHECK",
            NextValue(prbs_cycles, prbs_cycles + 1),
            If(self.prbs_error,
                NextValue(prbs_errors, prbs_errors + 1),
            ),
            If(prbs_cycles == self.prbs_cycles.storage,
                NextState("IDLE")
            )
        )


class SERWBPHY(Module, AutoCSR):
    def __init__(self, device, pads, mode="master", init_timeout=2**14):
        self.sink = sink = stream.Endpoint([("data", 32)])
        self.source = source = stream.Endpoint([("data", 32)])
        assert mode in ["master", "slave"]
        if device[:4] == "xcku":
            taps = 512
            self.submodules.serdes = KUSSerdes(pads, mode)
        elif device[:4] == "xc7a":
            taps = 32
            self.submodules.serdes = S7Serdes(pads, mode)
        else:
            raise NotImplementedError
        if mode == "master":
            self.submodules.init = _SerdesMasterInit(self.serdes, taps, init_timeout)
        else:
            self.submodules.init = _SerdesSlaveInit(self.serdes, taps, init_timeout)
        self.submodules.control = _SerdesControl(self.serdes, self.init, mode)

        # scrambling
        scrambler =  Scrambler()
        descrambler = Descrambler()
        self.submodules += scrambler, descrambler
        self.comb += [
            scrambler.enable.eq(self.control.scrambling_enable.storage),
            descrambler.enable.eq(self.control.scrambling_enable.storage)
        ]

        # tx dataflow
        self.comb += \
            If(self.init.ready,
                sink.connect(scrambler.sink),
                scrambler.source.ack.eq(self.serdes.tx_ce),
                If(scrambler.source.stb,
                    self.serdes.tx_d.eq(scrambler.source.d),
                    self.serdes.tx_k.eq(scrambler.source.k)
                )
            )

        # rx dataflow
        self.comb += [
            If(self.init.ready,
                descrambler.sink.stb.eq(self.serdes.rx_ce),
                descrambler.sink.d.eq(self.serdes.rx_d),
                descrambler.sink.k.eq(self.serdes.rx_k),
                descrambler.source.connect(source)
            ),
            # For PRBS test we are using the scrambler/descrambler as PRBS,
            # sending 0 to the scrambler and checking that descrambler
            # output is always 0.
            self.control.prbs_error.eq(
                descrambler.source.stb &
                descrambler.source.ack &
                (descrambler.source.data != 0))
        ]
