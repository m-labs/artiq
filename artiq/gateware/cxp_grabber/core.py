from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from misoc.interconnect.csr import *
from misoc.interconnect.stream import Buffer, SyncFIFO
from misoc.cores.coaxpress.common import char_width, word_layout_dchar, word_width
from misoc.cores.coaxpress.core import HostTXCore, HostRXCore
from misoc.cores.coaxpress.core.packet import StreamPacketArbiter
from misoc.cores.coaxpress.core.crc import CXPCRC32Checker

from artiq.gateware.cxp_grabber.frame import (
    EndOfLineMarker,
    FrameHeaderReader,
    PixelParser,
    pixelword_layout,
)

from operator import or_, add


class CXPHostCore(Module, AutoCSR):
    def __init__(self, tx_phy, rx_phy, clk_freq, command_buffer_depth=32, nrxslot=4):
        # control buffer is only 32 words (128 bytes) wide for compatibility with CXP 1.x compliant devices
        # Section 12.1.6 (CXP-001-2021)
        self.buffer_depth, self.nslots = command_buffer_depth, nrxslot

        self.submodules.tx = HostTXCore(tx_phy, command_buffer_depth, clk_freq, False)
        self.submodules.rx = HostRXCore(rx_phy, command_buffer_depth, nrxslot, False)

    def get_tx_port(self):
        return self.tx.writer.mem.get_port(write_capable=True)

    def get_rx_port(self):
        return self.rx.command_reader.mem.get_port(write_capable=False)

    def get_mem_size(self):
        return word_width * self.buffer_depth * self.nslots // 8


class StreamDecoder(Module, AutoCSR):
    """
    Convert the raw frame data into pixel data

    Currently only support:
    - Pixel format: mono8, mono10, mono12, mono14, mono16
    - Tap geometry: 1X-1Y
    - Scanning mode: area scanning

    """
    def __init__(self, res_width):
        self.crc_error = CSR()
        self.stream_type_error = CSR()

        self.new_frame = CSR()
        self.x_size = CSRStatus(3*char_width)
        self.y_size = CSRStatus(3*char_width)
        self.pixel_format_code = CSRStatus(2*char_width)

        # # #
         
        cdr = ClockDomainsRenamer("cxp_gt_rx")
        # 
        #      32+8(dchar)                                                             32 
        # sink ────/────> stream ────> buffer ────> crc checker ─────> frame header ───/───> end of line ─────> skid buffer ─────> pixel parser ─────> 4x pixel with
        #                 arbiter                   reader             reader                marker                                                    xy coordinate
        # 
         
        
        # Drops the packet header & K29.7 and mark eop on the crc word
        self.submodules.arbiter = arbiter = cdr(StreamPacketArbiter())
        
        # Buffer to improve timing
        self.submodules.buffer = buffer = cdr(Buffer(word_layout_dchar))

        # CRC 
        self.submodules.crc_checker = crc_checker = cdr(CXPCRC32Checker())
        self.submodules.crc_error_ps = crc_error_ps = PulseSynchronizer("cxp_gt_rx", "sys")
        self.sync.cxp_gt_rx += crc_error_ps.i.eq(crc_checker.error)
        self.sync += [
            If(crc_error_ps.o,
                self.crc_error.w.eq(1),
            ).Elif(self.crc_error.re,
                self.crc_error.w.eq(0),
            ),
        ]

        # Frame header extraction
        self.submodules.header_reader = header_reader = cdr(FrameHeaderReader())
        # New frame and stream type error notification
        self.submodules.new_frame_ps = new_frame_ps = PulseSynchronizer("cxp_gt_rx", "sys")
        self.submodules.stream_type_err_ps = stream_type_err_ps = PulseSynchronizer("cxp_gt_rx", "sys")
        self.sync.cxp_gt_rx += [
            new_frame_ps.i.eq(header_reader.new_frame),
            stream_type_err_ps.i.eq(header_reader.decode_err),
        ]
        self.sync += [
            If(new_frame_ps.o,
                self.new_frame.w.eq(1),
            ).Elif(self.new_frame.re,
                self.new_frame.w.eq(0),
            ),
            If(stream_type_err_ps.o,
                self.stream_type_error.w.eq(1),
            ).Elif(self.stream_type_error.re,
                self.stream_type_error.w.eq(0),
            )
        ]

        frame_header = header_reader.header
        self.specials += [
            MultiReg(frame_header.Xsize, self.x_size.status),
            MultiReg(frame_header.Ysize, self.y_size.status),
            MultiReg(frame_header.PixelF, self.pixel_format_code.status),
        ]


        # Mark end of line for pixel parser
        self.submodules.eol_marker = eol_marker = cdr(EndOfLineMarker())
        self.sync.cxp_gt_rx += eol_marker.words_per_img_line.eq(frame_header.DsizeL)

        # Skid buffer to prevent pipeline stalling
        # At each linebreak, `Pixel_Parser.sink.ack` will fall for 1-2 cycle.
        # Without the skid buffer , the whole pipleline will stall during that 1-2 cycle.
        # 
        # Due to the backpressure, 2 words line marker (4x K28.3 + 4x 0x02) will arrive as the linebreak indicator and will be consumed by `frame_header_reader`
        # Thus, the buffer won't experience any data buildup.
        self.submodules.skid_buf = skid_buf = cdr(SyncFIFO(pixelword_layout, 2))

        self.submodules.parser = parser = cdr(PixelParser(res_width))
        self.sync.cxp_gt_rx += [
            parser.x_size.eq(frame_header.Xsize),
            parser.y_size.eq(frame_header.Ysize),
            parser.pixel_format_code.eq(frame_header.PixelF),
        ]

        # Connecting the pipeline
        self.sink = arbiter.sink
        self.comb += arbiter.sources[0].connect(buffer.sink)
        self.pipeline = [buffer, crc_checker, header_reader, eol_marker, skid_buf, parser]
        for s, d in zip(self.pipeline, self.pipeline[1:]):
            self.comb += s.source.connect(d.sink)
        

        # For downstream ROI engine
        self.source_pixel4x = parser.source_pixel4x


