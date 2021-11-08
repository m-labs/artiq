import os
import subprocess

from migen import *
from migen.build.platforms.sinara import kasli
from misoc.interconnect.csr import *
from misoc.integration.builder import *

from artiq.gateware.amp import AMPSoC
from artiq import __version__ as artiq_version
from artiq import __artiq_dir__ as artiq_dir


__all__ = ["add_identifier", "build_artiq_soc"]


def get_identifier_string(soc, suffix="", add_class_name=True):
    r = artiq_version
    if suffix or add_class_name:
        r += ";"
    if add_class_name:
        r += getattr(soc, "class_name_override", soc.__class__.__name__.lower())
    r += suffix
    return r


class ReprogrammableIdentifier(Module, AutoCSR):
    def __init__(self, ident):
        self.address = CSRStorage(8)
        self.data = CSRStatus(8)

        contents = list(ident.encode())
        l = len(contents)
        if l > 255:
            raise ValueError("Identifier string must be 255 characters or less")
        contents.insert(0, l)

        for i in range(8):
            self.specials += Instance("ROM256X1", name="identifier_str"+str(i),
                i_A0=self.address.storage[0], i_A1=self.address.storage[1],
                i_A2=self.address.storage[2], i_A3=self.address.storage[3],
                i_A4=self.address.storage[4], i_A5=self.address.storage[5],
                i_A6=self.address.storage[6], i_A7=self.address.storage[7],
                o_O=self.data.status[i],
                p_INIT=sum(1 << j if c & (1 << i) else 0 for j, c in enumerate(contents)))


def add_identifier(soc, *args, gateware_identifier_str=None, **kwargs):
    if hasattr(soc, "identifier"):
        raise ValueError
    identifier_str = get_identifier_string(soc, *args, **kwargs)
    soc.submodules.identifier = ReprogrammableIdentifier(gateware_identifier_str or identifier_str)
    soc.config["IDENTIFIER_STR"] = identifier_str


def build_artiq_soc(soc, argdict):
    firmware_dir = os.path.join(artiq_dir, "firmware")
    builder = Builder(soc, **argdict)
    builder.software_packages = []
    builder.add_software_package("bootloader", os.path.join(firmware_dir, "bootloader"))
    is_kasli_v1 = isinstance(soc.platform, kasli.Platform) and soc.platform.hw_rev in ("v1.0", "v1.1")
    if isinstance(soc, AMPSoC):
        kernel_cpu_type = "vexriscv" if is_kasli_v1 else "vexriscv-g"
        builder.add_software_package("libm", cpu_type=kernel_cpu_type)
        builder.add_software_package("libprintf", cpu_type=kernel_cpu_type)
        builder.add_software_package("libunwind", cpu_type=kernel_cpu_type)
        builder.add_software_package("ksupport", os.path.join(firmware_dir, "ksupport"), cpu_type=kernel_cpu_type)
        # Generate unwinder for soft float target (ARTIQ runtime)
        # If the kernel lacks FPU, then the runtime unwinder is already generated
        if not is_kasli_v1:
            builder.add_software_package("libunwind")
        builder.add_software_package("runtime", os.path.join(firmware_dir, "runtime"))
    else:
        # Assume DRTIO satellite.
        builder.add_software_package("satman", os.path.join(firmware_dir, "satman"))
    try:
        builder.build()
    except subprocess.CalledProcessError as e:
        raise SystemExit("Command {} failed".format(" ".join(e.cmd)))
