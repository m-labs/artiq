from artiq.language.core import syscall
from artiq.language.types import TInt32, TInt64, TList, TNone, TTuple


@syscall(flags={"nowrite"})
def rtio_output(target: TInt32, data: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nowrite"})
def rtio_output_wide(target: TInt32, data: TList(TInt32)) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nowrite"})
def rtio_input_timestamp(timeout_mu: TInt64, channel: TInt32) -> TInt64:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nowrite"})
def rtio_input_data(channel: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nowrite"})
def rtio_input_timestamped_data(timeout_mu: TInt64,
                                channel: TInt32) -> TTuple([TInt64, TInt32]):
    """Wait for an input event up to timeout_mu on the given channel, and
    return a tuple of timestamp and attached data, or (-1, 0) if the timeout is
    reached."""
    raise NotImplementedError("syscall not simulated")
