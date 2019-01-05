"""Common RTIO Interface"""

from migen import *
from migen.genlib.record import *
from migen.genlib.cdc import MultiReg

from misoc.interconnect.csr import *


# CRI write happens in 3 cycles:
# 1. set timestamp and channel
# 2. set other payload elements and issue write command
# 3. check status

commands = {
    "nop": 0,
    "write": 1,
    # i_status should have the "wait for status" bit set until
    # an event is available, or timestamp is reached.
    "read": 2,
    # targets must assert o_buffer_space_valid in response
    # to this command
    "get_buffer_space": 3
}


layout = [
    ("cmd", 2, DIR_M_TO_S),
    # 8  MSBs of chan_sel = routing destination
    # 16 LSBs of chan_sel = channel within the destination
    ("chan_sel", 24, DIR_M_TO_S),

    ("o_timestamp", 64, DIR_M_TO_S),
    ("o_data", 512, DIR_M_TO_S),
    ("o_address", 8, DIR_M_TO_S),
    # o_status bits:
    # <0:wait> <1:underflow> <2:destination unreachable>
    ("o_status", 3, DIR_S_TO_M),

    # pessimistic estimate of the number of outputs events that can be
    # written without waiting.
    # this feature may be omitted on systems without DRTIO.
    ("o_buffer_space_valid", 1, DIR_S_TO_M),
    ("o_buffer_space", 16, DIR_S_TO_M),

    ("i_timeout", 64, DIR_M_TO_S),
    ("i_data", 32, DIR_S_TO_M),
    ("i_timestamp", 64, DIR_S_TO_M),
    # i_status bits:
    # <0:wait for event (command timeout)> <1:overflow> <2:wait for status>
    # <3:destination unreachable>
    # <0> and <1> are mutually exclusive. <1> has higher priority.
    ("i_status", 4, DIR_S_TO_M),
]


class Interface(Record):
    def __init__(self, **kwargs):
        Record.__init__(self, layout, **kwargs)


class KernelInitiator(Module, AutoCSR):
    def __init__(self, tsc, cri=None):
        self.target = CSRStorage(32)
        # not using CSRStorage atomic_write feature here to make storage reset_less
        self.now_hi = CSR(32)
        self.now_lo = CSR(32)

        # Writing target clears o_data. This implements automatic
        # zero-extension of output event data by the gateware. When staging an
        # output event, always write target before o_data.
        self.o_data = CSRStorage(512, write_from_dev=True)
        self.o_status = CSRStatus(3)

        self.i_timeout = CSRStorage(64)
        self.i_data = CSRStatus(32)
        self.i_timestamp = CSRStatus(64)
        self.i_status = CSRStatus(4)
        self.i_overflow_reset = CSR()

        self.counter = CSRStatus(64)
        self.counter_update = CSR()

        if cri is None:
            cri = Interface()
        self.cri = cri

        # # #

        now_hi_backing = Signal(32)
        now = Signal(64, reset_less=True)
        self.sync += [
            If(self.now_hi.re, now_hi_backing.eq(self.now_hi.r)),
            If(self.now_lo.re, now.eq(Cat(self.now_lo.r, now_hi_backing)))
        ]
        self.comb += [
            self.now_hi.w.eq(now[32:]),
            self.now_lo.w.eq(now[:32])
        ]

        self.comb += [
            self.cri.cmd.eq(commands["nop"]),
            If(self.o_data.re, self.cri.cmd.eq(commands["write"])),
            If(self.i_timeout.re, self.cri.cmd.eq(commands["read"])),

            self.cri.chan_sel.eq(self.target.storage[8:]),

            self.cri.o_timestamp.eq(now),
            self.cri.o_data.eq(self.o_data.storage),
            self.cri.o_address.eq(self.target.storage[:8]),
            self.o_status.status.eq(self.cri.o_status),

            self.cri.i_timeout.eq(self.i_timeout.storage),
            self.i_data.status.eq(self.cri.i_data),
            self.i_timestamp.status.eq(self.cri.i_timestamp),
            self.i_status.status.eq(self.cri.i_status),

            self.o_data.dat_w.eq(0),
            self.o_data.we.eq(self.target.re),
        ]
        self.sync += If(self.counter_update.re, self.counter.status.eq(tsc.full_ts_cri))


