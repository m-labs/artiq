import os
import subprocess

from migen import *
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

        init_params = {i: 0 for i in range(0x40)}
        for i, c in enumerate(contents):
            # 0x38 was determined empirically. Another Xilinx mystery.
            row = 0x38 + i//32
            col = 8*(i % 32)
            init_params[row] |= c << col
        init_params = {"p_INIT_{:02X}".format(k): v for k, v in init_params.items()}

        self.specials += Instance("RAMB18E1", name="identifier_str",
            i_ADDRARDADDR=Cat(C(0, 3), self.address.storage),
            i_CLKARDCLK=ClockSignal(),
            o_DOADO=self.data.status,
            i_ENARDEN=1,
            p_READ_WIDTH_A=9,
            **init_params)


def add_identifier(soc, *args, **kwargs):
    if hasattr(soc, "identifier"):
        raise ValueError
    identifier_str = get_identifier_string(soc, *args, **kwargs)
    soc.submodules.identifier = ReprogrammableIdentifier(identifier_str)
    soc.config["IDENTIFIER_STR"] = identifier_str



def build_artiq_soc(soc, argdict):
    firmware_dir = os.path.join(artiq_dir, "firmware")
    builder = Builder(soc, **argdict)
    builder.software_packages = []
    builder.add_software_package("bootloader", os.path.join(firmware_dir, "bootloader"))
    if isinstance(soc, AMPSoC):
        builder.add_software_package("libm")
        builder.add_software_package("libprintf")
        builder.add_software_package("libunwind")
        builder.add_software_package("ksupport", os.path.join(firmware_dir, "ksupport"))
        builder.add_software_package("runtime", os.path.join(firmware_dir, "runtime"))
    else:
        # Assume DRTIO satellite.
        builder.add_software_package("satman", os.path.join(firmware_dir, "satman"))
    try:
        builder.build()
    except subprocess.CalledProcessError as e:
        raise SystemExit("Command {} failed".format(" ".join(e.cmd)))
