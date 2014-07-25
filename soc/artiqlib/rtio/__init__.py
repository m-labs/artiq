from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fifo import SyncFIFOBuffered
from migen.genlib.cdc import MultiReg

from types import SimpleNamespace

from artiqlib.rtio import phy

class RTIOBankO(Module):
	def __init__(self, channels, counter_width, fine_ts_width, fifo_depth):
		self.sel = Signal(max=len(channels))
		self.timestamp = Signal(counter_width+fine_ts_width)
		self.value = Signal()
		self.writable = Signal()
		self.we = Signal()
		self.underflow = Signal()
		self.level = Signal(bits_for(fifo_depth))

		###

		counter = Signal(counter_width)
		self.sync += [
			counter.eq(counter + 1),
			If(self.we & self.writable,
				If(self.timestamp[fine_ts_width:] < counter + 2, self.underflow.eq(1))
			)
		]

		fifos = []
		for n, channel in enumerate(channels):
			fifo = SyncFIFOBuffered([
				("timestamp", counter_width+fine_ts_width), ("value", 2)],
				fifo_depth)
			self.submodules += fifo
			fifos.append(fifo)

			# FIFO write
			self.comb += [
				fifo.din.timestamp.eq(self.timestamp),
				fifo.din.value.eq(self.value),
				fifo.we.eq(self.we & (self.sel == n))
			]

			# FIFO read
			self.comb += [
				channel.hit.eq(fifo.readable &
					(fifo.dout.timestamp[fine_ts_width:] == counter)),
				channel.value.eq(fifo.dout.value),
				fifo.re.eq(channel.hit)
			]
			if fine_ts_width:
				self.comb += channel.fine_ts.eq(fifo.dout.timestamp[:fine_ts_width])

		selfifo = Array(fifos)[self.sel]
		self.comb += self.writable.eq(selfifo.writable), self.level.eq(selfifo.level)

class RTIO(Module, AutoCSR):
	def __init__(self, phy, counter_width=32, ofifo_depth=8, ififo_depth=8):
		# Extract info from PHY
		if hasattr(phy.interface[0], "o_fine_ts"):
			fine_ts_width = flen(channels[0].o_fine_ts)
		else:
			fine_ts_width = 0
		oes = [padif.oe for padif in phy.interface if hasattr(padif, "oe")]

		# Submodules
		self.submodules.bank_o = InsertReset(RTIOBankO(
			[SimpleNamespace(hit=padif.o_set_value,
					value=padif.o_value,
					fine_ts=getattr(padif, "o_fine_ts", None))
				for padif in phy.interface],
			counter_width, fine_ts_width, ofifo_depth))

		# CSRs
		self._r_reset = CSRStorage(reset=1)
		self._r_oe = CSRStorage(len(oes))
		self._r_chan_sel = CSRStorage(flen(self.bank_o.sel))
		self._r_o_timestamp = CSRStorage(counter_width+fine_ts_width)
		self._r_o_value = CSRStorage()
		self._r_o_writable = CSRStatus()
		self._r_o_we = CSR()
		self._r_o_underflow = CSRStatus()
		self._r_o_level = CSRStatus(bits_for(ofifo_depth))

		# OE
		self.comb += Cat(*oes).eq(self._r_oe.storage)

		# Output/Gate
		self.comb += [
			self.bank_o.reset.eq(self._r_reset.storage),
			self.bank_o.sel.eq(self._r_chan_sel.storage),
			self.bank_o.timestamp.eq(self._r_o_timestamp.storage),
			self.bank_o.value.eq(self._r_o_value.storage),
			self._r_o_writable.status.eq(self.bank_o.writable),
			self.bank_o.we.eq(self._r_o_we.re),
			self._r_o_underflow.status.eq(self.bank_o.underflow),
			self._r_o_level.status.eq(self.bank_o.level)
		]
