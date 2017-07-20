"""
Driver for generic SPI on RTIO.

Output event replacement is not supported and issuing commands at the same
time is an error.
"""


import numpy

from artiq.language.core import syscall, kernel, portable, now_mu, delay_mu
from artiq.language.types import TInt32, TNone
from artiq.language.units import MHz
from artiq.coredevice.rtio import rtio_output, rtio_input_data


__all__ = [
   "SPI_DATA_ADDR", "SPI_XFER_ADDR", "SPI_CONFIG_ADDR",
    "SPI_OFFLINE", "SPI_ACTIVE", "SPI_PENDING",
    "SPI_CS_POLARITY", "SPI_CLK_POLARITY", "SPI_CLK_PHASE",
    "SPI_LSB_FIRST", "SPI_HALF_DUPLEX",
    "SPIMaster", "NRTSPIMaster"
]


SPI_DATA_ADDR, SPI_XFER_ADDR, SPI_CONFIG_ADDR = range(3)
(
    SPI_OFFLINE,
    SPI_ACTIVE,
    SPI_PENDING,
    SPI_CS_POLARITY,
    SPI_CLK_POLARITY,
    SPI_CLK_PHASE,
    SPI_LSB_FIRST,
    SPI_HALF_DUPLEX,
) = (1 << i for i in range(8))

SPI_RT2WB_READ = 1 << 2


