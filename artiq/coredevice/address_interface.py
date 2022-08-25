"""
Provide a standard method for drivers which has multiple RTIO output address
"""


class HasAddress:
    address_map = dict()

    @classmethod
    def get_address_name(cls, addr):
        return cls.address_map.get(addr)
