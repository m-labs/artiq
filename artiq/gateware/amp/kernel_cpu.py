from migen import *
from misoc.interconnect.csr import *
from misoc.interconnect import wishbone
from misoc.cores import mor1kx
from misoc.integration.soc_core import mem_decoder


class KernelCPU(Module):
    def __init__(self, platform,
                 exec_address=0x40800000,
                 main_mem_origin=0x40000000,
                 l2_size=8192):
        self._reset = CSRStorage(reset=1)

        # # #

        self._wb_slaves = []

        # CPU core
        self.clock_domains.cd_sys_kernel = ClockDomain()
        self.comb += [
            self.cd_sys_kernel.clk.eq(ClockSignal()),
            self.cd_sys_kernel.rst.eq(self._reset.storage)
        ]
        self.submodules.cpu = ClockDomainsRenamer("sys_kernel")(
            mor1kx.MOR1KX(
                platform,
                OPTION_RESET_PC=exec_address,
                FEATURE_PERFCOUNTERS="ENABLED",
                OPTION_PERFCOUNTERS_NUM=7))

        # DRAM access
        self.wb_sdram = wishbone.Interface()
        self.add_wb_slave(mem_decoder(main_mem_origin), self.wb_sdram)

    def get_csrs(self):
        return [self._reset]

    def do_finalize(self):
        self.submodules.wishbonecon = wishbone.InterconnectShared(
            [self.cpu.ibus, self.cpu.dbus], self._wb_slaves, register=True)

    def add_wb_slave(self, address_decoder, interface):
        if self.finalized:
            raise FinalizeError
        self._wb_slaves.append((address_decoder, interface))
