#!/usr/bin/env python3

import argparse
import os
import subprocess
import tempfile
import shutil
import re
import atexit
from functools import partial
from collections import defaultdict

from sipyco import common_args

from artiq import __version__ as artiq_version
from artiq import __artiq_dir__ as artiq_dir
from artiq.remoting import SSHClient, LocalClient
from artiq.frontend.bit2bin import bit2bin


def get_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="ARTIQ flashing/deployment tool",
        epilog="""\
Valid actions:

    * gateware: write main gateware bitstream to flash
    * rtm_gateware: write RTM gateware bitstream to flash
    * bootloader: write bootloader to flash
    * storage: write storage image to flash
    * firmware: write firmware to flash
    * load: load main gateware bitstream into device (volatile but fast)
    * rtm_load: load RTM gateware bitstream into device
    * erase: erase flash memory
    * start: trigger the target to (re)load its gateware bitstream from flash

Prerequisites:

    * Connect the board through its/a JTAG adapter.
    * Have OpenOCD installed and in your $PATH.
    * Have access to the JTAG adapter's devices. Udev rules from OpenOCD:
      'sudo cp openocd/contrib/99-openocd.rules /etc/udev/rules.d'
      and replug the device. Ensure you are member of the
      plugdev group: 'sudo adduser $USER plugdev' and re-login.
""")

    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    common_args.verbosity_args(parser)

    parser.add_argument("-n", "--dry-run",
                        default=False, action="store_true",
                        help="only show the openocd script that would be run")
    parser.add_argument("-H", "--host", metavar="HOSTNAME",
                        type=str, default=None,
                        help="SSH host where the board is located")
    parser.add_argument("-J", "--jump",
                        type=str, default=None,
                        help="SSH host to jump through")
    parser.add_argument("-t", "--target", default="kasli",
                        help="target board, default: %(default)s, one of: "
                             "kasli sayma metlino kc705")
    parser.add_argument("-V", "--variant", default=None,
                        help="board variant. Autodetected if only one is installed.")
    parser.add_argument("-I", "--preinit-command", default=[], action="append",
                        help="add a pre-initialization OpenOCD command. "
                             "Useful for selecting a board when several are connected.")
    parser.add_argument("-f", "--storage", help="write file to storage area")
    parser.add_argument("-d", "--dir", help="look for board binaries in this directory")
    parser.add_argument("--srcbuild", help="board binaries directory is laid out as a source build tree",
                        default=False, action="store_true")
    parser.add_argument("--force-rtm", help="force RTM actions on boards/variants that normally do not have a RTM",
                        default=False, action="store_true")
    parser.add_argument("action", metavar="ACTION", nargs="*",
                        default="gateware rtm_gateware bootloader firmware start".split(),
                        help="actions to perform, default: %(default)s")
    return parser


def scripts_path():
    p = ["share", "openocd", "scripts"]
    if os.name == "nt":
        p.insert(0, "Library")
    p = os.path.abspath(os.path.join(
        os.path.dirname(os.path.realpath(shutil.which("openocd"))),
        "..", *p))
    return p


def proxy_path():
    p = ["share", "bscan-spi-bitstreams"]
    p = os.path.abspath(os.path.join(
        os.path.dirname(os.path.realpath(shutil.which("openocd"))),
        "..", *p))
    return p


def find_proxy_bitfile(filename):
    for p in [proxy_path(), os.path.expanduser("~/.migen"),
              "/usr/local/share/migen", "/usr/share/migen"]:
        full_path = os.path.join(p, filename)
        if os.access(full_path, os.R_OK):
            return full_path
    raise FileNotFoundError("Cannot find proxy bitstream {}"
                            .format(filename))


def add_commands(script, *commands, **substs):
    script += [command.format(**substs) for command in commands]


