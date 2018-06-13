from migen import *
from migen.genlib.io import *
from migen.genlib.misc import BitSlip, WaitTimer

from misoc.interconnect import stream
from misoc.interconnect.csr import *

from artiq.gateware.serwb.datapath import TXDatapath, RXDatapath


class _SerdesClocking(Module):
    def __init__(self, pads, mode="master"):
        self.refclk = Signal()

        # # #

        # In Master mode, generate the clock with 180° phase shift so that Slave
        # can use this clock to sample data
        if mode == "master":
            self.specials += DDROutput(0, 1, self.refclk)
            if hasattr(pads, "clk_p"):
                self.specials += DifferentialOutput(self.refclk, pads.clk_p, pads.clk_n)
            else:
                self.comb += pads.clk.eq(self.refclk)
        # In Slave mode, use the clock provided by Master
        elif mode == "slave":
            if hasattr(pads, "clk_p"):
                self.specials += DifferentialInput(pads.clk_p, pads.clk_n, self.refclk)
            else:
                self.comb += self.refclk.eq(pads.clk)
        else:
            raise ValueError


class _SerdesTX(Module):
    def __init__(self, pads):
        # Control
        self.idle = idle = Signal()
        self.comma = comma = Signal()

        # Datapath
        self.sink = sink = stream.Endpoint([("data", 32)])

        # # #

        # Datapath
        self.submodules.datapath = datapath = TXDatapath(1)
        self.comb += [
            sink.connect(datapath.sink),
            datapath.source.ack.eq(1),
            datapath.idle.eq(idle),
            datapath.comma.eq(comma)
        ]

        # Output data (on rising edge of sys_clk)
        data = Signal()
        self.sync += data.eq(datapath.source.data)
        if hasattr(pads, "tx_p"):
            self.specials += DifferentialOutput(data, pads.tx_p, pads.tx_n)
        else:
            self.comb += pads.tx.eq(data)


class _SerdesRX(Module):
    def __init__(self, pads):
        # Control
        self.bitslip_value = bitslip_value = Signal(6)

        # Status
        self.idle = idle = Signal()
        self.comma = comma = Signal()

        # Datapath
        self.source = source = stream.Endpoint([("data", 32)])

        # # #

        # Input data (on rising edge of sys_clk)
        data = Signal()
        data_d = Signal()
        if hasattr(pads, "rx_p"):
            self.specials += DifferentialInput(pads.rx_p, pads.rx_n, data)
        else:
            self.comb += data.eq(pads.rx)
        self.sync += data_d.eq(data)

        # Datapath
        self.submodules.datapath = datapath = RXDatapath(1)
        self.comb += [
            datapath.sink.stb.eq(1),
            datapath.sink.data.eq(data_d),
            datapath.bitslip_value.eq(bitslip_value),
            datapath.source.connect(source),
            idle.eq(datapath.idle),
            comma.eq(datapath.comma)
        ]


@ResetInserter()
class _Serdes(Module):
    def __init__(self, pads, mode="master"):
        self.submodules.clocking = _SerdesClocking(pads, mode)
        self.submodules.tx = _SerdesTX(pads)
        self.submodules.rx = _SerdesRX(pads)


# SERWB Master <--> Slave physical synchronization process:
# 1) Master sends idle patterns (zeroes) to Slave to reset it.
# 2) Master sends K28.5 commas to allow Slave to calibrate, Slave sends idle patterns.
# 3) Slave sends K28.5 commas to allow Master to calibrate, Master sends K28.5 commas.
# 4) Master stops sending K28.5 commas.
# 5) Slave stops sending K28.5 commas.
# 6) Physical link is ready.


