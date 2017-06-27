class CRC:
    """Generic and simple table driven CRC calculator.

    This implementation is:

        * MSB first data
        * "un-reversed" full polynomial (i.e. starts with 0x1)
        * no initial complement
        * no final complement

    Handle any variation on those details outside this class.

    >>> r = CRC(0x1814141AB)(b"123456789")  # crc-32q
    >>> assert r == 0x3010BF7F, hex(r)
    """
    def __init__(self, poly, data_width=8):
        self.poly = poly
        self.crc_width = poly.bit_length() - 1
        self.data_width = data_width
        self._table = [self._one(i << self.crc_width - data_width)
                       for i in range(1 << data_width)]

    def _one(self, i):
        for j in range(self.data_width):
            i <<= 1
            if i & 1 << self.crc_width:
                i ^= self.poly
        return i

    def __call__(self, msg, crc=0):
        for data in msg:
            p = data ^ crc >> self.crc_width - self.data_width
            q = crc << self.data_width & (1 << self.crc_width) - 1
            crc = self._table[p] ^ q
        return crc