class Programmer:
    def __init__(self, client, preinit_script):
        self._client = client
        self._board_script = []
        self._preinit_script = [
            "gdb_port disabled",
            "tcl_port disabled",
            "telnet_port disabled"
        ] + preinit_script
        self._loaded = defaultdict(lambda: None)
        self._script = ["init"]

    def _transfer_script(self, script):
        if isinstance(self._client, LocalClient):
            return "[find {}]".format(script)

        def rewriter(content):
            def repl(match):
                return self._transfer_script(match.group(1).decode()).encode()
            return re.sub(rb"\[find (.+?)\]", repl, content, re.DOTALL)

        script = os.path.join(scripts_path(), script)
        return self._client.upload(script, rewriter)

    def add_flash_bank(self, name, tap, index):
        add_commands(self._board_script,
            "target create {tap}.{name}.proxy testee -chain-position {tap}.tap",
            "flash bank {name} jtagspi 0 0 0 0 {tap}.{name}.proxy {ir:#x}",
            tap=tap, name=name, ir=0x02 + index)

    def erase_flash(self, bankname):
        self.load_proxy()
        add_commands(self._script,
                     "flash probe {bankname}",
                     "flash erase_sector {bankname} 0 last",
                     bankname=bankname)

    def load(self, bitfile, pld):
        os.stat(bitfile) # check for existence

        if self._loaded[pld] == bitfile:
            return
        self._loaded[pld] = bitfile

        bitfile = self._client.upload(bitfile)
        add_commands(self._script,
            "pld load {pld} {{{filename}}}",
            pld=pld, filename=bitfile)

    def load_proxy(self):
        raise NotImplementedError

    def write_binary(self, bankname, address, filename):
        self.load_proxy()

        size = os.path.getsize(filename)
        filename = self._client.upload(filename)
        add_commands(self._script,
            "flash probe {bankname}",
            "flash erase_sector {bankname} {firstsector} {lastsector}",
            "flash write_bank {bankname} {{{filename}}} {address:#x}",
            "flash verify_bank {bankname} {{{filename}}} {address:#x}",
            bankname=bankname, address=address, filename=filename,
            firstsector=address // self._sector_size,
            lastsector=(address + size - 1) // self._sector_size)

    def read_binary(self, bankname, address, length, filename):
        self.load_proxy()

        filename = self._client.prepare_download(filename)
        add_commands(self._script,
            "flash probe {bankname}",
            "flash read_bank {bankname} {{{filename}}} {address:#x} {length}",
            bankname=bankname, filename=filename, address=address, length=length)

    def start(self):
        raise NotImplementedError

    def script(self):
        return [
            *self._board_script,
            *self._preinit_script,
            *self._script,
            "exit"
        ]

    def run(self):
        cmdline = ["openocd"]
        if isinstance(self._client, LocalClient):
            cmdline += ["-s", scripts_path()]
        cmdline += ["-c", "; ".join(self.script())]

        cmdline = [arg.replace("{", "{{").replace("}", "}}") for arg in cmdline]
        self._client.run_command(cmdline)
        self._client.download()

        self._script = []


class ProgrammerXC7(Programmer):
    _sector_size = 0x10000

    def __init__(self, client, preinit_script, board, proxy):
        Programmer.__init__(self, client, preinit_script)
        self._proxy = proxy

        add_commands(self._board_script,
            "source {boardfile}",
            boardfile=self._transfer_script("board/{}.cfg".format(board)))
        self.add_flash_bank("spi0", "xc7", index=0)

        add_commands(self._script, "xadc_report xc7.tap")

    def load_proxy(self):
        self.load(find_proxy_bitfile(self._proxy), pld=0)

    def start(self):
        add_commands(self._script,
            "xc7_program xc7.tap")


class ProgrammerSayma(Programmer):
    _sector_size = 0x10000

    def __init__(self, client, preinit_script):
        Programmer.__init__(self, client, preinit_script)

        add_commands(self._board_script,
            "source {}".format(self._transfer_script("fpga/xilinx-xadc.cfg")),

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
            "source {}".format(self._transfer_script("cpld/xilinx-xcu.cfg")))
        self.add_flash_bank("spi0", "xcu", index=0)
        self.add_flash_bank("spi1", "xcu", index=1)

        add_commands(self._script, "echo \"RTM FPGA XADC:\"", "xadc_report xc7.tap")
        add_commands(self._script, "echo \"AMC FPGA XADC:\"", "xadc_report xcu.tap")

    def load_proxy(self):
        self.load(find_proxy_bitfile("bscan_spi_xcku040.bit"), pld=1)

    def start(self):
        add_commands(self._script, "xcu_program xcu.tap")


class ProgrammerMetlino(Programmer):
    _sector_size = 0x10000

    def __init__(self, client, preinit_script):
        Programmer.__init__(self, client, preinit_script)

        add_commands(self._board_script,
            "source {}".format(self._transfer_script("fpga/xilinx-xadc.cfg")),

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
            "set CHIP XCKU040",
            "source {}".format(self._transfer_script("cpld/xilinx-xcu.cfg")))
        self.add_flash_bank("spi0", "xcu", index=0)
        self.add_flash_bank("spi1", "xcu", index=1)

        add_commands(self._script, "echo \"AMC FPGA XADC:\"", "xadc_report xcu.tap")

    def load_proxy(self):
        self.load(find_proxy_bitfile("bscan_spi_xcku040.bit"), pld=0)

    def start(self):
        add_commands(self._script, "xcu_program xcu.tap")


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    config = {
        "kasli": {
            "programmer":   partial(ProgrammerXC7, board="kasli", proxy="bscan_spi_xc7a100t.bit"),
            "gateware":     ("spi0", 0x000000),
            "bootloader":   ("spi0", 0x400000),
            "storage":      ("spi0", 0x440000),
            "firmware":     ("spi0", 0x450000),
        },
        "sayma": {
            "programmer":   ProgrammerSayma,
            "gateware":     ("spi0", 0x000000),
            "bootloader":   ("spi1", 0x000000),
            "storage":      ("spi1", 0x040000),
            "firmware":     ("spi1", 0x050000),
            "rtm_gateware": ("spi1", 0x200000),
        },
        "metlino": {
            "programmer":   ProgrammerMetlino,
            "gateware":     ("spi0", 0x000000),
            "bootloader":   ("spi1", 0x000000),
            "storage":      ("spi1", 0x040000),
            "firmware":     ("spi1", 0x050000),
        },
        "kc705": {
            "programmer":   partial(ProgrammerXC7, board="kc705", proxy="bscan_spi_xc7k325t.bit"),
            "gateware":     ("spi0", 0x000000),
            "bootloader":   ("spi0", 0xaf0000),
            "storage":      ("spi0", 0xb30000),
            "firmware":     ("spi0", 0xb40000),
        },
    }[args.target]

    bin_dir = args.dir
    if bin_dir is None:
        bin_dir = os.path.join(artiq_dir, "board-support")

    needs_artifacts = any(
        action in args.action
        for action in ["gateware", "rtm_gateware", "bootloader", "firmware", "load", "rtm_load"])
    variant = args.variant
    if needs_artifacts and variant is None:
        variants = []
        if args.srcbuild:
            for entry in os.scandir(bin_dir):
                if entry.is_dir():
                    variants.append(entry.name)
        else:
            prefix = args.target + "-"
            for entry in os.scandir(bin_dir):
                if entry.is_dir() and entry.name.startswith(prefix):
                    variants.append(entry.name[len(prefix):])
        if args.target == "sayma":
            try:
                variants.remove("rtm")
            except ValueError:
                pass
        if len(variants) == 0:
            raise FileNotFoundError("no variants found, did you install a board binary package?")
        elif len(variants) == 1:
            variant = variants[0]
        else:
            raise ValueError("more than one variant found for selected board, specify -V. "
                "Found variants: {}".format(" ".join(sorted(variants))))
    if needs_artifacts:
        if args.srcbuild:
            variant_dir = variant
        else:
            variant_dir = args.target + "-" + variant
        if args.target == "sayma":
            if args.srcbuild:
                rtm_variant_dir = "rtm"
            else:
                rtm_variant_dir = "sayma-rtm"

    if args.host is None:
        client = LocalClient()
    else:
        client = SSHClient(args.host, args.jump)

    programmer = config["programmer"](client, preinit_script=args.preinit_command)

    def artifact_path(this_variant_dir, *path_filename):
        if args.srcbuild:
            # source tree - use path elements to locate file
            return os.path.join(bin_dir, this_variant_dir, *path_filename)
        else:
            # flat tree - all files in the same directory, discard path elements
            *_, filename = path_filename
            return os.path.join(bin_dir, this_variant_dir, filename)

    def convert_gateware(bit_filename, header=False):
        bin_handle, bin_filename = tempfile.mkstemp(
            prefix="artiq_", suffix="_" + os.path.basename(bit_filename))
        with open(bit_filename, "rb") as bit_file, \
                open(bin_handle, "wb") as bin_file:
            if header:
                bin_file.write(b"\x00"*8)
            bit2bin(bit_file, bin_file)
            if header:
                magic = 0x5352544d  # "SRTM", see sayma_rtm target
                length = bin_file.tell() - 8
                bin_file.seek(0)
                bin_file.write(magic.to_bytes(4, byteorder="big"))
                bin_file.write(length.to_bytes(4, byteorder="big"))
        atexit.register(lambda: os.unlink(bin_filename))
        return bin_filename

    for action in args.action:
        if action == "gateware":
            gateware_bin = convert_gateware(
                artifact_path(variant_dir, "gateware", "top.bit"))
            programmer.write_binary(*config["gateware"], gateware_bin)
        elif action == "rtm_gateware":
            if args.force_rtm or (
                    args.target == "sayma" and variant != "simplesatellite" and variant != "master"):
                rtm_gateware_bin = convert_gateware(
                    artifact_path(rtm_variant_dir, "gateware", "top.bit"), header=True)
                programmer.write_binary(*config["rtm_gateware"],
                                        rtm_gateware_bin)
        elif action == "bootloader":
            bootloader_bin = artifact_path(variant_dir, "software", "bootloader", "bootloader.bin")
            programmer.write_binary(*config["bootloader"], bootloader_bin)
        elif action == "storage":
            storage_img = args.storage
            programmer.write_binary(*config["storage"], storage_img)
        elif action == "firmware":
            if variant.endswith("satellite"):
                firmware = "satman"
            else:
                firmware = "runtime"

            firmware_fbi = artifact_path(variant_dir, "software", firmware, firmware + ".fbi")
            programmer.write_binary(*config["firmware"], firmware_fbi)
        elif action == "load":
            if args.target == "sayma":
                gateware_bit = artifact_path(variant_dir, "gateware", "top.bit")
                programmer.load(gateware_bit, 1)
            else:
                gateware_bit = artifact_path(variant_dir, "gateware", "top.bit")
                programmer.load(gateware_bit, 0)
        elif action == "rtm_load":
            if args.force_rtm or (
                    args.target == "sayma" and variant != "simplesatellite" and variant != "master"):
                rtm_gateware_bit = artifact_path(rtm_variant_dir, "gateware", "top.bit")
                programmer.load(rtm_gateware_bit, 0)
        elif action == "start":
            programmer.start()
        elif action == "erase":
            if args.target == "sayma" or args.target == "metlino":
                programmer.erase_flash("spi0")
                programmer.erase_flash("spi1")
            else:
                programmer.erase_flash("spi0")
        else:
            raise ValueError("invalid action", action)

    if args.dry_run:
        print("\n".join(programmer.script()))
    else:
        programmer.run()


if __name__ == "__main__":
    main()
