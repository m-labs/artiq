from migen.fhdl.std import *
from migen.genlib.cdc import MultiReg
from migen.genlib.record import Record

class PHYBase(Module):
	def __init__(self, fine_ts_bits, pads, output_only_pads):
		self.interface = []
		
		for pad in pads:
			layout = [
				("o_set_value", 1),
				("o_value", 1)
			]
			if fine_ts_bits:
				layout.append(("o_fine_ts", fine_ts_bits))
			if pad not in output_only_pads:
				layout += [
					("oe", 1),
					("i_detect", 1),
					("i_value", 1)
				]
				if fine_ts_bits:
					layout.append(("i_fine_ts", fine_ts_bits))
			self.interface.append(Record(layout))

class SimplePHY(PHYBase):
	def __init__(self, pads, output_only_pads=set()):
		PHYBase.__init__(self, 0, pads, output_only_pads)

		for pad, padif in zip(pads, self.interface):
			o_pad_d1 = Signal()
			o_pad = Signal()
			self.sync += [
				If(padif.o_set_value, o_pad_d1.eq(padif.o_value)),
				o_pad.eq(o_pad_d1)
			]
			if pad in output_only_pads:
				self.comb += pad.eq(o_pad)
			else:
				ts = TSTriple()
				i_pad = Signal()
				self.sync += ts.oe.eq(padif.oe)
				self.comb += ts.o.eq(o_pad)
				self.specials += MultiReg(ts.i, i_pad), \
					ts.get_tristate(pad)

				i_pad_d = Signal()
				self.sync += i_pad_d.eq(i_pad)
				self.comb += padif.i_detect.eq(i_pad ^ i_pad_d), \
					padif.i_value.eq(i_pad)
