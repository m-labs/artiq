import warnings

from artiq.gateware.rtio import rtlink


class Channel:
    def __init__(self, interface, probes=None, overrides=None,
                 ofifo_depth=None, ififo_depth=64):
        if probes is None:
            probes = []
        if overrides is None:
            overrides = []

        self.interface = interface
        self.probes = probes
        self.overrides = overrides
        if ofifo_depth is None:
            ofifo_depth = 64
        else:
            warnings.warn("ofifo_depth is deprecated", FutureWarning)
        self.ofifo_depth = ofifo_depth
        self.ififo_depth = ififo_depth

    @classmethod
    def from_phy(cls, phy, **kwargs):
        probes = getattr(phy, "probes", [])
        overrides = getattr(phy, "overrides", [])
        return cls(phy.rtlink, probes, overrides, **kwargs)


class LogChannel:
    """A degenerate channel used to log messages into the analyzer."""
    def __init__(self):
        self.interface = rtlink.Interface(rtlink.OInterface(32))
        self.probes = []
        self.overrides = []
