from migen import *


class OInterface:
    def __init__(self, data_width, address_width=0,
                 fine_ts_width=0, enable_replace=True,
                 delay=0):
        self.stb = Signal()
        self.busy = Signal()

        assert 0 <= data_width <= 512
        assert 0 <= address_width <= 8
        assert 0 <= fine_ts_width <= 4

        if data_width:
            self.data = Signal(data_width, reset_less=True)
        if address_width:
            self.address = Signal(address_width, reset_less=True)
        if fine_ts_width:
            self.fine_ts = Signal(fine_ts_width, reset_less=True)

        self.enable_replace = enable_replace

        if delay < 0:
            raise ValueError("only positive delays allowed", delay)
        self.delay = delay

    @classmethod
    def like(cls, other):
        return cls(get_data_width(other),
                   get_address_width(other),
                   get_fine_ts_width(other),
                   other.enable_replace,
                   other.delay)


class IInterface:
    def __init__(self, data_width,
                 timestamped=True, fine_ts_width=0, delay=0):
        self.stb = Signal()

        assert 0 <= data_width <= 32
        assert 0 <= fine_ts_width <= 4

        if data_width:
            self.data = Signal(data_width, reset_less=True)
        if fine_ts_width:
            self.fine_ts = Signal(fine_ts_width, reset_less=True)

        assert(not fine_ts_width or timestamped)
        self.timestamped = timestamped
        if delay < 0:
            raise ValueError("only positive delays")
        self.delay = delay

    @classmethod
    def like(cls, other):
        return cls(get_data_width(other),
                   other.timestamped,
                   get_fine_ts_width(other),
                   delay)


class Interface:
    def __init__(self, o, i=None):
        self.o = o
        self.i = i

    @classmethod
    def like(cls, other):
        if self.i is None:
            return cls(OInterface.like(self.o))
        else:
            return cls(OInterface.like(self.o),
                       IInterface.like(self.i))


def _get_or_zero(interface, attr):
    if interface is None:
        return 0
    assert isinstance(interface, (OInterface, IInterface))
    if hasattr(interface, attr):
        return len(getattr(interface, attr))
    else:
        return 0


def get_data_width(interface):
    return _get_or_zero(interface, "data")


def get_address_width(interface):
    return _get_or_zero(interface, "address")


def get_fine_ts_width(interface):
    return _get_or_zero(interface, "fine_ts")
