"""Common RTIO Interface"""

from migen import *
from migen.genlib.record import *

from misoc.interconnect.csr import *


commands = {
    "nop": 0,

    "write": 1,
    # i_status should have the "wait for status" bit set until
    # an event is available, or timestamp is reached.
    "read": 2
}


layout = [
    ("cmd", 2, DIR_M_TO_S),
    # 8 MSBs of chan_sel are used to select core
    ("chan_sel", 24, DIR_M_TO_S),
    ("timestamp", 64, DIR_M_TO_S),

    ("o_data", 512, DIR_M_TO_S),
    ("o_address", 16, DIR_M_TO_S),
    # o_status bits:
    # <0:wait> <1:underflow> <2:sequence_error>
    ("o_status", 3, DIR_S_TO_M),

    ("i_data", 32, DIR_S_TO_M),
    ("i_timestamp", 64, DIR_S_TO_M),
    # i_status bits:
    # <0:wait for event (command timeout)> <1:overflow> <2:wait for status>
    # <0> and <1> are mutually exclusive. <1> has higher priority.
    ("i_status", 3, DIR_S_TO_M),

    ("counter", 64, DIR_S_TO_M)
]


class Interface(Record):
    def __init__(self):
        Record.__init__(self, layout)


class KernelInitiator(Module, AutoCSR):
    def __init__(self, cri=None):
        self.chan_sel = CSRStorage(24)
        self.timestamp = CSRStorage(64)

        # Writing timestamp clears o_data. This implements automatic
        # zero-extension of output event data by the gateware. When staging an
        # output event, always write timestamp before o_data.
        self.o_data = CSRStorage(512, write_from_dev=True)
        self.o_address = CSRStorage(16)
        self.o_we = CSR()
        self.o_status = CSRStatus(3)

        self.i_data = CSRStatus(32)
        self.i_timestamp = CSRStatus(64)
        self.i_request = CSR()
        self.i_status = CSRStatus(3)
        self.i_overflow_reset = CSR()

        self.counter = CSRStatus(64)
        self.counter_update = CSR()

        if cri is None:
            cri = Interface()
        self.cri = cri

        # # #

        self.comb += [
            self.cri.cmd.eq(commands["nop"]),
            If(self.o_we.re, self.cri.cmd.eq(commands["write"])),
            If(self.i_request.re, self.cri.cmd.eq(commands["read"])),

            self.cri.chan_sel.eq(self.chan_sel.storage),
            self.cri.timestamp.eq(self.timestamp.storage),

            self.cri.o_data.eq(self.o_data.storage),
            self.cri.o_address.eq(self.o_address.storage),
            self.o_status.status.eq(self.cri.o_status),

            self.i_data.status.eq(self.cri.i_data),
            self.i_timestamp.status.eq(self.cri.i_timestamp),
            self.i_status.status.eq(self.cri.i_status),

            self.o_data.dat_w.eq(0),
            self.o_data.we.eq(self.timestamp.re),
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


class CRISwitch(Module, AutoCSR):
    def __init__(self, masters=2, slave=None):
        if isinstance(masters, int):
            masters = [Interface() for _ in range(masters)]
        if slave is None:
            slave = Interface()
        self.masters = masters
        self.slave = slave

        self.selected = CSRStorage(len(masters).bit_length())

        # # #

        if len(masters) == 1:
            self.comb += masters[0].connect(slave)
        else:
            # mux master->slave signals
            for name, size, direction in layout:
                if direction == DIR_M_TO_S:
                    choices = Array(getattr(m, name) for m in masters)
                    self.comb += getattr(slave, name).eq(choices[self.selected.storage])

            # connect slave->master signals
            for name, size, direction in layout:
                if direction == DIR_S_TO_M:
                    source = getattr(slave, name)
                    for i, m in enumerate(masters):
                        dest = getattr(m, name)
                        self.comb += dest.eq(source)

class CRIInterconnectShared(Module):
    def __init__(self, masters=2, slaves=2):
        shared = Interface()
        self.submodules.switch = CRISwitch(masters, shared)
        self.submodules.decoder = CRIDecoder(slaves, shared)

    def get_csrs(self):
        return self.switch.get_csrs()
