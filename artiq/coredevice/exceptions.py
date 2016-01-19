import builtins
from artiq.language.core import ARTIQException


ZeroDivisionError = builtins.ZeroDivisionError
ValueError = builtins.ValueError
IndexError = builtins.IndexError


class InternalError(Exception):
    """Raised when the runtime encounters an internal error condition."""
    artiq_builtin = True


class CacheError(Exception):
    """Raised when putting a value into a cache row would violate memory safety."""
    artiq_builtin = True


class RTIOUnderflow(Exception):
    """Raised when the CPU fails to submit a RTIO event early enough
    (with respect to the event's timestamp).

    The offending event is discarded and the RTIO core keeps operating.
    """
    artiq_builtin = True

class RTIOSequenceError(Exception):
    """Raised when an event is submitted on a given channel with a timestamp
    not larger than the previous one.

    The offending event is discarded and the RTIO core keeps operating.
    """
    artiq_builtin = True

class RTIOCollisionError(Exception):
    """Raised when an event is submitted on a given channel with the same
    coarse timestamp as the previous one but with a different fine timestamp.

    Coarse timestamps correspond to the RTIO system clock (typically around
    125MHz) whereas fine timestamps correspond to the RTIO SERDES clock
    (typically around 1GHz).

    The offending event is discarded and the RTIO core keeps operating.
    """
    artiq_builtin = True

class RTIOOverflow(Exception):
    """Raised when at least one event could not be registered into the RTIO
    input FIFO because it was full (CPU not reading fast enough).

    This does not interrupt operations further than cancelling the current
    read attempt and discarding some events. Reading can be reattempted after
    the exception is caught, and events will be partially retrieved.
    """
    artiq_builtin = True

class DDSBatchError(Exception):
    """Raised when attempting to start a DDS batch while already in a batch,
    or when too many commands are batched.
    """
    artiq_builtin = True
