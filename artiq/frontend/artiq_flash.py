#!/usr/bin/env python3

import argparse
import os
import subprocess
import tempfile
import shutil
import re
from functools import partial

from artiq import __artiq_dir__ as artiq_dir
from artiq.tools import verbosity_args, init_logger
from artiq.remoting import SSHClient, LocalClient
from artiq.frontend.bit2bin import bit2bin


def get_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="ARTIQ flashing/deployment tool",
        epilog="""\
Valid actions:

    * proxy: load the flash proxy gateware bitstream
    * gateware: write gateware bitstream to flash
    * bootloader: write bootloader to flash
    * storage: write storage image to flash
    * firmware: write firmware to flash
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

    verbosity_args(parser)

    parser.add_argument("-n", "--dry-run",
                        default=False, action="store_true",
                        help="only show the openocd script that would be run")
    parser.add_argument("-H", "--host", metavar="HOSTNAME",
                        type=str, default=None,
                        help="SSH host where the development board is located")
    parser.add_argument("-t", "--target", default="kc705",
                        help="target board, default: %(default)s, one of: "
                             "kc705 kasli sayma_amc sayma_rtm")
    parser.add_argument("-m", "--variant", default=None,
                        help="board variant")
    parser.add_argument("-I", "--preinit-command", default=[], action="append",
                        help="add a pre-initialization OpenOCD command. "
                             "Useful for selecting a development board "
                             "when several are connected.")
    parser.add_argument("-f", "--storage", help="write file to storage area")
    parser.add_argument("-d", "--dir", help="look for files in this directory")
    parser.add_argument("--srcbuild", help="look for bitstream, bootloader and firmware in this "
                                            "ARTIQ source build tree")
    parser.add_argument("action", metavar="ACTION", nargs="*",
                        default="proxy gateware bootloader firmware start".split(),
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
    def __init__(self, client, preinit_script):
        self._client = client
        self._preinit_script = preinit_script
        self._script = []

    def _transfer_script(self, script):
        if isinstance(self._client, LocalClient):
            return "[find {}]".format(script)

        def rewriter(content):
            def repl(match):
                return self._transfer_script(match.group(1).decode()).encode()
            return re.sub(rb"\[find (.+?)\]", repl, content, re.DOTALL)

        script = os.path.join(scripts_path(), script)
        return self._client.transfer_file(script, rewriter)

    def script(self):
        return [
            *self._preinit_script,
            "init",
            *self._script,
            "exit"
        ]

    def run(self):
        cmdline = ["openocd"]
        if isinstance(self._client, LocalClient):
            cmdline += ["-s", scripts_path()]
        cmdline += ["-c", "; ".join(script)]

        cmdline = [arg.replace("{", "{{").replace("}", "}}") for arg in self.script()]
        self._client.run_command(cmdline)

    def load(self, bitfile, pld):
        raise NotImplementedError

    def proxy(self, proxy_bitfile, pld):
        raise NotImplementedError

    def flash_binary(self, flashno, address, filename):
        raise NotImplementedError

    def start(self):
        raise NotImplementedError


class ProgrammerJtagSpi7(Programmer):
    def __init__(self, client, target, preinit_script):
        Programmer.__init__(self, client, preinit_script)

        target_file = self._transfer_script(os.path.join("board", target + ".cfg"))
        self._preinit_script.append("source {}".format(target_file))

    def load(self, bitfile, pld=0):
        bitfile = self._client.transfer_file(bitfile)
        self._script.append("pld load {} {{{}}}".format(pld, bitfile))

    def proxy(self, proxy_bitfile, pld=0):
        proxy_bitfile = self._client.transfer_file(proxy_bitfile)
        self._script.append("jtagspi_init {} {{{}}}".format(pld, proxy_bitfile))

    def flash_binary(self, flashno, address, filename):
        assert flashno == 0 # jtagspi_program supports only one flash

        filename = self._client.transfer_file(filename)
        self._script.append("jtagspi_program {{{}}} 0x{:x}".format(
                filename, address))

    def start(self):
        self._script.append("xc7_program xc7.tap")


class ProgrammerSayma(Programmer):
    sector_size = 0x10000

    def __init__(self, client, preinit_script):
        Programmer.__init__(self, client, preinit_script)

        self._preinit_script += [
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

            # tap 0, pld 0
            "source {}".format(self._transfer_script("cpld/xilinx-xc7.cfg")),
            # tap 1, pld 1
            "set CHIP XCKU040",
            "source {}".format(self._transfer_script("cpld/xilinx-xcu.cfg")),

            "target create xcu.proxy testee -chain-position xcu.tap",
            "set XILINX_USER1 0x02",
            "set XILINX_USER2 0x03",
            "flash bank xcu.spi0 jtagspi 0 0 0 0 xcu.proxy $XILINX_USER1",
            "flash bank xcu.spi1 jtagspi 0 0 0 0 xcu.proxy $XILINX_USER2"
        ]

    def load(self, bitfile, pld=1):
        bitfile = self._client.transfer_file(bitfile)
        self._script.append("pld load {} {{{}}}".format(pld, bitfile))

    def proxy(self, proxy_bitfile, pld=1):
        self.load(proxy_bitfile, pld)
        self._script.append("reset halt")

    def flash_binary(self, flashno, address, filename):
        sector_first = address // self.sector_size
        size = os.path.getsize(filename)
        sector_last = sector_first + (size - 1) // self.sector_size
        filename = self._client.transfer_file(filename)
        self._script += [
            "flash probe xcu.spi{}".format(flashno),
            "flash erase_sector {} {} {}".format(flashno, sector_first, sector_last),
            "flash write_bank {} {{{}}} 0x{:x}".format(flashno, filename, address),
            "flash verify_bank {} {{{}}} 0x{:x}".format(flashno, filename, address),
        ]

    def start(self):
        self._script.append("xcu_program xcu.tap")


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    config = {
        "kc705": {
            "programmer_factory": partial(ProgrammerJtagSpi7, target="kc705"),
            "proxy_bitfile": "bscan_spi_xc7k325t.bit",
            "variants": ["nist_clock", "nist_qc2"],
            "gateware":   (0, 0x000000),
            "bootloader": (0, 0xaf0000),
            "storage":    (0, 0xb30000),
            "firmware":   (0, 0xb40000),
        },
        "kasli": {
            "programmer_factory": partial(ProgrammerJtagSpi7, target="kasli"),
            "proxy_bitfile": "bscan_spi_xc7a100t.bit",
            "variants": ["opticlock"],
            "gateware":   (0, 0x000000),
            "bootloader": (0, 0x400000),
            "storage":    (0, 0x440000),
            "firmware":   (0, 0x450000),
        },
        "sayma_amc": {
            "programmer_factory": ProgrammerSayma,
            "proxy_bitfile": "bscan_spi_xcku040-sayma.bit",
            "variants": ["standalone", "master", "satellite"],
            "gateware":   (0, 0x000000),
            "bootloader": (1, 0x000000),
            "storage":    (1, 0x040000),
            "firmware":   (1, 0x050000),
        },
        "sayma_rtm": {
            "programmer_factory": ProgrammerSayma,
            "proxy_bitfile": "bscan_spi_xcku040-sayma.bit",
            "gateware":   (1, 0x150000),
        },
    }[args.target]

    variant = args.variant
    if "variants" in config:
        if variant is not None and variant not in config["variants"]:
            raise SystemExit("Invalid variant for this board")
        if variant is None:
            variant = config["variants"][0]
    bin_dir = args.dir
    if bin_dir is None:
        if variant:
            bin_name = "{}-{}".format(args.target, variant)
        else:
            bin_name = args.target
        bin_dir = os.path.join(artiq_dir, "binaries", bin_name)
    if args.srcbuild is None and not os.path.exists(bin_dir) and args.action != ["start"]:
        raise SystemExit("Binaries directory '{}' does not exist"
                         .format(bin_dir))

    if args.host is None:
        client = LocalClient()
    else:
        client = SSHClient(args.host)

    programmer = config["programmer_factory"](client, preinit_script=args.preinit_command)

    conv = False
    for action in args.action:
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
            if args.srcbuild is None:
                path = bin_dir
            else:
                path = os.path.join(args.srcbuild, "gateware")
            bin = os.path.join(path, "top.bin")
            if not os.access(bin, os.R_OK):
                bin_handle, bin = tempfile.mkstemp()
                bit = os.path.join(path, "top.bit")
                with open(bit, "rb") as f, open(bin_handle, "wb") as g:
                    bit2bin(f, g)
                conv = True
            programmer.flash_binary(*config["gateware"], bin)
        elif action == "bootloader":
            if args.srcbuild is None:
                path = bin_dir
            else:
                path = os.path.join(args.srcbuild, "software", "bootloader")
            programmer.flash_binary(*config["bootloader"], os.path.join(path, "bootloader.bin"))
        elif action == "storage":
            programmer.flash_binary(*config["storage"], args.storage)
        elif action == "firmware":
            if variant == "satellite":
                firmware_name = "satman"
            else:
                firmware_name = "runtime"
            if args.srcbuild is None:
                path = bin_dir
            else:
                path = os.path.join(args.srcbuild, "software", firmware_name)
            programmer.flash_binary(*config["firmware"],
                                    os.path.join(path, firmware_name + ".fbi"))
        elif action == "load":
            if args.srcbuild is None:
                path = bin_dir
            else:
                path = os.path.join(args.srcbuild, "gateware")
            programmer.load(os.path.join(path, "top.bit"))
        elif action == "start":
            programmer.start()
        else:
            raise ValueError("invalid action", action)

    if args.dry_run:
        print("\n".join(programmer.script()))
    else:
        try:
            programmer.run()
        finally:
            if conv:
                os.unlink(bin)


if __name__ == "__main__":
    main()
