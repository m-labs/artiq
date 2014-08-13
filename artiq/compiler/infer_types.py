from collections import namedtuple
from fractions import gcd
import ast

from artiq.language import units

def _lcm(a, b):
	return a*b//gcd(a, b)

TBool = namedtuple("TBool", "")
TFloat = namedtuple("TFloat", "")
TInt = namedtuple("TInt", "nbits")
TFractionCD = namedtuple("TFractionCD", "denominator")
TFraction = namedtuple("TFraction", "")

class TypeAnnotation:
	def __init__(self, t, unit=None):
		self.t = t
		self.unit = unit

	def __repr__(self):
		r = "TypeAnnotation("+str(self.t)
		if self.unit is not None:
			r += " <unit:"+str(self.unit.name)+">"
		r += ")"
		return r

	def promote(self, ta):
		if ta.unit != self.unit:
			raise units.DimensionError
		if isinstance(self.t, TBool):
			if not isinstance(ta.t, TBool):
				raise TypeError
		elif isinstance(self.t, TFloat):
			if not isinstance(ta.t, TFloat):
				raise TypeError
		elif isinstance(self.t, TInt):
			if isinstance(ta.t, TInt):
				self.t = TInt(max(self.t.nbits, ta.t.nbits))
			elif isinstance(ta.t, (TFractionCD, TFraction)):
				self.t = ta.t
			else:
				raise TypeError
		elif isinstance(self.t, TFractionCD):
			if isinstance(ta.t, TInt):
				pass
			elif isinstance(ta.t, TFractionCD):
				self.t = TFractionCD(_lcm(self.t.denominator, ta.t.denominator))
			elif isinstance(ta.t, TFraction):
				self.t = TFraction()
			else:
				raise TypeError
		elif isinstance(self.t, TFraction):
			if not isinstance(ta.t, (TInt, TFractionCD, TFraction)):
				raise TypeError
		else:
			raise TypeError

def _get_expr_type(sym_to_type, node):
	if isinstance(node, ast.NameConstant):
		if isinstance(node.value, bool):
			return TypeAnnotation(TBool())
		else:
			raise TypeError
	elif isinstance(node, ast.Num):
		if isinstance(node.n, int):
			nbits = 32 if abs(node.n) < 2**31 else 64
			return TypeAnnotation(TInt(nbits))
		elif isinstance(node.n, float):
			return TypeAnnotation(TFloat())
		else:
			raise TypeError
	elif isinstance(node, ast.Name):
		return sym_to_type[node.id]
	elif isinstance(node, ast.UnaryOp):
		return _get_expr_type(sym_to_type, node.operand)
	elif isinstance(node, ast.Compare):
		return TypeAnnotation(TBool())
	elif isinstance(node, ast.BinOp):
		l, r = _get_expr_type(sym_to_type, node.left), _get_expr_type(sym_to_type, node.right)
		if isinstance(node.op, (ast.Add, ast.Sub)):
			if l.unit != r.unit:
				raise units.DimensionError
			if isinstance(l.t, TFloat):
				if isinstance(r.t, (TFloat, TInt, TFraction, TFractionCD)):
					return l
				else:
					raise TypeError
			if isinstance(l.t, TInt) and isinstance(r.t, TInt):
				return TypeAnnotation(TInt(max(l.t.nbits, r.t.nbits)), l.unit)
			if isinstance(l.t, TInt) and isinstance(r.t, (TFloat, TFraction, TFractionCD)):
				return r
			if isinstance(l.t, (TFractionCD, TFraction)) and isinstance(r.t, TFloat):
				return r
			if isinstance(l.t, TFractionCD) and isinstance(r.t, TInt):
				return l
			if isinstance(l.t, TFractionCD) and isinstance(r.t, TFractionCD):
				return TypeAnnotation(TFractionCD(_lcm(l.t.denominator, r.t.denominator)), l.unit)
			if isinstance(l.t, TFractionCD) and isinstance(r.t, TFraction):
				return TypeAnnotation(TFraction())
			if isinstance(l.t, TFraction) and isinstance(r.t, (TInt, TFractionCD, TFraction)):
				return l
			raise TypeError
		else:
			raise NotImplementedError
	elif isinstance(node, ast.Call):
		if node.func.id == "bool":
			return TypeAnnotation(TBool())
		elif node.func.id == "float":
			return TypeAnnotation(TFloat())
		elif node.func.id == "int":
			return TypeAnnotation(TInt(32))
		elif node.func.id == "int64":
			return TypeAnnotation(TInt(64))
		elif node.func.id == "Fraction":
			if len(node.args) == 2 and isinstance(node.args[1], ast.Num):
				if not isinstance(node.args[1].n, int):
					raise TypeError
				return TypeAnnotation(TFractionCD(node.args[1].n))
			else:
				return TypeAnnotation(TFraction())
		elif node.func.id == "Quantity":
			ta = _get_expr_type(sym_to_type, node.args[0])
			ta.unit = getattr(units, node.args[1].id)
			return ta
		else:
			raise NotImplementedError
	else:
		raise NotImplementedError

if __name__ == "__main__":
	import sys
	testexpr = ast.parse(sys.argv[1], mode="eval")
	print(_get_expr_type(dict(), testexpr.body))
