from migen import *

from artiq.gateware.rtio import rtlink


def fifo_payload(channels):
    address_width = max(rtlink.get_address_width(channel.interface.o)
                        for channel in channels)
    data_width = max(rtlink.get_data_width(channel.interface.o)
                     for channel in channels)

    layout = [
        ("channel", bits_for(len(channels)-1)),
        ("timestamp", 64)
    ]
    if address_width:
        layout.append(("address", address_width))
    if data_width:
        layout.append(("data", data_width))

    return layout


def seqn_width(lane_count, fifo_depth):
    # There must be a unique sequence number for every possible event in every FIFO.
    # Plus 2 bits to detect and handle wraparounds.
    return bits_for(lane_count*fifo_depth-1) + 2


def fifo_ingress(seqn_width, layout_payload):
    return [
        ("we", 1, DIR_M_TO_S),
        ("writable", 1, DIR_S_TO_M),
        ("seqn", seqn_width, DIR_M_TO_S),
        ("payload", [(a, b, DIR_M_TO_S) for a, b in layout_payload])
    ]


def fifo_egress(seqn_width, layout_payload):
    return [
        ("re", 1, DIR_S_TO_M),
        ("readable", 1, DIR_M_TO_S),
        ("seqn", seqn_width, DIR_M_TO_S),
        ("payload", [(a, b, DIR_M_TO_S) for a, b in layout_payload])
    ]


# We use glbl_fine_ts_width in the output network so that collisions due
# to insufficiently increasing timestamps are always reliably detected.
# We can still have undetected collisions on the address by making it wrap
# around, but those are more rare and easier to debug, and addresses are
# not normally exposed directly to the ARTIQ user.
def output_network_payload(channels, glbl_fine_ts_width):
    address_width = max(rtlink.get_address_width(channel.interface.o)
                        for channel in channels)
    data_width = max(rtlink.get_data_width(channel.interface.o)
                     for channel in channels)

    layout = [("channel", bits_for(len(channels)-1))]
    if glbl_fine_ts_width:
        layout.append(("fine_ts", glbl_fine_ts_width))
    if address_width:
        layout.append(("address", address_width))
    if data_width:
        layout.append(("data", data_width))

    return layout


def output_network_node(seqn_width, layout_payload):
    return [
        ("valid", 1),
        ("seqn", seqn_width),
        ("replace_occured", 1),
        ("nondata_replace_occured", 1),
        ("payload", layout_payload)
    ]
