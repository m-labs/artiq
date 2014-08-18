from collections import namedtuple
from fractions import Fraction

_prefixes_str = "pnum_kMG"
_smallest_prefix = Fraction(1, 10**12)

Unit = namedtuple("Unit", "name")

class DimensionError(Exception):
	pass

class Quantity:
	def __init__(self, amount, unit):
		self.amount = amount
		self.unit = unit

	def __repr__(self):
		r_amount = self.amount
		if isinstance(r_amount, int) or isinstance(r_amount, Fraction):
			r_prefix = 0
			r_amount = r_amount/_smallest_prefix
			if r_amount:
				numerator = r_amount.numerator
				while numerator % 1000 == 0 and r_prefix < len(_prefixes_str):
					numerator /= 1000
					r_amount /= 1000
					r_prefix += 1
			prefix_str = _prefixes_str[r_prefix]
			if prefix_str == "_":
				prefix_str = ""
			return str(r_amount) + " " + prefix_str + self.unit.name
		else:
			return str(r_amount) + " " + self.unit.name

	def __mul__(self, other):
		if isinstance(other, Quantity):
			return NotImplemented
		return Quantity(self.amount*other, self.unit)
	def __rmul__(self, other):
		if isinstance(other, Quantity):
			return NotImplemented
		return Quantity(other*self.amount, self.unit)
	def __truediv__(self, other):
		if isinstance(other, Quantity):
			if other.unit == self.unit:
				return self.amount/other.amount
			else:
				return NotImplemented
		else:
			return Quantity(self.amount/other, self.unit)
	def __floordiv__(self, other):
		if isinstance(other, Quantity):
			if other.unit == self.unit:
				return self.amount//other.amount
			else:
				return NotImplemented
		else:
			return Quantity(self.amount//other, self.unit)

	def __neg__(self):
		return Quantity(-self.amount, self.unit)

	def __add__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return Quantity(self.amount + other.amount, self.unit)
	def __radd__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return Quantity(other.amount + self.amount, self.unit)
	def __sub__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return Quantity(self.amount - other.amount, self.unit)
	def __rsub__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return Quantity(other.amount - self.amount, self.unit)

	def __lt__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return self.amount < other.amount
	def __le__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return self.amount <= other.amount
	def __eq__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return self.amount == other.amount
	def __ne__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return self.amount != other.amount
	def __gt__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return self.amount > other.amount
	def __ge__(self, other):
		if self.unit != other.unit:
			raise DimensionError
		return self.amount >= other.amount

def check_unit(value, unit):
	if not isinstance(value, Quantity) or value.unit != unit:
		raise DimensionError
	return value.amount

def _register_unit(name, prefixes):
	unit = Unit(name)
	globals()[name+"_unit"] = unit
	amount = _smallest_prefix
	for prefix in _prefixes_str:
		if prefix in prefixes:
			quantity = Quantity(amount, unit)
			full_name = prefix + name if prefix != "_" else name
			globals()[full_name] = quantity
		amount *= 1000

_register_unit("s", "pnum_")
_register_unit("Hz", "_kMG")

microcycle_unit = Unit("microcycle")
microcycle = Quantity(1, microcycle_unit)
