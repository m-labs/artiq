from migen import *
from misoc.interconnect.csr import *
from misoc.interconnect import wishbone
from misoc.cores import mor1kx
from misoc.integration.wb_slaves import WishboneSlaveManager


class KernelCPU(Module):
    def __init__(self, platform,
                 exec_address=0x40800000,
                 main_mem_origin=0x40000000,
                 l2_size=8192):
        self._reset = CSRStorage(reset=1)

        # # #

        self._wb_slaves = WishboneSlaveManager(0x80000000)

        # CPU core
        self.clock_domains.cd_sys_kernel = ClockDomain()
        self.comb += [
            self.cd_sys_kernel.clk.eq(ClockSignal()),
            self.cd_sys_kernel.rst.eq(self._reset.storage)
        ]
        self.submodules.cpu = ClockDomainsRenamer("sys_kernel")(
            mor1kx.MOR1KX(
                platform,
                OPTION_RESET_PC=exec_address))

        # DRAM access
        self.wb_sdram = wishbone.Interface()
        self.add_wb_slave(main_mem_origin, 0x10000000, self.wb_sdram)

    def get_csrs(self):
        return [self._reset]

    def do_finalize(self):
        self.submodules.wishbonecon = wishbone.InterconnectShared(
            [self.cpu.ibus, self.cpu.dbus],
            self._wb_slaves.get_interconnect_slaves(), register=True)

    def add_wb_slave(self, origin, length, interface):
        if self.finalized:
            raise FinalizeError
        self._wb_slaves.add(origin, length, interface)
