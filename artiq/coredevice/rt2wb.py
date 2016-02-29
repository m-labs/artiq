from artiq.language.core import *
from artiq.language.types import *


@syscall
def rt2wb_write(time_mu: TInt64, channel: TInt32, addr: TInt32, data: TInt32
                ) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall
def rt2wb_read_sync(time_mu: TInt64, channel: TInt32, addr: TInt32,
                    duration_mu: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")
