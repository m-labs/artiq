"""Common RTIO Interface"""

from migen import *
from migen.genlib.record import *

from misoc.interconnect.csr import *


commands = {
    "nop": 0,
    "reset": 1,
    "reset_phy": 2,

    "write": 3,
    "read": 4,

    "o_underflow_reset": 5,
    "o_sequence_error_reset": 6,
    "o_collision_reset": 7,
    "o_busy_reset": 8,
    "i_overflow_reset": 9
}


layout = [
    ("arb_req", 1, DIR_M_TO_S),
    ("arb_gnt", 1, DIR_S_TO_M),

    ("cmd", 4, DIR_M_TO_S),
    # 8 MSBs of chan_sel are used to select core
    ("chan_sel", 24, DIR_M_TO_S),

    ("o_data", 512, DIR_M_TO_S),
    ("o_address", 16, DIR_M_TO_S),
    ("o_timestamp", 64, DIR_M_TO_S),
    # o_status bits:
    # <0:wait> <1:underflow> <2:sequence_error> <3:collision> <4:busy>
    ("o_status", 5, DIR_S_TO_M),

    ("i_data", 32, DIR_S_TO_M),
    ("i_timestamp", 64, DIR_S_TO_M),
    # i_status bits:
    # <0:wait> <1:overflow>
    ("i_status", 2, DIR_S_TO_M),

    ("counter", 64, DIR_S_TO_M)
]


class Interface(Record):
    def __init__(self):
        Record.__init__(self, layout)


class KernelInitiator(Module, AutoCSR):
    def __init__(self, cri=None):
        self.arb_req = CSRStorage()
        self.arb_gnt = CSRStatus()

        self.reset = CSR()
        self.reset_phy = CSR()
        self.chan_sel = CSRStorage(24)

        self.o_data = CSRStorage(512, write_from_dev=True)
        self.o_address = CSRStorage(16)
        self.o_timestamp = CSRStorage(64)
        self.o_we = CSR()
        self.o_status = CSRStatus(5)
        self.o_underflow_reset = CSR()
        self.o_sequence_error_reset = CSR()
        self.o_collision_reset = CSR()
        self.o_busy_reset = CSR()

        self.i_data = CSRStatus(32)
        self.i_timestamp = CSRStatus(64)
        self.i_re = CSR()
        self.i_status = CSRStatus(2)
        self.i_overflow_reset = CSR()

        self.counter = CSRStatus(64)
        self.counter_update = CSR()

        if cri is None:
            cri = Interface()
        self.cri = cri

        # # #

        self.comb += [
            self.cri.arb_req.eq(self.arb_req.storage),
            self.arb_gnt.status.eq(self.cri.arb_gnt),

            self.cri.cmd.eq(commands["nop"]),
            If(self.reset.re, self.cri.cmd.eq(commands["reset"])),
            If(self.reset_phy.re, self.cri.cmd.eq(commands["reset_phy"])),
            If(self.o_we.re, self.cri.cmd.eq(commands["write"])),
            If(self.i_re.re, self.cri.cmd.eq(commands["read"])),
            If(self.o_underflow_reset.re, self.cri.cmd.eq(commands["o_underflow_reset"])),
            If(self.o_sequence_error_reset.re, self.cri.cmd.eq(commands["o_sequence_error_reset"])),
            If(self.o_collision_reset.re, self.cri.cmd.eq(commands["o_collision_reset"])),
            If(self.o_busy_reset.re, self.cri.cmd.eq(commands["o_busy_reset"])),
            If(self.i_overflow_reset.re, self.cri.cmd.eq(commands["i_overflow_reset"])),

            self.cri.chan_sel.eq(self.chan_sel.storage),

            self.cri.o_data.eq(self.o_data.storage),
            self.cri.o_address.eq(self.o_address.storage),
            self.cri.o_timestamp.eq(self.o_timestamp.storage),
            self.o_status.status.eq(self.cri.o_status),

            self.i_data.status.eq(self.cri.i_data),
            self.i_timestamp.status.eq(self.cri.i_timestamp),
            self.i_status.status.eq(self.cri.i_status),

            self.o_data.dat_w.eq(0),
            self.o_data.we.eq(self.o_timestamp.re),
        ]
        self.sync += If(self.counter_update.re, self.counter.status.eq(self.cri.counter))


class CRIDecoder(Module):
    def __init__(self, slaves=2, master=None):
        if isinstance(slaves, int):
            slaves = [Interface() for _ in range(slaves)]
        if master is None:
            master = Interface()
        self.slaves = slaves
        self.master = master

        # # #

        selected = Signal(8)
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


class CRIArbiter(Module):
    def __init__(self, masters=2, slave=None):
        if isinstance(masters, int):
            masters = [Interface() for _ in range(masters)]
        if slave is None:
            slave = Interface()
        self.masters = masters
        self.slave = slave

        # # #

        if len(masters) == 1:
            self.comb += masters[0].connect(slave)
        else:
            selected = Signal(max=len(masters))

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
                        if name == "arb_gnt":
                            self.comb += dest.eq(source & (selected == i))
                        else:
                            self.comb += dest.eq(source)

            # select master
            self.sync += \
                If(~slave.arb_req,
                    [If(m.arb_req, selected.eq(i)) for i, m in enumerate(masters)]
                )


class CRIInterconnectShared(Module):
    def __init__(self, masters=2, slaves=2):
        shared = Interface()
        self.submodules.arbiter = CRIArbiter(masters, shared)
        self.submodules.decoder = CRIDecoder(slaves, shared)
