"""Direct Memory Access (DMA) extension.

This feature allows storing pre-defined sequences of output RTIO events into
the core device's SDRAM, and playing them back at higher speeds than the CPU
alone could achieve.
"""

from artiq.language.core import syscall, kernel
from artiq.language.types import TInt64, TStr, TNone

from numpy import int64


@syscall
def dma_record_start(name: TStr) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall
def dma_record_stop(duration: TInt64) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall
def dma_erase(name: TStr) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall
def dma_playback(timestamp: TInt64, name: TStr) -> TNone:
    raise NotImplementedError("syscall not simulated")


class DMARecordContextManager:
    """Context manager returned by ``CoreDMA.record()``.

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

    @kernel
    def __enter__(self):
        dma_record_start(self.name) # this may raise, so do it before altering now
        self.saved_now_mu = now_mu()
        at_mu(0)

    @kernel
    def __exit__(self, type, value, traceback):
        dma_record_stop(now_mu()) # see above
        at_mu(self.saved_now_mu)


class CoreDMA:
    """Core device Direct Memory Access (DMA) driver.

    Gives access to the DMA functionality of the core device.
    """

    kernel_invariants = {"core", "recorder"}

    def __init__(self, dmgr, core_device="core"):
        self.core     = dmgr.get(core_device)
        self.recorder = DMARecordContextManager()

    @kernel
    def record(self, name):
        """Returns a context manager that will record a DMA trace called ``name``.
        Any previously recorded trace with the same name is overwritten.
        The trace will persist across kernel switches."""
        self.recorder.name = name
        return self.recorder

    @kernel
    def erase(self, name):
        """Removes the DMA trace with the given name from storage."""
        dma_erase(name)

    @kernel
    def replay(self, name):
        """Replays a previously recorded DMA trace. This function blocks until
        the entire trace is submitted to the RTIO FIFOs."""
        dma_playback(now_mu(), name)