class ROI(Module):
    """
    ROI Engine that accept 4 pixels each cycle. For each frame, accumulates pixels values within a
    rectangular region of interest, and reports the total.
    """
    def __init__(self, pixel_4x, count_width):
        assert len(pixel_4x) == 4

        self.cfg = Record([
            ("x0", len(pixel_4x[0].x)),
            ("y0", len(pixel_4x[0].y)),
            ("x1", len(pixel_4x[0].x)),
            ("y1", len(pixel_4x[0].y)),
        ])

        self.out = Record([
            ("update", 1),
            # registered output - can be used as CDC input
            ("count", count_width),
        ])

        # # #

        roi_4x = [
            Record([
                ("x_good", 1),
                ("y_good", 1),
                ("gray", len(pixel_4x[0].gray)),
                ("stb", 1),
                ("count", count_width),
            ]) for _ in range(4)
            
        ]

        for pix, roi in zip(pixel_4x, roi_4x):
            self.sync += [
                # stage 1 - generate "good" (in-ROI) signals
                roi.x_good.eq(0),
                If((self.cfg.x0 <= pix.x) & (pix.x < self.cfg.x1),
                    roi.x_good.eq(1)
                ),

                # the 4 pixels are on the same y level, no need for extra calculation
                If(pix.y == self.cfg.y0,
                    roi.y_good.eq(1)
                ),
                If(pix.y == self.cfg.y1,
                    roi.y_good.eq(0)
                ),
                If(pix.eof,
                    roi.x_good.eq(0),
                    roi.y_good.eq(0)
                ),
                roi.gray.eq(pix.gray),
                roi.stb.eq(pix.stb),

                # stage 2 - accumulate
                If((roi.stb & roi.x_good & roi.y_good),
                    roi.count.eq(roi.count + roi.gray)
                )
            ]

        eof = Signal()
        eof_buf = Signal()
        count_buf = [Signal(count_width), Signal(count_width)]
        
        # stage 3 - update
        self.sync += [
            eof.eq(reduce(or_, [pix.eof for pix in pixel_4x])),
            eof_buf.eq(eof),
            count_buf[0].eq(roi_4x[0].count + roi_4x[1].count),
            count_buf[1].eq(roi_4x[2].count + roi_4x[3].count),

            self.out.update.eq(0),
            If(eof_buf,
                [roi.count.eq(0) for roi in roi_4x],
                self.out.update.eq(1),
                self.out.count.eq(reduce(add, count_buf))
            ),
        ]
