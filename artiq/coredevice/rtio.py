from artiq.language.core import syscall
from artiq.language.types import TInt64, TInt32, TNone, TList


@syscall(flags={"nowrite"})
def rtio_output(time_mu: TInt64, channel: TInt32, addr: TInt32, data: TInt32
                ) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nowrite"})
def rtio_output_wide(time_mu: TInt64, channel: TInt32, addr: TInt32,
                     data: TList(TInt32)) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nowrite"})
def rtio_input_timestamp(timeout_mu: TInt64, channel: TInt32) -> TInt64:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nowrite"})
def rtio_input_data(channel: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")
