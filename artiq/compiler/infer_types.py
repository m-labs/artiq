from collections import namedtuple
import ast

from artiq.language import units

TBool = namedtuple("TBool", "")
TFloat = namedtuple("TFloat", "")
TInt = namedtuple("TInt", "nbits")
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

	def __eq__(self, other):
		return self.t == other.t and self.unit == other.unit

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
			else:
				raise TypeError
		elif isinstance(self.t, TFraction):
			if not isinstance(ta.t, TFraction):
				raise TypeError
		else:
			raise TypeError

def _get_addsub_type(l, r):
	if l.unit != r.unit:
		raise units.DimensionError
	if isinstance(l.t, TFloat):
		if isinstance(r.t, (TFloat, TInt, TFraction)):
			return l
		else:
			raise TypeError
	if isinstance(l.t, TInt) and isinstance(r.t, TInt):
		return TypeAnnotation(TInt(max(l.t.nbits, r.t.nbits)), l.unit)
	if isinstance(l.t, TInt) and isinstance(r.t, (TFloat, TFraction)):
		return r
	if isinstance(l.t, TFraction) and isinstance(r.t, TFloat):
		return r
	if isinstance(l.t, TFraction) and isinstance(r.t, (TInt, TFraction)):
		return l
	raise TypeError

def _get_mul_type(l, r):
	unit = l.unit
	if r.unit is not None:
		if unit is None:
			unit = r.unit
		else:
			raise NotImplementedError
	if isinstance(l.t, TFloat):
		if isinstance(r.t, (TFloat, TInt, TFraction)):
			return TypeAnnotation(TFloat(), unit)
		else:
			raise TypeError
	if isinstance(l.t, TInt) and isinstance(r.t, TInt):
		return TypeAnnotation(TInt(max(l.t.nbits, r.t.nbits)), unit)
	if isinstance(l.t, TInt) and isinstance(r.t, (TFloat, TFraction)):
		return TypeAnnotation(r.t, unit)
	if isinstance(l.t, TFraction) and isinstance(r.t, TFloat):
		return TypeAnnotation(TFloat(), unit)
	if isinstance(l.t, TFraction) and isinstance(r.t, (TInt, TFraction)):
		return TypeAnnotation(TFraction(), unit)
	raise TypeError

def _get_div_unit(l, r):
	if l.unit is not None and r.unit is None:
		return l.unit
	elif l.unit == r.unit:
		return None
	else:
		raise NotImplementedError

def _get_truediv_type(l, r):
	unit = _get_div_unit(l, r)
	if isinstance(l.t, (TInt, TFraction)) and isinstance(r.t, TFraction):
		return TypeAnnotation(TFraction(), unit)
	elif isinstance(l.t, TFraction) and isinstance(r.t, (TInt, TFraction)):
		return TypeAnnotation(TFraction(), unit)
	else:
		return TypeAnnotation(TFloat(), unit)

def _get_floordiv_type(l, r):
	unit = _get_div_unit(l, r)
	if isinstance(l.t, TInt) and isinstance(r.t, TInt):
		return TypeAnnotation(TInt(max(l.t.nbits, r.t.nbits)), unit)
	elif isinstance(l.t, (TInt, TFloat)) and isinstance(r.t, TFloat):
		return TypeAnnotation(TFloat(), unit)
	elif isinstance(l.t, TFloat) and isinstance(r.t, (TInt, TFloat)):
		return TypeAnnotation(TFloat(), unit)
	elif (isinstance(l.t, TFloat) and isinstance(r.t, TFraction)) or (isinstance(l.t, TFraction) and isinstance(r.t, TFloat)):
		return TypeAnnotation(TInt(64), unit)
	elif isinstance(l.t, (TInt, TFraction)) and isinstance(r.t, TFraction):
		return TypeAnnotation(TFraction(), unit)
	elif isinstance(l.t, TFraction) and isinstance(r.t, (TInt, TFraction)):
		return TypeAnnotation(TFraction(), unit)
	else:
		raise NotImplementedError

def _get_call_type(sym_to_type, node):
	fn = node.func.id
	if fn == "bool":
		return TypeAnnotation(TBool())
	elif fn == "float":
		return TypeAnnotation(TFloat())
	elif fn == "int" or fn == "round":
		return TypeAnnotation(TInt(32))
	elif fn == "int64" or fn == "round64":
		return TypeAnnotation(TInt(64))
	elif fn == "Fraction":
		return TypeAnnotation(TFraction())
	elif fn == "Quantity":
		ta = _get_expr_type(sym_to_type, node.args[0])
		ta.unit = getattr(units, node.args[1].id)
		return ta
	else:
		raise NotImplementedError

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
			return _get_addsub_type(l, r)
		elif isinstance(node.op, ast.Mul):
			return _get_mul_type(l, r)
		elif isinstance(node.op, ast.Div):
			return _get_truediv_type(l, r)
		elif isinstance(node.op, ast.FloorDiv):
			return _get_floordiv_type(l, r)
		else:
			raise NotImplementedError
	elif isinstance(node, ast.Call):
		return _get_call_type(sym_to_type, node)
	else:
		raise NotImplementedError

if __name__ == "__main__":
	import sys
	testexpr = ast.parse(sys.argv[1], mode="eval")
	print(_get_expr_type(dict(), testexpr.body))
