from math import log, sqrt
import logging
import struct

import serial

from artiq.wavesynth.coefficients import discrete_compensate
from artiq.language.core import portable


logger = logging.getLogger(__name__)



class Segment:
    """Serialize the lines for a single Segment.

    Attributes:
        max_time (int): Maximum duration of a line.
        max_val (int): Maximum absolute value (scale) of the DAC output.
        max_out (float): Output voltage at :attr:`max_val`. In Volt.
        out_scale (float): Steps per Volt.
        cordic_gain (float): CORDIC amplitude gain.
        addr (int): Address assigned to this segment.
        data (bytes): Serialized segment data.
    """
    max_time = 1 << 16  # uint16 timer
    max_val = 1 << 15  # int16 DAC
    max_out = 10.  # Volt
    out_scale = max_val/max_out
    cordic_gain = 1.
    for i in range(16):
        cordic_gain *= sqrt(1 + 2**(-2*i))

    def __init__(self):
        self.data = b""
        self.addr = None

    def line(self, typ, duration, data, trigger=False, silence=False,
             aux=False, shift=0, jump=False, clear=False, wait=False):
        """Append a line to this segment.

        Args:
            typ (int): Output module to target with this line.
            duration (int): Duration of the line in units of
                ``clock_period*2**shift``.
            data (bytes): Opaque data for the output module.
            trigger (bool): Wait for trigger assertion before executing
                this line.
            silence (bool): Disable DAC clocks for the duration of this line.
            aux (bool): Assert the AUX (F5 TTL) output during this line.
                The corresponding global AUX routing setting determines which
                channels control AUX.
            shift (int): Duration and spline evolution exponent.
            jump (bool): Return to the frame address table after this line.
            clear (bool): Clear the DDS phase accumulator when starting to
                exectute this line.
            wait (bool): Wait for trigger assertion before executing the next
                line.
        """
        assert len(data) % 2 == 0, data
        assert len(data)//2 <= 14
        # assert dt*(1 << shift) > 1 + len(data)//2
        header = (
            1 + len(data)//2 | (typ << 4) | (trigger << 6) | (silence << 7) |
            (aux << 8) | (shift << 9) | (jump << 13) | (clear << 14) |
            (wait << 15)
        )
        self.data += struct.pack("<HH", header, duration) + data

    @staticmethod
    def pack(widths, values):
        """Pack spline data.

        Args:
            widths (list[int]): Widths of values in multiples of 16 bits.
            values (list[int]): Values to pack.

        Returns:
            data (bytes): Packed data.
        """
        fmt = "<"
        ud = []
        for width, value in zip(widths, values):
            value = int(round(value * (1 << 16*width)))
            if width == 2:
                ud.append(value & 0xffff)
                fmt += "H"
                value >>= 16
                width -= 1
            ud.append(value)
            fmt += "hi"[width]
        try:
            return struct.pack(fmt, *ud)
        except struct.error as e:
            logger.error("can not pack %s as %s (%s as %s): %s",
                         values, widths, ud, fmt, e)
            raise e

    def bias(self, amplitude=[], **kwargs):
        """Append a bias line to this segment.

        Args:
            amplitude (list[float]): Amplitude coefficients in in Volts and
                increasing powers of ``1/(2**shift*clock_period)``.
                Discrete time compensation will be applied.
            **kwargs: Passed to :meth:`line`.
        """
        coef = [self.out_scale*a for a in amplitude]
        discrete_compensate(coef)
        data = self.pack([0, 1, 2, 2], coef)
        self.line(typ=0, data=data, **kwargs)

    def dds(self, amplitude=[], phase=[], **kwargs):
        """Append a DDS line to this segment.

        Args:
            amplitude (list[float]): Amplitude coefficients in in Volts and
                increasing powers of ``1/(2**shift*clock_period)``.
                Discrete time compensation and CORDIC gain compensation
                will be applied by this method.
            phase (list[float]): Phase/frequency/chirp coefficients.
                ``phase[0]`` in ``turns``,
                ``phase[1]`` in ``turns/clock_period``,
                ``phase[2]`` in ``turns/(clock_period**2*2**shift)``.
            **kwargs: Passed to :meth:`line`.
        """
        scale = self.out_scale/self.cordic_gain
        coef = [scale*a for a in amplitude]
        discrete_compensate(coef)
        if phase:
            assert len(amplitude) == 4
        coef += [p*self.max_val*2 for p in phase]
        data = self.pack([0, 1, 2, 2, 0, 1, 1], coef)
        self.line(typ=1, data=data, **kwargs)


