from migen.fhdl.std import *
from migen.genlib.fsm import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

class AD9858(Module):
	"""Wishbone interface to the AD9858 DDS chip.

	Addresses 0-63 map the AD9858 registers.
	Data is zero-padded.

	Write to address 64 to pulse the FUD signal.
	Address 65 is a GPIO register that controls	the sel, p and reset signals.
	sel is mapped to the lower bits, followed by p and reset.

	Write timing:
	Address is set one cycle before assertion of we_n.
	we_n is asserted for one cycle, at the same time as valid data is driven.

	Read timing:
	Address is set one cycle before assertion of rd_n.
	rd_n is asserted for 3 cycles.
	Data is sampled 2 cycles into the assertion of rd_n.

	FUD is asserted for fud_cycles cycles.
	"""
	def __init__(self, pads, fud_cycles=3, bus=None):
		if bus is None:
			bus = wishbone.Interface()
		self.bus = bus

		###

		dts = TSTriple(8)
		self.specials += dts.get_tristate(pads.d)
		dr = Signal(8)
		oe_p = Signal()
		self.sync += [
			pads.a.eq(bus.adr[:6]),
			dts.o.eq(bus.dat_w),
			dr.eq(dts.i),
			dts.oe.eq(oe_p)
		]

		gpio = Signal(flen(pads.sel) + flen(pads.p) + 1)
		gpio_load = Signal()
		self.sync += If(gpio_load, gpio.eq(bus.dat_w))
		self.comb += Cat(pads.sel, pads.p, pads.reset).eq(gpio)

		bus_r_sel_gpio = Signal()
		self.comb += If(bus_r_sel_gpio,
				bus.dat_r.eq(gpio)
			).Else(
				bus.dat_r.eq(dr)
			)

		fud_p = Signal()
		self.sync += pads.fud.eq(fud_p)
		fud_counter_max = fud_cycles - 1
		fud_counter = Signal(max=fud_counter_max+1)
		fud_counter_en = Signal()
		fud_counter_done = Signal()
		self.comb += fud_counter_done.eq(fud_counter == fud_counter_max)
		self.sync += If(fud_counter_en,
				fud_counter.eq(fud_counter + 1)
			).Else(
				fud_counter.eq(0)
			)

		pads.wr_n.reset = 1
		pads.rd_n.reset = 1
		wr_n_p = Signal(reset=1)
		rd_n_p = Signal(reset=1)
		self.sync += pads.wr_n.eq(wr_n_p), pads.rd_n.eq(rd_n_p)

		fsm = FSM()
		self.submodules += fsm

		fsm.act("IDLE",
			If(bus.cyc & bus.stb,
				If(bus.adr[6],
					If(bus.adr[0],
						NextState("GPIO")
					).Else(
						NextState("FUD")
					)
				).Else(
					If(bus.we,
						NextState("WRITE")
					).Else(
						NextState("READ")
					)
				)
			)
		)
		fsm.act("WRITE",
			oe_p.eq(1),
			wr_n_p.eq(0),
			bus.ack.eq(1),
			NextState("IDLE")
		)
		fsm.act("READ",
			rd_n_p.eq(0),
			NextState("READ0")
		)
		fsm.act("READ0",
			rd_n_p.eq(0),
			NextState("READ1")
		)
		fsm.act("READ1",
			rd_n_p.eq(0),
			NextState("READ2")
		)
		fsm.act("READ2",
			NextState("READ3")
		)
		fsm.act("READ3",
			bus.ack.eq(1),
			NextState("IDLE")
		)
		fsm.act("GPIO",
			bus.ack.eq(1),
			bus_r_sel_gpio.eq(1),
			If(bus.we, gpio_load.eq(1)),
			NextState("IDLE")
		)
		fsm.act("FUD",
			fud_p.eq(1),
			fud_counter_en.eq(1),
			If(fud_counter_done,
				bus.ack.eq(1),
				NextState("IDLE")
			)
		)

def _test_gen():
	# Test external bus writes
	yield TWrite(4, 2)
	yield TWrite(5, 3)

	# Test external bus reads
	yield TRead(14)
	yield TRead(15)

	# Test FUD
	yield TWrite(64, 0)

	# Test GPIO
	yield TWrite(65, 0xff)
	yield None

class _TestPads:
	def __init__(self):
		self.a = Signal(6)
		self.d = Signal(8)
		self.sel = Signal(5)
		self.p = Signal(2)
		self.fud = Signal()
		self.wr_n = Signal()
		self.rd_n = Signal()
		self.reset = Signal()

class _TB(Module):
	def __init__(self):
		pads = _TestPads()
		self.submodules.dut = AD9858(pads)
		self.submodules.initiator = wishbone.Initiator(_test_gen())
		self.submodules.interconnect = wishbone.InterconnectPointToPoint(self.initiator.bus, self.dut.bus)

if __name__ == "__main__":
	run_simulation(_TB(), vcd_name="ad9858.vcd")
