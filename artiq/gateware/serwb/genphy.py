from migen import *
from migen.genlib.io import *
from migen.genlib.misc import BitSlip, WaitTimer

from misoc.interconnect import stream
from misoc.interconnect.csr import *
from misoc.cores.code_8b10b import Encoder, Decoder

from artiq.gateware.serwb.scrambler import Scrambler, Descrambler


def K(x, y):
    return (y << 5) | x


class _SerdesClocking(Module):
    def __init__(self, pads, mode="master"):
        self.refclk = Signal()

        # # #

        # In Master mode, generate the clock with 180° phase shift so that Slave
        # can use this clock to sample data
        if mode == "master":
            self.specials += DDROutput(0, 1, self.refclk)
            self.specials += DifferentialOutput(self.refclk, pads.clk_p, pads.clk_n)
        # In Slave mode, use the clock provided by Master
        elif mode == "slave":
            self.specials += DifferentialInput(pads.clk_p, pads.clk_n, self.refclk)


class _SerdesTX(Module):
    def __init__(self, pads, mode="master"):
        # Control
        self.idle = idle = Signal()
        self.comma = comma = Signal()

        # Datapath
        self.ce = ce = Signal()
        self.k = k = Signal(4)
        self.d = d = Signal(32)

        # # #

        # 8b10b encoder
        self.submodules.encoder = encoder = CEInserter()(Encoder(4, True))
        self.comb += encoder.ce.eq(ce)

        # 40 --> 1 converter
        converter = stream.Converter(40, 1)
        self.submodules += converter
        self.comb += [
            converter.sink.stb.eq(1),
            converter.source.ack.eq(1),
            # Enable pipeline when converter accepts the 40 bits
            ce.eq(converter.sink.ack),
            # If not idle, connect encoder to converter
            If(~idle,
                converter.sink.data.eq(Cat(*[encoder.output[i] for i in range(4)]))
            ),
            # If comma, send K28.5
            If(comma,
                encoder.k[0].eq(1),
                encoder.d[0].eq(K(28,5)),
            # Else connect TX to encoder
            ).Else(
                encoder.k[0].eq(k[0]),
                encoder.k[1].eq(k[1]),
                encoder.k[2].eq(k[2]),
                encoder.k[3].eq(k[3]),
                encoder.d[0].eq(d[0:8]),
                encoder.d[1].eq(d[8:16]),
                encoder.d[2].eq(d[16:24]),
                encoder.d[3].eq(d[24:32])
            )
        ]

        # Data output (on rising edge of sys_clk)
        data = Signal()
        self.sync += data.eq(converter.source.data)
        self.specials += DifferentialOutput(data, pads.tx_p, pads.tx_n)


class _SerdesRX(Module):
    def __init__(self, pads, mode="master"):
        # Control
        self.bitslip_value = bitslip_value = Signal(6)

        # Status
        self.idle = idle = Signal()
        self.comma = comma = Signal()

        # Datapath
        self.ce = ce = Signal()
        self.k = k = Signal(4)
        self.d = d = Signal(32)

        # # #

        # Input data (on rising edge of sys_clk)
        data = Signal()
        data_d = Signal()
        self.specials += DifferentialInput(pads.rx_p, pads.rx_n, data)
        self.sync += data_d.eq(data)

        # 1 --> 40 converter and bitslip
        converter = stream.Converter(1, 40)
        self.submodules += converter
        bitslip = CEInserter()(BitSlip(40))
        self.submodules += bitslip
        self.comb += [
            converter.sink.stb.eq(1),
            converter.source.ack.eq(1),
            # Enable pipeline when converter outputs the 40 bits
            ce.eq(converter.source.stb),
            # Connect input data to converter
            converter.sink.data.eq(data),
            # Connect converter to bitslip
            bitslip.ce.eq(ce),
            bitslip.value.eq(bitslip_value),
            bitslip.i.eq(converter.source.data)
        ]

        # 8b10b decoder
        self.submodules.decoders = decoders = [CEInserter()(Decoder(True)) for _ in range(4)]
        self.comb += [decoders[i].ce.eq(ce) for i in range(4)]
        self.comb += [
            # Connect bitslip to decoder
            decoders[0].input.eq(bitslip.o[0:10]),
            decoders[1].input.eq(bitslip.o[10:20]),
            decoders[2].input.eq(bitslip.o[20:30]),
            decoders[3].input.eq(bitslip.o[30:40]),
            # Connect decoder to output
            self.k.eq(Cat(*[decoders[i].k for i in range(4)])),
            self.d.eq(Cat(*[decoders[i].d for i in range(4)])),
        ]

        # Status
        idle_timer = WaitTimer(256)
        self.submodules += idle_timer
        self.comb += [
            idle_timer.wait.eq(1),
            self.idle.eq(idle_timer.done &
                 ((bitslip.o == 0) | (bitslip.o == (2**40-1)))),
            self.comma.eq(
                (decoders[0].k == 1) & (decoders[0].d == K(28,5)) &
                (decoders[1].k == 0) & (decoders[1].d == 0) &
                (decoders[2].k == 0) & (decoders[2].d == 0) &
                (decoders[3].k == 0) & (decoders[3].d == 0))
        ]


@ResetInserter()
class _Serdes(Module):
    def __init__(self, pads, mode="master"):
        self.submodules.clocking = _SerdesClocking(pads, mode)
        self.submodules.tx = _SerdesTX(pads, mode)
        self.submodules.rx = _SerdesRX(pads, mode)


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

        # scrambling
        self.submodules.scrambler = scrambler = Scrambler()
        self.submodules.descrambler = descrambler = Descrambler()

        # tx dataflow
        self.comb += \
            If(self.init.ready,
                sink.connect(scrambler.sink),
                scrambler.source.ack.eq(self.serdes.tx.ce),
                If(scrambler.source.stb,
                    self.serdes.tx.d.eq(scrambler.source.d),
                    self.serdes.tx.k.eq(scrambler.source.k)
                )
            )

        # rx dataflow
        self.comb += [
            If(self.init.ready,
                descrambler.sink.stb.eq(self.serdes.rx.ce),
                descrambler.sink.d.eq(self.serdes.rx.d),
                descrambler.sink.k.eq(self.serdes.rx.k),
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
