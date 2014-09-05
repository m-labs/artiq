from migen.fhdl.std import *
from migen.genlib.record import Record


def create_rbus(fine_ts_bits, pads, output_only_pads):
    rbus = []
    for pad in pads:
        layout = [
            ("o_stb", 1),
            ("o_value", 2)
        ]
        if fine_ts_bits:
            layout.append(("o_fine_ts", fine_ts_bits))
        if pad not in output_only_pads:
            layout += [
                ("oe", 1),
                ("i_stb", 1),
                ("i_value", 1)
            ]
            if fine_ts_bits:
                layout.append(("i_fine_ts", fine_ts_bits))
        rbus.append(Record(layout))
    return rbus


def get_fine_ts_width(rbus):
    if hasattr(rbus[0], "o_fine_ts"):
        return flen(rbus[0].o_fine_ts)
    else:
        return 0
