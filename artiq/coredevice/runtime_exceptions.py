import inspect

from artiq.language.core import RuntimeException


# Must be kept in sync with soc/runtime/exceptions.h

class InternalError(RuntimeException):
    """Raised when the runtime encounters an internal error condition."""
    eid = 1


class _RPCException(RuntimeException):
    eid = 2


class RTIOUnderflow(RuntimeException):
    """Raised when the CPU fails to submit a RTIO event early enough
    (with respect to the event's timestamp).

    The offending event is discarded and the RTIO core keeps operating.
    """
    eid = 3

    def __str__(self):
        return "at {} on channel {}, violation {}".format(
            self.p0*self.core.ref_period,
            self.p1,
            (self.p2 - self.p0)*self.core.ref_period)


class RTIOSequenceError(RuntimeException):
    """Raised when an event is submitted on a given channel with a timestamp
    not larger than the previous one.

    The offending event is discarded and the RTIO core keeps operating.
    """
    eid = 4

    def __str__(self):
        return "at {} on channel {}".format(self.p0*self.core.ref_period,
                                            self.p1)

class RTIOCollisionError(RuntimeException):
    """Raised when an event is submitted on a given channel with the same
    coarse timestamp as the previous one but with a different fine timestamp.

    Coarse timestamps correspond to the RTIO system clock (typically around
    125MHz) whereas fine timestamps correspond to the RTIO SERDES clock
    (typically around 1GHz).

    The offending event is discarded and the RTIO core keeps operating.
    """
    eid = 5

    def __str__(self):
        return "at {} on channel {}".format(self.p0*self.core.ref_period,
                                            self.p1)


class RTIOOverflow(RuntimeException):
    """Raised when at least one event could not be registered into the RTIO
    input FIFO because it was full (CPU not reading fast enough).

    This does not interrupt operations further than cancelling the current
    read attempt and discarding some events. Reading can be reattempted after
    the exception is caught, and events will be partially retrieved.
    """
    eid = 6

    def __str__(self):
        return "on channel {}".format(self.p0)


class DDSBatchError(RuntimeException):
    """Raised when attempting to start a DDS batch while already in a batch,
    or when too many commands are batched.
    """
    eid = 7


exception_map = {e.eid: e for e in globals().values()
                 if inspect.isclass(e)
                 and issubclass(e, RuntimeException)
                 and hasattr(e, "eid")}