class SPIMaster:
    """Core device Serial Peripheral Interface (SPI) bus master.
    Owns one SPI bus.

    **Transfer Sequence**:

    * If desired, write the ``config`` register (:meth:`set_config`)
      to configure and activate the core.
    * If desired, write the ``xfer`` register (:meth:`set_xfer`)
      to set ``cs_n``, ``write_length``, and ``read_length``.
    * :meth:`write` to the ``data`` register (also for transfers with
      zero bits to be written). Writing starts the transfer.
    * If desired, :meth:`read_sync` (or :meth:`read_async` followed by a
      :meth:`input_async` later) the ``data`` register corresponding to
      the last completed transfer.
    * If desired, :meth:`set_xfer` for the next transfer.
    * If desired, :meth:`write` ``data`` queuing the next
      (possibly chained) transfer.

    **Notes**:

    * In order to chain a transfer onto an in-flight transfer without
      deasserting ``cs`` in between, the second :meth:`write` needs to
      happen strictly later than ``2*ref_period_mu`` (two coarse RTIO
      cycles) but strictly earlier than ``xfer_period_mu + write_period_mu``
      after the first. Note that :meth:`write` already applies a delay of
      ``xfer_period_mu + write_period_mu``.
    * A full transfer takes ``write_period_mu + xfer_period_mu``.
    * Chained transfers can happen every ``xfer_period_mu``.
    * Read data is available every ``xfer_period_mu`` starting
      a bit after xfer_period_mu (depending on ``clk_phase``).
    * As a consequence, in order to chain transfers together, new data must
      be written before the pending transfer's read data becomes available.

    :param channel: RTIO channel number of the SPI bus to control.
    """

    kernel_invariants = {"core", "ref_period_mu", "channel"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
                self.core.coarse_ref_period)
        assert self.ref_period_mu == self.core.ref_multiplier
        self.channel = channel
        self.write_period_mu = numpy.int64(0)
        self.read_period_mu = numpy.int64(0)
        self.xfer_period_mu = numpy.int64(0)

    @portable
    def frequency_to_div(self, f):
        return int(1/(f*self.core.mu_to_seconds(self.ref_period_mu))) + 1

    @kernel
    def set_config(self, flags=0, write_freq=20*MHz, read_freq=20*MHz):
        """Set the configuration register.

        * If ``config.cs_polarity`` == 0 (``cs`` active low, the default),
          "``cs_n`` all deasserted" means "all ``cs_n`` bits high".
        * ``cs_n`` is not mandatory in the pads supplied to the gateware core.
          Framing and chip selection can also be handled independently
          through other means, e.g. ``TTLOut``.
        * If there is a ``miso`` wire in the pads supplied in the gateware,
          input and output may be two signals ("4-wire SPI"),
          otherwise ``mosi`` must be used for both output and input
          ("3-wire SPI") and ``config.half_duplex`` must to be set
          when reading data is desired or when the slave drives the
          ``mosi`` signal at any point.
        * The first bit output on ``mosi`` is always the MSB/LSB (depending
          on ``config.lsb_first``) of the ``data`` register, independent of
          ``xfer.write_length``. The last bit input from ``miso`` always ends
          up in the LSB/MSB (respectively) of the ``data`` register,
          independent of ``xfer.read_length``.
        * Writes to the ``config`` register take effect immediately.

        **Configuration flags**:

        * :const:`SPI_OFFLINE`: all pins high-z (reset=1)
        * :const:`SPI_ACTIVE`: transfer in progress (read-only)
        * :const:`SPI_PENDING`: transfer pending in intermediate buffer
          (read-only)
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

        This method advances the timeline by the duration of the
        RTIO-to-Wishbone bus transaction (three RTIO clock cycles).

        :param flags: A bit map of `SPI_*` flags.
        :param write_freq: Desired SPI clock frequency during write bits.
        :param read_freq: Desired SPI clock frequency during read bits.
        """
        self.set_config_mu(flags, self.frequency_to_div(write_freq),
                           self.frequency_to_div(read_freq))

    @kernel
    def set_config_mu(self, flags=0, write_div=6, read_div=6):
        """Set the ``config`` register (in SPI bus machine units).

        .. seealso:: :meth:`set_config`

        :param write_div: Counter load value to divide the RTIO
          clock by to generate the SPI write clk. (minimum=2, reset=2)
          ``f_rtio_clk/f_spi_write == write_div``. If ``write_div`` is odd,
          the setup phase of the SPI clock is biased to longer lengths
          by one RTIO clock cycle.
        :param read_div: Ditto for the read clock.
        """
        rtio_output(now_mu(), self.channel, SPI_CONFIG_ADDR, flags |
                    ((write_div - 2) << 16) | ((read_div - 2) << 24))
        self.write_period_mu = int(write_div*self.ref_period_mu)
        self.read_period_mu = int(read_div*self.ref_period_mu)
        delay_mu(3*self.ref_period_mu)

    @kernel
    def set_xfer(self, chip_select=0, write_length=0, read_length=0):
        """Set the ``xfer`` register.

        * Every transfer consists of a write of ``write_length`` bits
          immediately followed by a read of ``read_length`` bits.
        * ``cs_n`` is asserted at the beginning and deasserted at the end
          of the transfer if there is no other transfer pending.
        * ``cs_n`` handling is agnostic to whether it is one-hot or decoded
          somewhere downstream. If it is decoded, "``cs_n`` all deasserted"
          should be handled accordingly (no slave selected).
          If it is one-hot, asserting multiple slaves should only be attempted
          if ``miso`` is either not connected between slaves, or open
          collector, or correctly multiplexed externally.
        * For 4-wire SPI only the sum of ``read_length`` and ``write_length``
          matters. The behavior is the same (except for clock speeds) no matter
          how the total transfer length is divided between the two. For
          3-wire SPI, the direction of ``mosi`` is switched from output to
          input after ``write_length`` bits.
        * Data output on ``mosi`` in 4-wire SPI during the read cycles is what
          is found in the data register at the time.
          Data in the ``data`` register outside the least/most (depending
          on ``config.lsb_first``) significant ``read_length`` bits is what is
          seen on ``miso`` (or ``mosi`` if ``config.half_duplex``)
          during the write cycles.
        * Writes to ``xfer`` are synchronized to the start of the next
          (possibly chained) transfer.

        This method advances the timeline by the duration of the
        RTIO-to-Wishbone bus transaction (three RTIO clock cycles).

        :param chip_select: Bit mask of chip selects to assert. Or number of
            the chip select to assert if ``cs`` is decoded downstream.
            (reset=0)
        :param write_length: Number of bits to write during the next transfer.
            (reset=0)
        :param read_length: Number of bits to read during the next transfer.
            (reset=0)
        """
        rtio_output(now_mu(), self.channel, SPI_XFER_ADDR,
                    chip_select | (write_length << 16) | (read_length << 24))
        self.xfer_period_mu = int(write_length*self.write_period_mu +
                                  read_length*self.read_period_mu)
        delay_mu(3*self.ref_period_mu)

    @kernel
    def write(self, data=0):
        """Write data to data register.

        * The ``data`` register and the shift register are 32 bits wide.
          If there are no writes to the register, ``miso`` data reappears on
          ``mosi`` after 32 cycles.
        * A wishbone data register write is acknowledged when the
          transfer has been written to the intermediate buffer.
          It will be started when there are no other transactions being
          executed, either beginning a new SPI transfer of chained
          to an in-flight transfer.
        * Writes take three ``ref_period`` cycles unless another
          chained transfer is pending and the transfer being
          executed is not complete.
        * The SPI ``data`` register is double-buffered: Once a transfer has
          started, new write data can be written, queuing a new transfer.
          Transfers submitted this way are chained and executed without
          deasserting ``cs`` in between. Once a transfer completes,
          the previous transfer's read data is available in the
          ``data`` register.
        * For bit alignment and bit ordering see :meth:`set_config`.

        This method advances the timeline by the duration of the SPI transfer.
        If a transfer is to be chained, the timeline needs to be rewound.
        """
        rtio_output(now_mu(), self.channel, SPI_DATA_ADDR, data)
        delay_mu(self.xfer_period_mu + self.write_period_mu)

    @kernel
    def read_async(self):
        """Trigger an asynchronous read from the ``data`` register.

        For bit alignment and bit ordering see :meth:`set_config`.

        Reads always finish in two cycles.

        Every data register read triggered by a :meth:`read_async`
        must be matched by a :meth:`input_async` to retrieve the data.

        This method advances the timeline by the duration of the
        RTIO-to-Wishbone bus transaction (three RTIO clock cycles).
        """
        rtio_output(now_mu(), self.channel, SPI_DATA_ADDR | SPI_RT2WB_READ, 0)
        delay_mu(3*self.ref_period_mu)

    @kernel
    def input_async(self):
        """Retrieves data read asynchronously from the ``data`` register.

        :meth:`input_async` must match a preeeding :meth:`read_async`.
        """
        return rtio_input_data(self.channel)

    @kernel
    def read_sync(self):
        """Read the ``data`` register synchronously.

        This is a shortcut for :meth:`read_async` followed by
        :meth:`input_async`.
        """
        self.read_async()
        return self.input_async()

    @kernel
    def _get_xfer_sync(self):
        rtio_output(now_mu(), self.channel, SPI_XFER_ADDR | SPI_RT2WB_READ, 0)
        return rtio_input_data(self.channel)

    @kernel
    def _get_config_sync(self):
        rtio_output(now_mu(), self.channel, SPI_CONFIG_ADDR | SPI_RT2WB_READ,
                    0)
        return rtio_input_data(self.channel)


@syscall(flags={"nounwind", "nowrite"})
def spi_set_config(busno: TInt32, flags: TInt32, write_div: TInt32, read_div: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def spi_set_xfer(busno: TInt32, chip_select: TInt32, write_length: TInt32, read_length: TInt32) -> TNone:
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
    def set_config_mu(self, flags=0, write_div=6, read_div=6):
        """Set the ``config`` register.

        Note that the non-realtime SPI cores are usually clocked by the system
        clock and not the RTIO clock. In many cases, the SPI configuration is
        already set by the firmware and you do not need to call this method.

        The offline bit cannot be set using this method.
        The SPI bus is briefly taken offline when this method is called.
        """
        spi_set_config(self.busno, flags, write_div, read_div)

    @kernel
    def set_xfer(self, chip_select=0, write_length=0, read_length=0):
        spi_set_xfer(self.busno, chip_select, write_length, read_length)

    @kernel
    def write(self, data=0):
        spi_write(self.busno, data)

    @kernel
    def read(self):
        return spi_read(self.busno)
