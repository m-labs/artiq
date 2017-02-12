from artiq.language.core import syscall
from artiq.language.types import TInt32, TNone


@syscall(flags={"nounwind", "nowrite"})
def mfspr(spr: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nowrite", "nowrite"})
def mtspr(spr: TInt32, value: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")