@ResetInserter()
class _SerdesMasterInit(Module):
    def __init__(self, serdes, timeout):
        self.ready = Signal()
        self.error = Signal()

        # # #

        self.bitslip = bitslip = Signal(max=40)

        self.submodules.timer = timer = WaitTimer(timeout)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(bitslip, 0),
            NextState("RESET_SLAVE"),
            serdes.tx.idle.eq(1)
        )
        fsm.act("RESET_SLAVE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("SEND_PATTERN")
            ),
            serdes.tx.idle.eq(1)
        )
        fsm.act("SEND_PATTERN",
            If(~serdes.rx.idle,
                timer.wait.eq(1),
                If(timer.done,
                    NextState("CHECK_PATTERN")
                )
            ),
            serdes.tx.comma.eq(1)
        )
        fsm.act("WAIT_STABLE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CHECK_PATTERN")
            ),
            serdes.tx.comma.eq(1)
        )
        fsm.act("CHECK_PATTERN",
            If(serdes.rx.comma,
                timer.wait.eq(1),
                If(timer.done,
                    NextState("READY")
                )
            ).Else(
                NextState("INC_BITSLIP")
            ),
            serdes.tx.comma.eq(1)
        )
        self.comb += serdes.rx.bitslip_value.eq(bitslip)
        fsm.act("INC_BITSLIP",
            NextState("WAIT_STABLE"),
            If(bitslip == (40 - 1),
                NextState("ERROR")
            ).Else(
                NextValue(bitslip, bitslip + 1)
            ),
            serdes.tx.comma.eq(1)
        )
        fsm.act("READY",
            self.ready.eq(1)
        )
        fsm.act("ERROR",
            self.error.eq(1)
        )


@ResetInserter()
class _SerdesSlaveInit(Module, AutoCSR):
    def __init__(self, serdes, timeout):
        self.ready = Signal()
        self.error = Signal()

        # # #

        self.bitslip = bitslip = Signal(max=40)

        self.submodules.timer = timer = WaitTimer(timeout)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        # reset
        fsm.act("IDLE",
            NextValue(bitslip, 0),
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("WAIT_STABLE"),
            ),
            serdes.tx.idle.eq(1)
        )
        fsm.act("WAIT_STABLE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CHECK_PATTERN")
            ),
            serdes.tx.idle.eq(1)
        )
        fsm.act("CHECK_PATTERN",
            If(serdes.rx.comma,
                timer.wait.eq(1),
                If(timer.done,
                    NextState("SEND_PATTERN")
                )
            ).Else(
                NextState("INC_BITSLIP")
            ),
            serdes.tx.idle.eq(1)
        )
        self.comb += serdes.rx.bitslip_value.eq(bitslip)
        fsm.act("INC_BITSLIP",
            NextState("WAIT_STABLE"),
            If(bitslip == (40 - 1),
                NextState("ERROR")
            ).Else(
                NextValue(bitslip, bitslip + 1)
            ),
            serdes.tx.idle.eq(1)
        )
        fsm.act("SEND_PATTERN",
            timer.wait.eq(1),
            If(timer.done,
                If(~serdes.rx.comma,
                    NextState("READY")
                )
            ),
            serdes.tx.comma.eq(1)
        )
        fsm.act("READY",
            self.ready.eq(1)
        )
        fsm.act("ERROR",
            self.error.eq(1)
        )


class _SerdesControl(Module, AutoCSR):
    def __init__(self, serdes, init, mode="master"):
        if mode == "master":
            self.reset = CSR()
        self.ready = CSRStatus()
        self.error = CSRStatus()

        self.bitslip = CSRStatus(6)

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
                init.reset.eq(serdes.rx.idle),
                serdes.reset.eq(serdes.rx.idle)
            ]
        self.comb += [
            self.ready.status.eq(init.ready),
            self.error.status.eq(init.error),
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
    def __init__(self, device, pads, mode="master", init_timeout=2**16):
        self.sink = sink = stream.Endpoint([("data", 32)])
        self.source = source = stream.Endpoint([("data", 32)])
        assert mode in ["master", "slave"]
        self.submodules.serdes = _Serdes(pads, mode)
        if mode == "master":
            self.submodules.init = _SerdesMasterInit(self.serdes, init_timeout)
        else:
            self.submodules.init = _SerdesSlaveInit(self.serdes, init_timeout)
        self.submodules.control = _SerdesControl(self.serdes, self.init, mode)

        # tx/rx dataflow
        self.comb += [
            If(self.init.ready,
                If(sink.stb,
                    sink.connect(self.serdes.tx.sink),
                ),
                self.serdes.rx.source.connect(source)
            ).Else(
                self.serdes.rx.source.ack.eq(1)
            ),
            self.serdes.tx.sink.stb.eq(1) # always transmitting
        ]

        # For PRBS test we are using the scrambler/descrambler as PRBS,
        # sending 0 to the scrambler and checking that descrambler
        # output is always 0.
        self.comb += self.control.prbs_error.eq(
                source.stb &
                source.ack &
                (source.data != 0))