class Channel:
    """PDQ Channel.

    Attributes:
        num_frames (int): Number of frames supported.
        max_data (int): Number of 16 bit data words per channel.
        segments (list[Segment]): Segments added to this channel.
    """
    def __init__(self, max_data, num_frames):
        self.max_data = max_data
        self.num_frames = num_frames
        self.segments = []

    def clear(self):
        """Remove all segments."""
        self.segments.clear()

    def new_segment(self):
        """Create and attach a new :class:`Segment` to this channel.

        Returns:
            :class:`Segment`
        """
        segment = Segment()
        self.segments.append(segment)
        return segment

    def place(self):
        """Place segments contiguously.

        Assign segment start addresses and determine length of data.

        Returns:
            addr (int): Amount of memory in use on this channel.
        """
        addr = self.num_frames
        for segment in self.segments:
            segment.addr = addr
            addr += len(segment.data)//2
        assert addr <= self.max_data, addr
        return addr

    def table(self, entry=None):
        """Generate the frame address table.

        Unused frame indices are assigned the zero address in the frame address
        table.
        This will cause the memory parser to remain in the frame address table
        until another frame is selected.

        The frame entry segments can be any segments in the channel.

        Args:
            entry (list[Segment]): List of initial segments for each frame.
                If not specified, the first :attr:`num_frames` segments are
                used as frame entry points.

        Returns:
            table (bytes): Frame address table.
        """
        table = [0] * self.num_frames
        if entry is None:
            entry = self.segments
        for i, frame in enumerate(entry):
            if frame is not None:
                table[i] = frame.addr
        return struct.pack("<" + "H"*self.num_frames, *table)

    def serialize(self, entry=None):
        """Serialize the memory for this channel.

        Places the segments contiguously in memory after the frame table.
        Allocates and assigns segment and frame table addresses.
        Serializes segment data and prepends frame address table.

        Args:
            entry (list[Segment]): See :meth:`table`.

        Returns:
            data (bytes): Channel memory data.
        """
        self.place()
        data = b"".join([segment.data for segment in self.segments])
        return self.table(entry) + data


@portable
def PDQ_CMD(board, is_mem, adr, we):
    """Pack PDQ command fields into command byte.

    :param board: Board address, 0 to 15, with ``15 = 0xf`` denoting broadcast
        to all boards connected.
    :param is_mem: If ``1``, ``adr`` denote the address of the memory to access
        (0 to 2). Otherwise ``adr`` denotes the register to access.
    :param adr: Address of the register or memory to access.
        (``PDQ_ADR_CONFIG``, ``PDQ_ADR_FRAME``, ``PDQ_ADR_CRC``).
    :param we: If ``1`` then write, otherwise read.
    """
    return (adr << 0) | (is_mem << 2) | (board << 3) | (we << 7)


PDQ_ADR_CONFIG = 0
PDQ_ADR_CRC = 1
PDQ_ADR_FRAME = 2


