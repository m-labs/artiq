import os

from misoc.integration.soc_core import mem_decoder
from misoc.cores import timer
from misoc.interconnect import wishbone
from misoc.integration.builder import *

from artiq.gateware import amp
from artiq import __artiq_dir__ as artiq_dir


class AMPSoC:
    """Contains timer, kernel CPU and mailbox for ARTIQ SoCs.

    Users must disable the timer from the platform SoC and provide
    a "mailbox" entry in the memory map.
    """
    def __init__(self):
        if not hasattr(self, "cpu"):
            raise ValueError("Platform SoC must be initialized first")
        if hasattr(self, "timer0"):
            raise ValueError("Timer already exists. "
                             "Initialize platform SoC using with_timer=False")

        self.submodules.timer0 = timer.Timer(width=64)

        self.submodules.kernel_cpu = amp.KernelCPU(self.platform)
        self.add_cpulevel_sdram_if(self.kernel_cpu.wb_sdram)
        self.csr_devices.append("kernel_cpu")

        self.submodules.mailbox = amp.Mailbox(size=3)
        self.add_wb_slave(mem_decoder(self.mem_map["mailbox"]),
                          self.mailbox.i1)
        self.kernel_cpu.add_wb_slave(mem_decoder(self.mem_map["mailbox"]),
                                     self.mailbox.i2)
        self.add_memory_region("mailbox",
                               self.mem_map["mailbox"] | 0x80000000, 4)

        self.submodules.timer_kernel = timer.Timer()
        self.register_kernel_cpu_csrdevice("timer_kernel")

    def register_kernel_cpu_csrdevice(self, name):
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
    builder.add_extra_software_packages()
    builder.add_software_package("liblwip", os.path.join(artiq_dir, "runtime",
                                                         "liblwip"))
    builder.add_software_package("runtime", os.path.join(artiq_dir, "runtime"))
    builder.build()
