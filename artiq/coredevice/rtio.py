from numpy import int32, int64

from artiq.language.core import extern


@extern
def rtio_output(target: int32, data: int32):
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_output_wide(target: int32, data: list[int32]):
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_input_timestamp(timeout_mu: int64, channel: int32) -> int64:
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_input_data(channel: int32) -> int32:
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_input_timestamped_data(timeout_mu: int64,
                                channel: int32) -> tuple[int64, int32]:
    """Wait for an input event up to ``timeout_mu`` on the given channel, and
    return a tuple of timestamp and attached data, or (-1, 0) if the timeout is
    reached."""
    raise NotImplementedError("syscall not simulated")
