from artiq.language.core import kernel, portable, delay
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.units import us
from artiq.language.types import TInt32, TList, TFloat


PHASER_ADDR_BOARD_ID = 0x00
PHASER_BOARD_ID = 19

class Phaser:
    kernel_invariants = {"core", "channel_base"}

    def __init__(self, dmgr, channel_base, readback_delay=1,
                 core_device="core"):
        self.channel_base = channel_base << 8
        self.core = dmgr.get(core_device)
        self.readback_delay = readback_delay

    @kernel
    def init(self):
        board_id = self.read(PHASER_ADDR_BOARD_ID)
        if board_id != PHASER_BOARD_ID:
            raise ValueError("invalid board id")

    @kernel
    def write(self, addr, data):
        """Write data to a Fastino register.

        :param addr: Address to write to.
        :param data: Data to write.
        """
        rtio_output(self.channel_base | addr | 0x80, data)

    @kernel
    def read(self, addr):
        """Read from Fastino register.

        TODO: untested

        :param addr: Address to read from.
        :return: The data read.
        """
        rtio_output(self.channel_base | addr, 0)
        response = rtio_input_data(self.channel_base >> 8)
        return response >> self.readback_delay
