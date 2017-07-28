"""
DRTIO debugging functions.

Those syscalls are intended for ARTIQ developers only.
"""

from artiq.language.core import syscall
from artiq.language.types import TTuple, TInt32, TInt64, TNone


@syscall(flags={"nounwind", "nowrite"})
def drtio_get_channel_state(channel: TInt32) -> TTuple([TInt32, TInt64]):
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def drtio_reset_channel_state(channel: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def drtio_get_fifo_space(channel: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def drtio_get_packet_counts(linkno: TInt32) -> TTuple([TInt32, TInt32]):
    raise NotImplementedError("syscall not simulated")

@syscall(flags={"nounwind", "nowrite"})
def drtio_get_fifo_space_req_count(linkno: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")
