from migen import *
from misoc.interconnect.csr import *

from artiq.gateware.drtio.wrpll.si549 import Si549


class WRPLL(Module, AutoCSR):
	def __init__(self, main_dcxo_i2c, helper_dxco_i2c):
		self.submodules.main_dcxo = Si549(main_dcxo_i2c)
		self.submodules.helper_dcxo = Si549(helper_dxco_i2c)
