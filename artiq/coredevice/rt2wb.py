from artiq.language.core import *
from artiq.language.types import *


@syscall
def rt2wb_input(channel: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")
