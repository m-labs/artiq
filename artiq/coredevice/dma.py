"""Direct Memory Access (DMA) extension.

This feature allows storing pre-defined sequences of output RTIO events into
the core device's SDRAM, and playing them back at higher speeds than the CPU
alone could achieve.
"""

from artiq.language.core import syscall, kernel
from artiq.language.types import TInt32, TInt64, TStr, TNone, TTuple, TBool
from artiq.coredevice.exceptions import DMAError

from numpy import int64


@syscall
def dma_record_start(name: TStr) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall
def dma_record_stop(duration: TInt64, enable_ddma: TBool) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall
def dma_erase(name: TStr) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall
def dma_retrieve(name: TStr) -> TTuple([TInt64, TInt32, TBool]):
    raise NotImplementedError("syscall not simulated")

@syscall
def dma_playback(timestamp: TInt64, ptr: TInt32, enable_ddma: TBool) -> TNone:
    raise NotImplementedError("syscall not simulated")


class DMARecordContextManager:
    """Context manager returned by :meth:`CoreDMA.record()`.

    Upon entering, starts recording a DMA trace. All RTIO operations are
    redirected to a newly created DMA buffer after this call, and ``now``
    is reset to zero.

    Upon leaving, stops recording a DMA trace. All recorded RTIO operations
    are stored in a newly created trace, and ``now`` is restored to the value
    it had before the context manager was entered.
    """
    def __init__(self):
        self.name = ""
        self.saved_now_mu = int64(0)
        self.enable_ddma = False

    @kernel
    def __enter__(self):
        dma_record_start(self.name) # this may raise, so do it before altering now
        self.saved_now_mu = now_mu()
        at_mu(0)

    @kernel
    def __exit__(self, type, value, traceback):
        dma_record_stop(now_mu(), self.enable_ddma) # see above
        at_mu(self.saved_now_mu)


class CoreDMA:
    """Core device Direct Memory Access (DMA) driver.

    Gives access to the DMA functionality of the core device.
    """

    kernel_invariants = {"core", "recorder"}

    def __init__(self, dmgr, core_device="core"):
        self.core     = dmgr.get(core_device)
        self.recorder = DMARecordContextManager()
        self.epoch    = 0

    @kernel
    def record(self, name, enable_ddma=False):
        """Returns a context manager that will record a DMA trace called `name`.
        Any previously recorded trace with the same name is overwritten.
        The trace will persist across kernel switches.

        In DRTIO context, distributed DMA can be toggled with `enable_ddma`.
        Enabling it allows running DMA on satellites, rather than sending all
        events from the master.

        Keeping it disabled it may improve performance in some scenarios, 
        e.g. when there are many small satellite buffers."""
        self.epoch += 1
        self.recorder.name = name
        self.recorder.enable_ddma = enable_ddma
        return self.recorder

    @kernel
    def erase(self, name):
        """Removes the DMA trace with the given name from storage."""
        self.epoch += 1
        dma_erase(name)

    @kernel
    def playback(self, name):
        """Replays a previously recorded DMA trace. This function blocks until
        the entire trace is submitted to the RTIO FIFOs."""
        (advance_mu, ptr, uses_ddma) = dma_retrieve(name)
        dma_playback(now_mu(), ptr, uses_ddma)
        delay_mu(advance_mu)

    @kernel
    def get_handle(self, name):
        """Returns a handle to a previously recorded DMA trace. The returned handle
        is only valid until the next call to :meth:`record` or :meth:`erase`."""
        (advance_mu, ptr, uses_ddma) = dma_retrieve(name)
        return (self.epoch, advance_mu, ptr, uses_ddma)

    @kernel
    def playback_handle(self, handle):
        """Replays a handle obtained with :meth:`get_handle`. Using this function
        is much faster than :meth:`playback` for replaying a set of traces repeatedly,
        but offloads the overhead of managing the handles onto the programmer."""
        (epoch, advance_mu, ptr, uses_ddma) = handle
        if self.epoch != epoch:
            raise DMAError("Invalid handle")
        dma_playback(now_mu(), ptr, uses_ddma)
        delay_mu(advance_mu)
