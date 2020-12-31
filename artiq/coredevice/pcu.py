from .spr import mtspr, mfspr
from artiq.language.core import kernel


_MAX_SPRS_PER_GRP_BITS = 11
_SPRGROUP_PC = 7 << _MAX_SPRS_PER_GRP_BITS
_SPR_PCMR_CP    = 0x00000001  # Counter present
_SPR_PCMR_CISM  = 0x00000004  # Count in supervisor mode
_SPR_PCMR_CIUM  = 0x00000008  # Count in user mode
_SPR_PCMR_LA    = 0x00000010  # Load access event
_SPR_PCMR_SA    = 0x00000020  # Store access event
_SPR_PCMR_IF    = 0x00000040  # Instruction fetch event
_SPR_PCMR_DCM   = 0x00000080  # Data cache miss event
_SPR_PCMR_ICM   = 0x00000100  # Insn cache miss event
_SPR_PCMR_IFS   = 0x00000200  # Insn fetch stall event
_SPR_PCMR_LSUS  = 0x00000400  # LSU stall event
_SPR_PCMR_BS    = 0x00000800  # Branch stall event
_SPR_PCMR_DTLBM = 0x00001000  # DTLB miss event
_SPR_PCMR_ITLBM = 0x00002000  # ITLB miss event
_SPR_PCMR_DDS   = 0x00004000  # Data dependency stall event
_SPR_PCMR_WPE   = 0x03ff8000  # Watchpoint events


@kernel(flags={"nowrite", "nounwind"})
def _PCCR(n):
    return _SPRGROUP_PC + n


@kernel(flags={"nowrite", "nounwind"})
def _PCMR(n):
    return _SPRGROUP_PC + 8 + n


class CorePCU:
    """Core device performance counter unit (PCU) access"""
    def __init__(self, dmgr, core_device="core"):
        self.core = dmgr.get(core_device)

    @kernel
    def start(self):
        """
        Configure and clear the kernel CPU performance counters.

        The eight counters are configured to count the following events:
            * Load or store
            * Instruction fetch
            * Data cache miss
            * Instruction cache miss
            * Instruction fetch stall
            * Load-store-unit stall
            * Branch stall
            * Data dependency stall
        """
        for i in range(8):
            if not mfspr(_PCMR(i)) & _SPR_PCMR_CP:
                raise ValueError("counter not present")
            mtspr(_PCMR(i), 0)
            mtspr(_PCCR(i), 0)
        mtspr(_PCMR(0), _SPR_PCMR_CISM | _SPR_PCMR_LA | _SPR_PCMR_SA)
        mtspr(_PCMR(1), _SPR_PCMR_CISM | _SPR_PCMR_IF)
        mtspr(_PCMR(2), _SPR_PCMR_CISM | _SPR_PCMR_DCM)
        mtspr(_PCMR(3), _SPR_PCMR_CISM | _SPR_PCMR_ICM)
        mtspr(_PCMR(4), _SPR_PCMR_CISM | _SPR_PCMR_IFS)
        mtspr(_PCMR(5), _SPR_PCMR_CISM | _SPR_PCMR_LSUS)
        mtspr(_PCMR(6), _SPR_PCMR_CISM | _SPR_PCMR_BS)
        mtspr(_PCMR(7), _SPR_PCMR_CISM | _SPR_PCMR_DDS)

    @kernel
    def get(self, r):
        """
        Read the performance counters and store the counts in the
        array provided.

        :param list[int] r: array to store the counter values
        """
        for i in range(8):
            r[i] = mfspr(_PCCR(i))
