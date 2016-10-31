from misoc.interconnect.csr import *


class KernelCSRs(AutoCSR):
    def __init__(self):
        self.reset = CSRStorage(reset=1)
        self.reset_phy = CSRStorage(reset=1)
        self.chan_sel = CSRStorage(16)

        self.o_data = CSRStorage(32)
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
