"""
Driver for generic SPI on RTIO.

This ARTIQ coredevice driver corresponds to the "new" MiSoC SPI core (v2).

Output event replacement is not supported and issuing commands at the same
time is an error.
"""

from artiq.language.core import syscall, kernel, portable, delay_mu
from artiq.language.types import TInt32, TNone
from artiq.coredevice.rtio import rtio_output, rtio_input_data


__all__ = [
    "SPI_DATA_ADDR", "SPI_CONFIG_ADDR",
    "SPI_OFFLINE", "SPI_END", "SPI_INPUT",
    "SPI_CS_POLARITY", "SPI_CLK_POLARITY", "SPI_CLK_PHASE",
    "SPI_LSB_FIRST", "SPI_HALF_DUPLEX",
    "SPIMaster", "NRTSPIMaster"
]

SPI_DATA_ADDR = 0
SPI_CONFIG_ADDR = 1

SPI_OFFLINE = 0x01
SPI_END = 0x02
SPI_INPUT = 0x04
SPI_CS_POLARITY = 0x08
SPI_CLK_POLARITY = 0x10
SPI_CLK_PHASE = 0x20
SPI_LSB_FIRST = 0x40
SPI_HALF_DUPLEX = 0x80


class SPIMaster:
    """Core device Serial Peripheral Interface (SPI) bus master.

    Owns one SPI bus.

    This ARTIQ coredevice driver corresponds to the "new" MiSoC SPI core (v2).

    **Transfer Sequence**:

    * If necessary, set the ``config`` register (:meth:`set_config` and
      :meth:`set_config_mu`) to activate and configure the core and to set
      various transfer parameters like transfer length, clock divider,
      and chip selects.
    * :meth:`write` to the ``data`` register. Writing starts the transfer.
    * If the transfer included submitting the SPI input data as an RTIO input
      event (``SPI_INPUT`` set), then :meth:`read` the ``data``.
    * If ``SPI_END`` was not set, repeat the transfer sequence.

    A **transaction** consists of one or more **transfers**. The chip select
    pattern is asserted for the entire length of the transaction. All but the
    last transfer are submitted with ``SPI_END`` cleared in the configuration
    register.

    :param channel: RTIO channel number of the SPI bus to control.
    :param div: Initial CLK divider, see also: :meth:`update_xfer_duration_mu`
    :param length: Initial transfer length, see also:
        :meth:`update_xfer_duration_mu`
    :param core_device: Core device name
    """
    kernel_invariants = {"core", "ref_period_mu", "channel"}

    def __init__(self, dmgr, channel, div=0, length=0, core_device="core"):
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
                self.core.coarse_ref_period)
        assert self.ref_period_mu == self.core.ref_multiplier
        self.channel = channel
        self.update_xfer_duration_mu(div, length)

    @portable
    def frequency_to_div(self, f):
        """Convert a SPI clock frequency to the closest SPI clock divider."""
        return int(round(1/(f*self.core.mu_to_seconds(self.ref_period_mu))))

    @kernel
    def set_config(self, flags, length, freq, cs):
        """Set the configuration register.

        * If ``SPI_CS_POLARITY`` is cleared (``cs`` active low, the default),
          "``cs`` all deasserted" means "all ``cs_n`` bits high".
        * ``cs_n`` is not mandatory in the pads supplied to the gateware core.
          Framing and chip selection can also be handled independently
          through other means, e.g. ``TTLOut``.
        * If there is a ``miso`` wire in the pads supplied in the gateware,
          input and output may be two signals ("4-wire SPI"),
          otherwise ``mosi`` must be used for both output and input
          ("3-wire SPI") and ``SPI_HALF_DUPLEX`` must to be set
          when reading data or when the slave drives the
          ``mosi`` signal at any point.
        * The first bit output on ``mosi`` is always the MSB/LSB (depending
          on ``SPI_LSB_FIRST``) of the ``data`` written, independent of
          the ``length`` of the transfer. The last bit input from ``miso``
          always ends up in the LSB/MSB (respectively) of the ``data`` read,
          independent of the ``length`` of the transfer.
        * ``cs`` is asserted at the beginning and deasserted at the end
          of the transaction.
        * ``cs`` handling is agnostic to whether it is one-hot or decoded
          somewhere downstream. If it is decoded, "``cs`` all deasserted"
          should be handled accordingly (no slave selected).
          If it is one-hot, asserting multiple slaves should only be attempted
          if ``miso`` is either not connected between slaves, or open
          collector, or correctly multiplexed externally.
        * Changes to the configuration register take effect on the start of the
          next transfer with the exception of ``SPI_OFFLINE`` which takes
          effect immediately.
        * The SPI core can only be written to when it is idle or waiting
          for the next transfer data. Writing (:meth:`set_config`,
          :meth:`set_config_mu` or :meth:`write`)
          when the core is busy will result in an RTIO busy error being logged.

        This method advances the timeline by one coarse RTIO clock cycle.

        **Configuration flags**:

        * :const:`SPI_OFFLINE`: all pins high-z (reset=1)
        * :const:`SPI_END`: transfer in progress (reset=1)
        * :const:`SPI_INPUT`: submit SPI read data as RTIO input event when
          transfer is complete (reset=0)
        * :const:`SPI_CS_POLARITY`: active level of ``cs_n`` (reset=0)
        * :const:`SPI_CLK_POLARITY`: idle level of ``clk`` (reset=0)
        * :const:`SPI_CLK_PHASE`: first edge after ``cs`` assertion to sample
          data on (reset=0). In Motorola/Freescale SPI language
          (:const:`SPI_CLK_POLARITY`, :const:`SPI_CLK_PHASE`) == (CPOL, CPHA):

          - (0, 0): idle low, output on falling, input on rising
          - (0, 1): idle low, output on rising, input on falling
          - (1, 0): idle high, output on rising, input on falling
          - (1, 1): idle high, output on falling, input on rising
        * :const:`SPI_LSB_FIRST`: LSB is the first bit on the wire (reset=0)
        * :const:`SPI_HALF_DUPLEX`: 3-wire SPI, in/out on ``mosi`` (reset=0)

        :param flags: A bit map of `SPI_*` flags.
        :param length: Number of bits to write during the next transfer.
            (reset=1)
        :param freq: Desired SPI clock frequency. (reset=f_rtio/2)
        :param cs: Bit pattern of chip selects to assert.
            Or number of the chip select to assert if ``cs`` is decoded
            downstream. (reset=0)
        """
        self.set_config_mu(flags, length, self.frequency_to_div(freq), cs)

    @kernel
    def set_config_mu(self, flags, length, div, cs):
        """Set the ``config`` register (in SPI bus machine units).

        .. seealso:: :meth:`set_config`

        :param flags: A bit map of `SPI_*` flags.
        :param length: Number of bits to write during the next transfer.
            (reset=1)
        :param div: Counter load value to divide the RTIO
          clock by to generate the SPI clock. (minimum=2, reset=2)
          ``f_rtio_clk/f_spi == div``. If ``div`` is odd,
          the setup phase of the SPI clock is one coarse RTIO clock cycle
          longer than the hold phase.
        :param cs: Bit pattern of chip selects to assert.
            Or number of the chip select to assert if ``cs`` is decoded
            downstream. (reset=0)
        """
        if length > 32 or length < 1:
            raise ValueError("Invalid SPI transfer length")
        if div > 257 or div < 2:
            raise ValueError("Invalid SPI clock divider")
        rtio_output((self.channel << 8) | SPI_CONFIG_ADDR, flags |
                ((length - 1) << 8) | ((div - 2) << 16) | (cs << 24))
        self.update_xfer_duration_mu(div, length)
        delay_mu(self.ref_period_mu)

    @portable
    def update_xfer_duration_mu(self, div, length):
        """Calculate and set the transfer duration.

        This method updates the SPI transfer duration which is used
        in :meth:`write` to advance the timeline.

        Use this method (and avoid having to call :meth:`set_config_mu`)
        when the divider and transfer length have been configured
        (using :meth:`set_config` or :meth:`set_config_mu`) by previous
        experiments and are known.

        This method is portable and can also be called from e.g.
        :meth:`__init__`.

        .. warning:: If this method is called while recording a DMA
           sequence, the playback of the sequence will not update the
           driver state.
           When required, update the driver state manually (by calling
           this method) after playing back a DMA sequence.

        :param div: SPI clock divider (see: :meth:`set_config_mu`)
        :param length: SPI transfer length (see: :meth:`set_config_mu`)
        """
        self.xfer_duration_mu = ((length + 1)*div + 1)*self.ref_period_mu

    @kernel
    def write(self, data):
        """Write SPI data to shift register register and start transfer.

        * The ``data`` register and the shift register are 32 bits wide.
        * Data writes take one ``ref_period`` cycle.
        * A transaction consisting of a single transfer (``SPI_END``) takes
          :attr:`xfer_duration_mu` ``=(n + 1)*div`` cycles RTIO time where
          ``n`` is the number of bits and ``div`` is the SPI clock divider.
        * Transfers in a multi-transfer transaction take up to one SPI clock
          cycle less time depending on multiple parameters. Advanced users may
          rewind the timeline appropriately to achieve faster multi-transfer
          transactions.
        * The SPI core will be busy for the duration of the SPI transfer.
        * For bit alignment and bit ordering see :meth:`set_config`.
        * The SPI core can only be written to when it is idle or waiting
          for the next transfer data. Writing (:meth:`set_config`,
          :meth:`set_config_mu` or :meth:`write`)
          when the core is busy will result in an RTIO busy error being logged.

        This method advances the timeline by the duration of one
        single-transfer SPI transaction (:attr:`xfer_duration_mu`).

        :param data: SPI output data to be written.
        """
        rtio_output((self.channel << 8) | SPI_DATA_ADDR, data)
        delay_mu(self.xfer_duration_mu)

    @kernel
    def read(self):
        """Read SPI data submitted by the SPI core.

        For bit alignment and bit ordering see :meth:`set_config`.

        This method does not alter the timeline.

        :return: SPI input data.
        """
        return rtio_input_data(self.channel)


@syscall(flags={"nounwind", "nowrite"})
def spi_set_config(busno: TInt32, flags: TInt32, length: TInt32, div: TInt32, cs: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def spi_write(busno: TInt32, data: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def spi_read(busno: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")


class NRTSPIMaster:
    """Core device non-realtime Serial Peripheral Interface (SPI) bus master.
    Owns one non-realtime SPI bus.

    With this driver, SPI transactions and are performed by the CPU without
    involving RTIO.

    Realtime and non-realtime buses are separate and defined at bitstream
    compilation time.

    See :class:`SPIMaster` for a description of the methods.
    """
    def __init__(self, dmgr, busno=0, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno

    @kernel
    def set_config_mu(self, flags=0, length=8, div=6, cs=1):
        """Set the ``config`` register.

        Note that the non-realtime SPI cores are usually clocked by the system
        clock and not the RTIO clock. In many cases, the SPI configuration is
        already set by the firmware and you do not need to call this method.
        """
        spi_set_config(self.busno, flags, length, div, cs)

    @kernel
    def write(self, data=0):
        spi_write(self.busno, data)

    @kernel
    def read(self):
        return spi_read(self.busno)
