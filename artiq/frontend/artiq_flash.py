#!/usr/bin/env python3

import argparse
import os
import subprocess
import tempfile
import shutil
from functools import partial

from artiq import __artiq_dir__ as artiq_dir
from artiq.frontend.bit2bin import bit2bin


def get_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="ARTIQ flashing/deployment tool",
        epilog="""\
Valid actions:

    * proxy: load the flash proxy gateware bitstream
    * gateware: write gateware bitstream to flash
    * bios: write bios to flash
    * runtime: write runtime to flash
    * storage: write storage image to flash
    * load: load gateware bitstream into device (volatile but fast)
    * start: trigger the target to (re)load its gateware bitstream from flash

Prerequisites:

    * Connect the board through its/a JTAG adapter.
    * Have OpenOCD installed and in your $PATH.
    * Have access to the JTAG adapter's devices. Udev rules from OpenOCD:
      'sudo cp openocd/contrib/99-openocd.rules /etc/udev/rules.d'
      and replug the device. Ensure you are member of the
      plugdev group: 'sudo adduser $USER plugdev' and re-login.
""")
    parser.add_argument("-t", "--target", default="kc705",
                        help="target board, default: %(default)s")
    parser.add_argument("-m", "--adapter", default=None,
                        help="target adapter, default: board-dependent")
    parser.add_argument("--preinit-command", default=[], action="append",
                        help="add a pre-initialization OpenOCD command. "
                             "Useful for selecting a development board " 
                             "when several are connected.")
    parser.add_argument("-f", "--storage", help="write file to storage area")
    parser.add_argument("-d", "--dir", help="look for files in this directory")
    parser.add_argument("action", metavar="ACTION", nargs="*",
                        default="proxy gateware bios runtime start".split(),
                        help="actions to perform, default: %(default)s")
    return parser


def scripts_path():
    p = ["share", "openocd", "scripts"]
    if os.name == "nt":
        p.insert(0, "Library")
    p = os.path.abspath(os.path.join(
        os.path.dirname(shutil.which("openocd")),
        "..", *p))
    return p


def proxy_path():
    p = ["share", "bscan-spi-bitstreams"]
    p = os.path.abspath(os.path.join(
        os.path.dirname(shutil.which("openocd")),
        "..", *p))
    return p


class Programmer:
    def __init__(self, target_file, preinit_commands):
        self.target_file = target_file
        self.preinit_commands = preinit_commands
        self.prog = []

    def init(self):
        self.prog.extend(self.preinit_commands)
        self.prog.append("init")

    def load(self, bitfile):
        raise NotImplementedError

    def proxy(self, proxy_bitfile):
        raise NotImplementedError

    def flash_binary(self, flashno, address, filename):
        raise NotImplementedError

    def start(self):
        raise NotImplementedError

    def do(self):
        self.prog.append("exit")
        cmdline = [
            "openocd",
            "-s", scripts_path()
        ]
        if self.target_file is not None:
            cmdline += ["-f", self.target_file]
        cmdline += ["-c", "; ".join(self.prog)]
        subprocess.check_call(cmdline)


class ProgrammerJtagSpi7(Programmer):
    def __init__(self, target, preinit_commands):
        Programmer.__init__(self, os.path.join("board", target + ".cfg"),
                            preinit_commands)
        self.init()

    def load(self, bitfile, pld=0):
        self.prog.append("pld load {} {{{}}}".format(pld, bitfile))

    def proxy(self, proxy_bitfile, pld=0):
        self.prog.append("jtagspi_init {} {{{}}}".format(pld, proxy_bitfile))

    def flash_binary(self, flashno, address, filename):
        # jtagspi_program supports only one flash
        assert flashno == 0
        self.prog.append("jtagspi_program {{{}}} 0x{:x}".format(
                filename, address))

    def start(self):
        self.prog.append("xc7_program xc7.tap")


