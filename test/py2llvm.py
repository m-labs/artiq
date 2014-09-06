import unittest
import ast
import inspect

from llvm import core as lc
from llvm import passes as lp
from llvm import ee as le

from artiq.py2llvm.infer_types import infer_function_types
from artiq.py2llvm import values
from artiq.py2llvm import compile_function
from artiq.py2llvm.tools import add_common_passes


def test_types(choice):
    a = 2          # promoted later to int64
    b = a + 1      # initially int32, becomes int64 after a is promoted
    c = b//2       # initially int32, becomes int64 after b is promoted
    d = 4          # stays int32
    x = int64(7)
    a += x         # promotes a to int64
    foo = True
    bar = None

    if choice:
        return 3
    else:
        return x

class FunctionTypesCase(unittest.TestCase):
    def setUp(self):
        self.ns = infer_function_types(
            None, ast.parse(inspect.getsource(test_types)),
            dict())

    def test_base_types(self):
        self.assertIsInstance(self.ns["foo"], values.VBool)
        self.assertIsInstance(self.ns["bar"], values.VNone)
        self.assertIsInstance(self.ns["d"], values.VInt)
        self.assertEqual(self.ns["d"].nbits, 32)
        self.assertIsInstance(self.ns["x"], values.VInt)
        self.assertEqual(self.ns["x"].nbits, 64)
        
    def test_promotion(self):
        for v in "abc":
            self.assertIsInstance(self.ns[v], values.VInt)
            self.assertEqual(self.ns[v].nbits, 64)

    def test_return(self):
        self.assertIsInstance(self.ns["return"], values.VInt)
        self.assertEqual(self.ns["return"].nbits, 64)


class CompiledFunction:
    def __init__(self, function, param_types):
        module = lc.Module.new("main")
        values.init_module(module)

        funcdef = ast.parse(inspect.getsource(function)).body[0]
        self.function, self.retval = compile_function(
            module, None, funcdef, param_types)
        self.argval = [param_types[arg.arg] for arg in funcdef.args.args]

        self.executor = le.ExecutionEngine.new(module)
        pass_manager = lp.PassManager.new()
        add_common_passes(pass_manager)
        pass_manager.run(module)

    def __call__(self, *args):
        args_llvm = [
            le.GenericValue.int(av.get_llvm_type(), a)
            for av, a in zip(self.argval, args)]
        result = self.executor.run_function(self.function, args_llvm)
        if isinstance(self.retval, values.VBool):
            return bool(result.as_int())
        elif isinstance(self.retval, values.VInt):
            return result.as_int_signed()
        else:
            raise NotImplementedError


def is_prime(x):
    d = 2
    while d*d <= x:
        if not x % d:
            return False
        d += 1
    return True

class CodeGenCase(unittest.TestCase):
    def test_is_prime(self):
        is_prime_c = CompiledFunction(is_prime, {"x": values.VInt(32)})
        for i in range(200):
            self.assertEqual(is_prime_c(i), is_prime(i))
