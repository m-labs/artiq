from migen import *
from misoc.cores import timer
from misoc.interconnect import wishbone

from artiq.gateware.amp.kernel_cpu import KernelCPU
from artiq.gateware.amp.mailbox import Mailbox


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

        mailbox_size = 3
        self.csr_separation = self.kernel_cpu.cpu_dw//8

        self.submodules.mailbox = Mailbox(mailbox_size, adr_width=32-log2_int(self.csr_separation))
        self.add_wb_slave(self.mem_map["mailbox"], self.csr_separation*mailbox_size,
                          self.mailbox.i1)
        self.kernel_cpu.add_wb_slave(self.mem_map["mailbox"], self.csr_separation*mailbox_size,
                                     self.mailbox.i2)
        self.add_memory_region("mailbox",
                               self.mem_map["mailbox"] | 0x80000000,
                               self.csr_separation*mailbox_size)

    def register_kernel_cpu_csrdevice(self, name, csrs=None):
        if csrs is None:
            csrs = getattr(self, name).get_csrs()
        csr_bus = wishbone.Interface(data_width=32, adr_width=32-log2_int(self.csr_separation))
        bank = wishbone.CSRBank(csrs, bus=csr_bus)
        self.submodules += bank
        self.kernel_cpu.add_wb_slave(self.mem_map[name], self.csr_separation*2**bank.decode_bits, bank.bus)
        self.add_csr_region(name,
                            self.mem_map[name] | 0x80000000, 32,
                            csrs)
