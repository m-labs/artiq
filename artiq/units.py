from collections import namedtuple

_prefixes_str = "pnum_kM"

Unit = namedtuple("Unit", "base_prefix name")

class DimensionError(Exception):
	pass

class Quantity:
	def __init__(self, amount, unit):
		self.amount = int(amount)
		self.unit = unit

	def __repr__(self):
		r_amount = self.amount
		r_prefix = self.unit.base_prefix
		if r_amount:
			while not r_amount % 1000 and r_prefix < len(_prefixes_str):
				r_amount //= 1000
				r_prefix += 1
		return str(r_amount) + " " + _prefixes_str[r_prefix] + self.unit.name

	def __add__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return Quantity(self.amount + other.amount, self.unit)
	__radd__ = __add__

	def __rmul__(self, other):
		if isinstance(other, Quantity):
			return NotImplemented
		return Quantity(self.amount*other, self.unit)

def check_unit(value, unit):
	if not isinstance(value, Quantity) or value.unit != unit:
		raise DimensionError

def _register_unit(base_prefix, name, prefixes):
	base_prefix_exp = _prefixes_str.index(base_prefix)
	unit = Unit(base_prefix_exp, name)
	globals()["base_"+name+"_unit"] = unit
	for prefix in prefixes:
		prefix_exp = _prefixes_str.index(prefix)
		exp_d = prefix_exp - base_prefix_exp
		assert(exp_d >= 0)
		quantity = Quantity(1000**exp_d, unit)
		full_name = prefix + name if prefix != "_" else name
		globals()[full_name] = quantity

_register_unit("p", "s", "pnum_")
_register_unit("_", "Hz", "_kM")
