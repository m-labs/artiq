from artiq.language.core import nac3


@nac3
class RTIOUnderflow(Exception):
    # NAC3TODO """Raised when the CPU or DMA core fails to submit a RTIO event early
    # enough (with respect to the event's timestamp).

    # The offending event is discarded and the RTIO core keeps operating.
    # """
    pass


@nac3
class RTIOOverflow(Exception):
    # NAC3TODO """Raised when at least one event could not be registered into the RTIO
    # input FIFO because it was full (CPU not reading fast enough).

    # This does not interrupt operations further than cancelling the current
    # read attempt and discarding some events. Reading can be reattempted after
    # the exception is caught, and events will be partially retrieved.
    # """
    pass


@nac3
class RTIODestinationUnreachable(Exception):
    # NAC3TODO """Raised with a RTIO operation could not be completed due to a DRTIO link
    # being down.
    # """
    pass


@nac3
class CacheError(Exception):
    # NAC3TODO """Raised when putting a value into a cache row would violate memory safety."""
    pass


@nac3
class DMAError(Exception):
    # NAC3TODO """Raised when performing an invalid DMA operation."""
    pass


@nac3
class ClockFailure(Exception):
    # NAC3TODO """Raised when RTIO PLL has lost lock."""
    pass


@nac3
class I2CError(Exception):
    # NAC3TODO """Raised when a I2C transaction fails."""
    pass


@nac3
class SPIError(Exception):
    # NAC3TODO """Raised when a SPI transaction fails."""
    pass
