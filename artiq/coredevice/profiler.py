from collections import defaultdict
import subprocess


class Symbolizer:
    def __init__(self, binary, triple):
        self._addr2line = subprocess.Popen([
            triple + "-addr2line", "--exe=" + binary,
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
    def __init__(self, output, binary, triple, compression=True):
        self._output = output
        self._binary = binary
        self._current = defaultdict(lambda: None)
        self._ids = defaultdict(lambda: {})
        self._compression = compression
        self._symbolizer = Symbolizer(binary, triple)

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
