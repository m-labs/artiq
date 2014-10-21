import inspect

from artiq.language.core import RuntimeException


# Must be kept in sync with soc/runtime/exceptions.h

class OutOfMemory(RuntimeException):
    """Raised when the runtime fails to allocate memory.

    """
    eid = 0


class RTIOUnderflow(RuntimeException):
    """Raised when the CPU fails to submit a RTIO event early enough
    (with respect to the event's timestamp).

    Causes a reset of the RTIO core, except its time counter.

    """
    eid = 1


# Raised by RTIO driver for regular RTIO.
# Raised by runtime for DDS FUD.
class RTIOSequenceError(RuntimeException):
    """Raised when an event is submitted on a given channel with a timestamp
    not larger than the previous one.

    The offending event is discarded and RTIO operation is not affected
    further.

    """
    eid = 2


class RTIOOverflow(RuntimeException):
    """Raised when at least one event could not be registered into the RTIO
    input FIFO because it was full (CPU not reading fast enough).

    Causes a reset of the RTIO core, except its time counter.

    """
    eid = 3


exception_map = {e.eid: e for e in globals().values()
                 if inspect.isclass(e)
                 and issubclass(e, RuntimeException)
                 and hasattr(e, "eid")}
