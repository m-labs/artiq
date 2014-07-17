from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fifo import SyncFIFOBuffered
from migen.genlib.cdc import MultiReg

class RTIOChannelO(Module):
	def __init__(self, signal, counter_width, fifo_depth):
		self.submodules.fifo = SyncFIFOBuffered([
			("timestamp", counter_width), ("level", 1)],
			fifo_depth)

		self.event = self.fifo.din
		self.writable = self.fifo.writable
		self.we = self.fifo.we
		self.underflow = Signal()

		###

		counter = Signal(counter_width)
		self.sync += counter.eq(counter + 1)

		self.sync += If(self.we & self.writable,
			If(self.event.timestamp < counter + 2,
				self.underflow.eq(1)
			)
		)

		time_hit = Signal()
		self.comb += [
			time_hit.eq(self.fifo.readable &
				(self.fifo.dout.timestamp == counter)),
			self.fifo.re.eq(time_hit)
		]
		self.sync += If(time_hit, signal.eq(self.fifo.dout.level))

class RTIO(Module, AutoCSR):
	def __init__(self, channels, counter_width=32, ofifo_depth=8, ififo_depth=8):
		self._r_reset = CSRStorage(reset=1)
		self._r_chan_sel = CSRStorage(bits_for(len(channels)-1))
		self._r_o_timestamp = CSRStorage(counter_width)
		self._r_o_level = CSRStorage()
		self._r_o_writable = CSRStatus()
		self._r_o_we = CSR()
		self._r_o_underflow = CSRStatus()

		channel_os = []
		for n, channel in enumerate(channels):
			channel_o = InsertReset(RTIOChannelO(channel, counter_width, ofifo_depth))
			self.submodules += channel_o
			channel_os.append(channel_o)
			self.comb += [
				channel_o.reset.eq(self._r_reset.storage),
				channel_o.event.timestamp.eq(self._r_o_timestamp.storage),
				channel_o.event.level.eq(self._r_o_level.storage),
				channel_o.we.eq(self._r_o_we.re & (self._r_chan_sel == n))
			]

		channel_o = Array(channel_os)[self._r_chan_sel.storage]
		self.comb += [
			self._r_o_writable.status.eq(channel_o.writable),
			self._r_o_underflow.status.eq(channel_o.underflow)
		]
