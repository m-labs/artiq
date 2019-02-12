import os
import subprocess

from misoc.cores import identifier
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


def add_identifier(soc, *args, **kwargs):
    if hasattr(soc, "identifier"):
        raise ValueError
    identifier_str = get_identifier_string(soc, *args, **kwargs)
    soc.submodules.identifier = identifier.Identifier(identifier_str)
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
