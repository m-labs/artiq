import builtins
from numpy.linalg import LinAlgError
from artiq.language.core import nac3, UnwrapNoneError


"""
This file provides class definition for all the exceptions declared in `EmbeddingMap` in `artiq.language.embedding_map`

For Python builtin exceptions, use the `builtins` module
For ARTIQ specific exceptions, inherit from `Exception` class
"""


AssertionError = builtins.AssertionError
AttributeError = builtins.AttributeError
IndexError = builtins.IndexError
IOError = builtins.IOError
KeyError = builtins.KeyError
NotImplementedError = builtins.NotImplementedError
OverflowError = builtins.OverflowError
RuntimeError = builtins.RuntimeError
TimeoutError = builtins.TimeoutError
TypeError = builtins.TypeError
ValueError = builtins.ValueError
ZeroDivisionError = builtins.ZeroDivisionError
OSError = builtins.OSError


@nac3
class RTIOUnderflow(Exception):
    """Raised when the CPU or DMA core fails to submit a RTIO event early
    enough (with respect to the event's timestamp).

    The offending event is discarded and the RTIO core keeps operating.
    """
    artiq_builtin = True


@nac3
class RTIOOverflow(Exception):
    """Raised when at least one event could not be registered into the RTIO
    input FIFO because it was full (CPU not reading fast enough).

    This does not interrupt operations further than cancelling the current
    read attempt and discarding some events. Reading can be reattempted after
    the exception is caught, and events will be partially retrieved.
    """
    artiq_builtin = True


@nac3
class RTIODestinationUnreachable(Exception):
    """Raised when a RTIO operation could not be completed due to a DRTIO link
    being down.
    """
    artiq_builtin = True


@nac3
class CacheError(Exception):
    """Raised when putting a value into a cache row would violate memory safety."""
    artiq_builtin = True


@nac3
class DMAError(Exception):
    """Raised when performing an invalid DMA operation."""
    artiq_builtin = True


@nac3
class SubkernelError(Exception):
    """Raised when an operation regarding a subkernel is invalid 
    or cannot be completed.
    """
    artiq_builtin = True


@nac3
class ClockFailure(Exception):
    """Raised when RTIO PLL has lost lock."""
    artiq_builtin = True


@nac3
class I2CError(Exception):
    """Raised when a I2C transaction fails."""
    artiq_builtin = True


@nac3
class SPIError(Exception):
    """Raised when a SPI transaction fails."""
    artiq_builtin = True


@nac3
class UnwrapNoneError(Exception):
    """Raised when unwrapping a none Option."""
    artiq_builtin = True


@nac3
class CXPError(Exception):
    """Raised when CXP transaction fails."""
    artiq_builtin = True
