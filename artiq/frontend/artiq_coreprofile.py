#!/usr/bin/env python3

import argparse
import sys
import struct
from collections import defaultdict
import subprocess

from artiq.tools import verbosity_args, init_logger
from artiq.master.databases import DeviceDB
from artiq.coredevice.comm_mgmt import CommMgmt


class Symbolizer:
    def __init__(self, binary):
        self._addr2line = subprocess.Popen([
            "or1k-linux-addr2line", "--exe=" + binary,
            "--addresses", "--demangle=rust", "--functions", "--inlines"
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)

    def symbolize(self, addr):
        self._addr2line.stdin.write("0x{:08x}\n0\n".format(addr))
        self._addr2line.stdin.flush()
        self._addr2line.stdout.readline() # 0x[addr]

        result = []
        while True:
            function = self._addr2line.stdout.readline().rstrip()

            # check for end marker
            if function == "0x00000000":          # 0x00000000
                self._addr2line.stdout.readline() # ??
                self._addr2line.stdout.readline() # ??:0
                return result

            file, line = self._addr2line.stdout.readline().rstrip().split(":")

            result.append((function, file, line))


class CallgrindWriter:
    def __init__(self, output, binary, compression=True):
        self._output = output
        self._binary = binary
        self._current = defaultdict(lambda: None)
        self._ids = defaultdict(lambda: {})
        self._compression = compression
        self._symbolizer = Symbolizer(binary)

    def _write(self, fmt, *args, **kwargs):
        self._output.write(fmt.format(*args, **kwargs))
        self._output.write("\n")

    def _spec(self, spec, value):
        if self._current[spec] == value:
            return
        self._current[spec] = value

        if not self._compression or value == "??":
            self._write("{}={}", spec, value)
            return

        spec_ids = self._ids[spec]
        if value in spec_ids:
            self._write("{}=({})", spec, spec_ids[value])
        else:
            spec_ids[value] = len(spec_ids) + 1
            self._write("{}=({}) {}", spec, spec_ids[value], value)

    def header(self):
        self._write("# callgrind format")
        self._write("version: 1")
        self._write("creator: ARTIQ")
        self._write("positions: instr line")
        self._write("events: Hits")
        self._write("")
        self._spec("ob", self._binary)
        self._spec("cob", self._binary)

    def hit(self, addr, count):
        for function, file, line in self._symbolizer.symbolize(addr):
            self._spec("fn", function)
            self._spec("fl", file)
            self._write("0x{:08x} {} {}", addr, line, count)

    def edge(self, caller, callee, count):
        function, file, line = next(self._symbolizer.symbolize(callee))
        self._spec("cfn", function)
        self._spec("cfl", file)
        self._write("calls={} 0x{:08x} {}", count, callee, line)

        function, file, line = next(self._symbolizer.symbolize(caller))
        self._spec("fn", function)
        self._spec("fl", file)
        self._write("0x{:08x} {} {}", caller, line, count)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device profiling tool")

    verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                       help="device database file (default: '%(default)s')")

    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    p_start = subparsers.add_parser("start",
                                    help="start profiling")
    p_start.add_argument("--interval", metavar="MICROS", type=int, default=2000,
                         help="sampling interval, in microseconds")
    p_start.add_argument("--hits-size", metavar="ENTRIES", type=int, default=8192,
                         help="hit buffer size")
    p_start.add_argument("--edges-size", metavar="ENTRIES", type=int, default=0,
                         help="edge buffer size (edge profiling not implemented)")

    p_stop = subparsers.add_parser("stop",
                                   help="stop profiling")

    p_save = subparsers.add_parser("save",
                                   help="save profile")
    p_save.add_argument("output", metavar="OUTPUT", type=argparse.FileType("w"),
                        help="file to save profile to, in Callgrind format")
    p_save.add_argument("firmware", metavar="FIRMWARE", type=str,
                        help="path to firmware ELF file")
    p_save.add_argument("--no-compression", default=False, action='store_true',
                        help="disable profile compression")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    core_addr = DeviceDB(args.device_db).get("core")["arguments"]["host"]
    mgmt = CommMgmt(core_addr)
    try:
        if args.action == "start":
            mgmt.start_profiler(args.interval, args.hits_size, args.edges_size)
        elif args.action == "stop":
            mgmt.stop_profiler()
        elif args.action == "save":
            hits, edges = mgmt.get_profile()
            writer = CallgrindWriter(args.output, args.firmware, not args.no_compression)
            writer.header()
            for addr, count in hits.items():
                writer.hit(addr, count)
            for (caller, callee), count in edges.items():
                writer.edge(caller, callee, count)
    finally:
        mgmt.close()

if __name__ == "__main__":
    main()