class CRIDecoder(Module):
    def __init__(self, slaves=2, master=None, mode="async", enable_routing=False):
        if isinstance(slaves, int):
            slaves = [Interface() for _ in range(slaves)]
        if master is None:
            master = Interface()
        self.slaves = slaves
        self.master = master

        # # #

        # routing
        if enable_routing:
            destination_unreachable = Interface()
            self.comb += [
                destination_unreachable.o_status.eq(4),
                destination_unreachable.i_status.eq(8)
            ]
            slaves = slaves[:]
            slaves.append(destination_unreachable)
            target_len = 2**(len(slaves) - 1).bit_length()
            slaves += [destination_unreachable]*(target_len - len(slaves))

        slave_bits = bits_for(len(slaves)-1)
        selected = Signal(slave_bits)

        if enable_routing:
            self.specials.routing_table = Memory(slave_bits, 256)

            if mode == "async":
                rtp_decoder = self.routing_table.get_port()
            elif mode == "sync":
                rtp_decoder = self.routing_table.get_port(clock_domain="rtio")
            else:
                raise ValueError
            self.specials += rtp_decoder
            self.comb += [
                rtp_decoder.adr.eq(self.master.chan_sel[16:]),
                selected.eq(rtp_decoder.dat_r)
            ]
        else:
            self.sync += selected.eq(self.master.chan_sel[16:])

        # master -> slave
        for n, slave in enumerate(slaves):
            for name, size, direction in layout:
                if direction == DIR_M_TO_S and name != "cmd":
                    self.comb += getattr(slave, name).eq(getattr(master, name))
            self.comb += If(selected == n, slave.cmd.eq(master.cmd))

        # slave -> master
        cases = dict()
        for n, slave in enumerate(slaves):
            cases[n] = []
            for name, size, direction in layout:
                if direction == DIR_S_TO_M:
                    cases[n].append(getattr(master, name).eq(getattr(slave, name)))
        self.comb += Case(selected, cases)


class CRISwitch(Module, AutoCSR):
    def __init__(self, masters=2, slave=None, mode="async"):
        if isinstance(masters, int):
            masters = [Interface() for _ in range(masters)]
        if slave is None:
            slave = Interface()
        self.masters = masters
        self.slave = slave

        self.selected = CSRStorage(len(masters).bit_length())

        # # #

        if mode == "async":
            selected = self.selected.storage
        elif mode == "sync":
            self.selected.storage.attr.add("no_retiming")
            selected = Signal.like(self.selected.storage)
            self.specials += MultiReg(self.selected.storage, selected, "rtio")
        else:
            raise ValueError

        if len(masters) == 1:
            self.comb += masters[0].connect(slave)
        else:
            # mux master->slave signals
            for name, size, direction in layout:
                if direction == DIR_M_TO_S:
                    choices = Array(getattr(m, name) for m in masters)
                    self.comb += getattr(slave, name).eq(choices[selected])

            # connect slave->master signals
            for name, size, direction in layout:
                if direction == DIR_S_TO_M:
                    source = getattr(slave, name)
                    for i, m in enumerate(masters):
                        dest = getattr(m, name)
                        self.comb += dest.eq(source)


class CRIInterconnectShared(Module):
    def __init__(self, masters=2, slaves=2, mode="async", enable_routing=False):
        shared = Interface()
        self.submodules.switch = CRISwitch(masters, shared, mode)
        self.submodules.decoder = CRIDecoder(slaves, shared, mode, enable_routing)

    def get_csrs(self):
        return self.switch.get_csrs()


class RoutingTableAccess(Module, AutoCSR):
    def __init__(self, interconnect):
        if isinstance(interconnect, CRIInterconnectShared):
            interconnect = interconnect.decoder

        rtp_csr = interconnect.routing_table.get_port(write_capable=True)
        self.specials += rtp_csr

        self.destination = CSRStorage(8)
        self.hop = CSR(len(rtp_csr.dat_w))

        self.comb += [
            rtp_csr.adr.eq(self.destination.storage),
            rtp_csr.dat_w.eq(self.hop.r),
            rtp_csr.we.eq(self.hop.re),
            self.hop.w.eq(rtp_csr.dat_r)
        ]
