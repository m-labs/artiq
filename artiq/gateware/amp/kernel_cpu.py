from migen.fhdl.std import *
from migen.bank.description import *
from migen.bus import wishbone

from misoclib.cpu import mor1kx
from misoclib.mem.sdram.frontend.wishbone2lasmi import WB2LASMI
from misoclib.soc import mem_decoder


class KernelCPU(Module):
    def __init__(self, platform, lasmim,
                 exec_address=0x41000000,
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
        self.submodules.cpu = RenameClockDomains(
            mor1kx.MOR1KX(platform, exec_address),
            "sys_kernel")

        # DRAM access
        # XXX Vivado 2014.X workaround
        from mibuild.xilinx.vivado import XilinxVivadoToolchain
        if isinstance(platform.toolchain, XilinxVivadoToolchain):
            from migen.fhdl.simplify import FullMemoryWE
            self.submodules.wishbone2lasmi = FullMemoryWE(
                WB2LASMI(l2_size//4, lasmim))
        else:
            self.submodules.wishbone2lasmi = WB2LASMI(l2_size//4, lasmim)
        self.add_wb_slave(mem_decoder(main_mem_origin),
                          self.wishbone2lasmi.wishbone)

    def get_csrs(self):
        return [self._reset]

    def do_finalize(self):
        self.submodules.wishbonecon = wishbone.InterconnectShared(
            [self.cpu.ibus, self.cpu.dbus], self._wb_slaves, register=True)

    def add_wb_slave(self, address_decoder, interface):
        if self.finalized:
            raise FinalizeError
        self._wb_slaves.append((address_decoder, interface))
