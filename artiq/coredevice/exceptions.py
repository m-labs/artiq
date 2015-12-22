from artiq.language.core import ARTIQException


class ZeroDivisionError(ARTIQException):
    """Python's :class:`ZeroDivisionError`, mirrored in ARTIQ."""


class ValueError(ARTIQException):
    """Python's :class:`ValueError`, mirrored in ARTIQ."""


class IndexError(ARTIQException):
    """Python's :class:`IndexError`, mirrored in ARTIQ."""


class InternalError(ARTIQException):
    """Raised when the runtime encounters an internal error condition."""


class RTIOUnderflow(ARTIQException):
    """Raised when the CPU fails to submit a RTIO event early enough
    (with respect to the event's timestamp).

    The offending event is discarded and the RTIO core keeps operating.
    """


class RTIOSequenceError(ARTIQException):
    """Raised when an event is submitted on a given channel with a timestamp
    not larger than the previous one.

    The offending event is discarded and the RTIO core keeps operating.
    """


class RTIOCollisionError(ARTIQException):
    """Raised when an event is submitted on a given channel with the same
    coarse timestamp as the previous one but with a different fine timestamp.

    Coarse timestamps correspond to the RTIO system clock (typically around
    125MHz) whereas fine timestamps correspond to the RTIO SERDES clock
    (typically around 1GHz).

    The offending event is discarded and the RTIO core keeps operating.
    """


class RTIOOverflow(ARTIQException):
    """Raised when at least one event could not be registered into the RTIO
    input FIFO because it was full (CPU not reading fast enough).

    This does not interrupt operations further than cancelling the current
    read attempt and discarding some events. Reading can be reattempted after
    the exception is caught, and events will be partially retrieved.
    """


class DDSBatchError(ARTIQException):
    """Raised when attempting to start a DDS batch while already in a batch,
    or when too many commands are batched.
    """
