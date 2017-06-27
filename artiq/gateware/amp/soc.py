import os

from misoc.integration.soc_core import mem_decoder
from misoc.cores import timer
from misoc.interconnect import wishbone
from misoc.integration.builder import *

from artiq.gateware.amp.kernel_cpu import KernelCPU
from artiq.gateware.amp.mailbox import Mailbox
from artiq import __artiq_dir__ as artiq_dir


class AMPSoC:
    """Contains kernel CPU and mailbox for ARTIQ SoCs.

    Users must provide a "mailbox" entry in the memory map.
    """
    def __init__(self):
        if not hasattr(self, "cpu"):
            raise ValueError("Platform SoC must be initialized first")

        self.submodules.kernel_cpu = KernelCPU(self.platform)
        self.add_cpulevel_sdram_if(self.kernel_cpu.wb_sdram)
        self.csr_devices.append("kernel_cpu")

        self.submodules.mailbox = Mailbox(size=3)
        self.add_wb_slave(mem_decoder(self.mem_map["mailbox"]),
                          self.mailbox.i1)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["mailbox"]),
                                     self.mailbox.i2)
        self.add_memory_region("mailbox",
                               self.mem_map["mailbox"] | 0x80000000, 4)

    def register_kernel_cpu_csrdevice(self, name, csrs=None):
        if csrs is None:
            csrs = getattr(self, name).get_csrs()
        bank = wishbone.CSRBank(csrs)
        self.submodules += bank
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map[name]),
                                     bank.bus)
        self.add_csr_region(name,
                            self.mem_map[name] | 0x80000000, 32,
                            csrs)


def build_artiq_soc(soc, argdict):
    builder = Builder(soc, **argdict)
    builder.add_software_package("libm")
    builder.add_software_package("libunwind")
    builder.add_software_package("ksupport", os.path.join(artiq_dir, "firmware", "ksupport"))
    builder.add_software_package("runtime", os.path.join(artiq_dir, "firmware", "runtime"))
    builder.build()
