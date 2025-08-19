from migen import *

(RW, RO, WO) = range(3)


class AddressDecoder(Module):
    """
    Possible register_table elements:
      1. (Signal, type)
      2. (Address, Signal, type)
    """

    def __init__(self, register_table, data_width=None, address_width=None):
        max_reg_width, reg_readback = 0, False
        for reg_type in register_table:
            if len(reg_type) == 3:
                _, reg, type = reg_type
            else:
                reg, type = reg_type
            assert type in (RW, RO, WO)

            max_reg_width = max(max_reg_width, len(reg))
            if type in [RW, RO]:
                reg_readback = True

        if data_width is None:
            data_width = max_reg_width

        if address_width is None:
            address_width = log2_int(len(register_table), False)

        if reg_readback:
            self.source = Record([("stb", 1), ("data", data_width)])
            # add read bit
            self.sink = Record(
                [("stb", 1), ("data", data_width), ("address", address_width + 1)]
            )
        else:
            self.source = None
            self.sink = Record(
                [("stb", 1), ("data", data_width), ("address", address_width)]
            )

        # # #

        cases = {}
        next_addr = 0x00
        for ch, reg_type in enumerate(register_table):
            if len(reg_type) == 3:
                next_addr, reg, type = reg_type
            else:
                reg, type = reg_type
            assert len(reg) <= data_width
            assert type in (RW, RO, WO)

            if type in [RW, RO]:
                # MSB is read bit
                cases[next_addr | 1 << (address_width)] = self.source.data.eq(reg)
            if type in [RW, WO]:
                cases[next_addr] = reg.eq(self.sink.data)
            next_addr += 1

        assert next_addr <= 1 << address_width

        if reg_readback:
            self.sync += [
                self.source.stb.eq(0),
                If(
                    self.sink.stb,
                    Case(self.sink.address, cases),
                    self.source.stb.eq(self.sink.address[-1]),
                ),
            ]
        else:
            self.sync += [
                If(
                    self.sink.stb,
                    Case(self.sink.address, cases),
                ),
            ]