class ProgrammerSayma(Programmer):
    def __init__(self, preinit_commands):
        # TODO: support Sayma RTM
        Programmer.__init__(self, None, preinit_commands)
        self.proxy_loaded = False
        self.prog += [
            "interface ftdi",
            "ftdi_device_desc \"Quad RS232-HS\"",
            "ftdi_vid_pid 0x0403 0x6011",
            "ftdi_channel 0",
            # EN_USB_JTAG on ADBUS7: out, high
            # nTRST on ADBUS4: out, high, but R46 is DNP
            "ftdi_layout_init 0x0098 0x008b",
            "reset_config none",

            "adapter_khz 5000",
            "transport select jtag",

            "source [find cpld/xilinx-xc7.cfg]",  # tap 0, pld 0
            "set CHIP XCKU040",
            "source [find cpld/xilinx-xcu.cfg]",  # tap 1, pld 1

            "set XILINX_USER1 0x02",
            "set XILINX_USER2 0x03",
            "set JTAGSPI_IR $XILINX_USER1",
            "source [find cpld/jtagspi.cfg]",
            "flash bank xcu.spi0 jtagspi 0 0 0 0 xcu.proxy $XILINX_USER1",
            "flash bank xcu.spi1 jtagspi 0 0 0 0 xcu.proxy $XILINX_USER2"
        ]
        self.init()

    def load(self, bitfile, pld=1):
        self.prog.append("pld load {} {{{}}}".format(pld, bitfile))

    def proxy(self, proxy_bitfile, pld=1):
        self.load(proxy_bitfile, pld)
        self.prog.append("reset halt")

    def flash_binary(self, flashno, address, filename):
        self.prog += [
            "flash probe xcu.spi{}".format(flashno),
            "irscan xcu.tap $XILINX_USER{}".format(flashno+1),
            "flash write_bank {} {} 0x{:x}".format(flashno, filename, address)
        ]

    def start(self):
        self.proxy_loaded = False
        self.prog.append("xcu_program xcu.tap")


def main():
    parser = get_argparser()
    opts = parser.parse_args()

    config = {
        "kc705": {
            "programmer_factory": partial(ProgrammerJtagSpi7, "kc705"),
            "proxy_bitfile": "bscan_spi_xc7k325t.bit",
            "adapters": ["nist_clock", "nist_qc2"],
            "gateware": (0, 0x000000),
            "bios":     (0, 0xaf0000),
            "runtime":  (0, 0xb00000),
            "storage":  (0, 0xb80000),
        },
        "sayma": {
            "programmer_factory": ProgrammerSayma,
            "proxy_bitfile": "bscan_spi_xcku040-sayma.bit",
            "adapters": [],
            "gateware": (0, 0x000000),
            "bios":     (1, 0x000000),
            "runtime":  (1, 0x010000),
            "storage":  (1, 0x090000),
        },
    }[opts.target]

    adapter = opts.adapter
    if adapter is not None and adapter not in config["adapters"]:
        raise SystemExit("Invalid adapter for this board")
    if adapter is None and config["adapters"]:
        adapter = config["adapters"][0]
    bin_dir = opts.dir
    if bin_dir is None:
        if adapter is None:
            bin_dir = os.path.join(artiq_dir, "binaries",
                        "{}".format(opts.target))
        else:
            bin_dir = os.path.join(artiq_dir, "binaries",
                                    "{}-{}".format(opts.target, adapter))
    if not os.path.exists(bin_dir) and opts.action != ["start"]:
        raise SystemExit("Binaries directory '{}' does not exist"
                         .format(bin_dir))

    programmer = config["programmer_factory"](opts.preinit_command)

    conv = False
    for action in opts.action:
        if action == "proxy":
            proxy_found = False
            for p in [bin_dir, proxy_path(), os.path.expanduser("~/.migen"),
                      "/usr/local/share/migen", "/usr/share/migen"]:
                proxy_bitfile = os.path.join(p, config["proxy_bitfile"])
                if os.access(proxy_bitfile, os.R_OK):
                    programmer.proxy(proxy_bitfile)
                    proxy_found = True
                    break
            if not proxy_found:
                raise SystemExit(
                    "proxy gateware bitstream {} not found".format(config["proxy_bitfile"]))
        elif action == "gateware":
            bin = os.path.join(bin_dir, "top.bin")
            if not os.access(bin, os.R_OK):
                bin_handle, bin = tempfile.mkstemp()
                bit = os.path.join(bin_dir, "top.bit")
                conv = True
            programmer.flash_binary(*config["gateware"], bin)
        elif action == "bios":
            programmer.flash_binary(*config["bios"], os.path.join(bin_dir, "bios.bin"))
        elif action == "runtime":
            programmer.flash_binary(*config["runtime"], os.path.join(bin_dir, "runtime.fbi"))
        elif action == "storage":
            programmer.flash_binary(*config["storage"], opts.storage)
        elif action == "load":
            programmer.load(os.path.join(bin_dir, "top.bit"))
        elif action == "start":
            programmer.start()
        else:
            raise ValueError("invalid action", action)

    if conv:
        with open(bit, "rb") as f, open(bin_handle, "wb") as g:
            bit2bin(f, g)
    try:
        programmer.do()
    finally:
        if conv:
            os.unlink(bin)


if __name__ == "__main__":
    main()
