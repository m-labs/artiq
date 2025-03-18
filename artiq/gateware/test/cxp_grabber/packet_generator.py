from migen import *
from misoc.cores.coaxpress.common import char_width, KCode, word_width

from math import ceil
from collections import namedtuple

_WORDLAYOUT = namedtuple("WordLayout", ["data", "k", "stb", "eop"])


def _switch_bit_order(s, width):
    bits = "{:0{width}b}".format(s, width=width)
    return int(bits[::-1], 2)


def MonoPixelPacketGenerator(
    x_size,
    y_size,
    pixel_width,
    with_eol_marked=False,
    stb_line_marker=False,
):
    words_per_image_line = ceil(x_size * pixel_width / word_width)
    packet = []
    for _ in range(y_size):
        packed = 0
        for x in range(x_size):
            # full white pixel
            gray = (2**pixel_width) - 1
            packed += _switch_bit_order(gray, pixel_width) << x * pixel_width

        # Line marker
        packet += [
            _WORDLAYOUT(
                data=Replicate(KCode["stream_marker"], 4),
                k=Replicate(1, 4),
                stb=1 if stb_line_marker else 0,
                eop=0,
            ),
            _WORDLAYOUT(
                data=Replicate(C(0x02, char_width), 4),
                k=Replicate(0, 4),
                stb=1 if stb_line_marker else 0,
                eop=0,
            ),
        ]

        for i in range(words_per_image_line):
            serialized = (packed & (0xFFFF_FFFF << i * word_width)) >> i * word_width
            word = []
            for j in range(4):
                word += [C(_switch_bit_order((serialized >> 8 * j) & 0xFF, 8), 8)]

            eop = 1 if ((i == words_per_image_line - 1) and with_eol_marked) else 0
            packet.append(
                _WORDLAYOUT(data=Cat(word), k=Replicate(0, 4), stb=1, eop=eop),
            )

    return packet
