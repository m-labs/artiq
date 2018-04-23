from migen import *
from migen.genlib import io


class DiffMixin:
    def _diff(self, pads, name, output=False):
        """Retrieve the single-ended ``Signal()`` ``name`` from
        ``pads`` and in its absence retrieve the differential signal with the
        pin pairs ``name_p`` and ``name_n``. Do so as an output if ``output``,
        otherwise make a differential input."""
        if hasattr(pads, name):
            return getattr(pads, name)
        sig = Signal()
        p, n = (getattr(pads, name + "_" + s) for s in "pn")
        if output:
            self.specials += io.DifferentialOutput(sig, p, n)
        else:
            self.specials += io.DifferentialInput(p, n, sig)
        return sig