class PDQBase:
    """
    PDQ stack.

    Attributes:
        checksum (int): Running checksum of data written.
        num_channels (int): Number of channels in this stack.
        num_boards (int): Number of boards in this stack.
        num_dacs (int): Number of DAC outputs per board.
        num_frames (int): Number of frames supported.
        channels (list[Channel]): List of :class:`Channel` in this stack.
    """
    freq = 50e6

    _mem_sizes = [None, (20,), (10, 10), (8, 6, 6)]  # 10kx16 units

    def __init__(self, num_boards=3, num_dacs=3, num_frames=32):
        """Initialize PDQ stack.

        Args:
            num_boards (int): Number of boards in this stack.
            num_dacs (int): Number of DAC outputs per board.
            num_frames (int): Number of frames supported.
        """
        self.checksum = 0
        self.num_boards = num_boards
        self.num_dacs = num_dacs
        self.num_frames = num_frames
        self.num_channels = self.num_dacs * self.num_boards
        m = self._mem_sizes[num_dacs]
        self.channels = [Channel(m[j] << 11, num_frames)
                         for i in range(num_boards)
                         for j in range(num_dacs)]

    @portable
    def get_num_boards(self):
        return self.num_boards

    @portable
    def get_num_channels(self):
        return self.num_channels

    @portable
    def get_num_frames(self):
        return self.num_frames

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = float(freq)

    @portable
    def write_reg(self, adr, data, board):
        raise NotImplementedError

    @portable
    def read_reg(self, adr, board):
        raise NotImplementedError

    @portable
    def write_mem(self, mem, adr, data, board=0xf):
        raise NotImplementedError

    @portable
    def read_mem(self, mem, adr, data, board=0xf, buffer=8):
        raise NotImplementedError

    @portable
    def write_config(self, reset=0, clk2x=0, enable=1,
                     trigger=0, aux_miso=0, aux_dac=0b111, board=0xf):
        """Set the configuration register.

        Args:
            reset (bool): Reset the board. Memory is not reset. Self-clearing.
            clk2x (bool): Enable the clock multiplier (100 MHz instead of 50
                MHz)
            enable (bool): Enable the reading and execution of waveform data
                from memory.
            trigger (bool): Soft trigger. Logical or with the ``F1 TTL Input``
                hardware trigger.
            aux_miso (bool): Drive SPI MISO on the AUX/``F5 OUT`` TTL port of
                each board. If ``False``/``0``, drive the masked logical OR of
                the DAC channels' aux data.
            aux_dac (int): DAC channel mask for AUX/F5. Each bit represents
                one channel. AUX/F5 is: ``aux_miso ? spi_miso :
                (aux_dac & Cat(_.aux for _ in channels) != 0)``
            board (int): Board to write to (0-0xe), 0xf for all boards.
        """
        config = ((reset << 0) | (clk2x << 1) | (enable << 2) |
                  (trigger << 3) | (aux_miso << 4) | (aux_dac << 5))
        self.write_reg(PDQ_ADR_CONFIG, config, board)

    @portable
    def read_config(self, board=0xf):
        """Read configuration register.

        .. seealso: :meth:`write_config`
        """
        return self.read_reg(PDQ_ADR_CONFIG, board)

    @portable
    def write_crc(self, crc=0, board=0xf):
        """Set/reset the checksum register.

        Args:
            crc (int): Checksum value to write.
            board (int): Board to write to (0-0xe), 0xf for all boards.
        """
        self.write_reg(PDQ_ADR_CRC, crc, board)

    @portable
    def read_crc(self, board=0xf):
        """Read checksum register.

        .. seealso:: :meth:`write_crc`
        """
        return self.read_reg(PDQ_ADR_CRC, board)

    @portable
    def write_frame(self, frame, board=0xf):
        """Set the current frame.

        Args:
            frame (int): Frame to select.
            board (int): Board to write to (0-0xe), 0xf for all boards.
        """
        self.write_reg(PDQ_ADR_FRAME, frame, board)

    @portable
    def read_frame(self, board=0xf):
        """Read frame selection register.

        .. seealso:: :meth:`write_frame`
        """
        return self.read_reg(PDQ_ADR_FRAME, board)

    def program_segments(self, segments, data):
        """Append the wavesynth lines to the given segments.

        Args:
            segments (list[Segment]): List of :class:`Segment` to append the
                lines to.
            data (list): List of wavesynth lines.
        """
        for i, line in enumerate(data):
            dac_divider = line.get("dac_divider", 1)
            shift = int(log(dac_divider, 2))
            if 2**shift != dac_divider:
                raise ValueError("only power-of-two dac_dividers supported")
            duration = line["duration"]
            trigger = line.get("trigger", False)
            for segment, data in zip(segments, line["channel_data"]):
                silence = data.pop("silence", False)
                if len(data) != 1:
                    raise ValueError("only one target per channel and line "
                                     "supported")
                for target, target_data in data.items():
                    getattr(segment, target)(
                        shift=shift, duration=duration, trigger=trigger,
                        silence=silence, **target_data)

    def program(self, program, channels=None):
        """Serialize a wavesynth program and write it to the channels
        in the stack.

        The :class:`Channel` targeted are cleared and each frame in the
        wavesynth program is appended to a fresh set of :class:`Segment`
        of the channels. All segments are allocated, the frame address tale
        is generated, the channels are serialized and their memories are
        written.

        Short single-cycle lines are prepended and appended to each frame to
        allow proper write interlocking and to assure that the memory reader
        can be reliably parked in the frame address table.
        The first line of each frame is mandatorily triggered.

        Args:
            program (list): Wavesynth program to serialize.
            channels (list[int]): Channel indices to use. If unspecified, all
                channels are used.
        """
        if channels is None:
            channels = range(self.num_channels)
        chs = [self.channels[i] for i in channels]
        for channel in chs:
            channel.clear()
        for frame in program:
            segments = [c.new_segment() for c in chs]
            self.program_segments(segments, frame)
            # append an empty line to stall the memory reader before jumping
            # through the frame table (`wait` does not prevent reading
            # the next line)
            for segment in segments:
                segment.line(typ=3, data=b"", trigger=True, duration=1, aux=1,
                             jump=True)
        for channel, ch in zip(channels, chs):
            self.write_mem(channel, ch.serialize())

    def ping(self):
        """Ping method returning True. Required for ARTIQ remote
        controller."""
        return True
