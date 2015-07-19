"""
The :mod:`ir` module contains the intermediate representation
of the ARTIQ compiler.
"""

from collections import OrderedDict
from pythonparser import ast
from . import types, builtins

# Generic SSA IR classes

def escape_name(name):
    if all([str.isalnum(x) or x == "." for x in name]):
        return name
    else:
        return "\"{}\"".format(name.replace("\"", "\\\""))

class TBasicBlock(types.TMono):
    def __init__(self):
        super().__init__("label")

class TOption(types.TMono):
    def __init__(self, inner):
        super().__init__("option", {"inner": inner})

class Value:
    """
    An SSA value that keeps track of its uses.

    :ivar type: (:class:`.types.Type`) type of this value
    :ivar uses: (list of :class:`Value`) values that use this value
    """

    def __init__(self, typ):
        self.uses, self.type = set(), typ.find()

    def replace_all_uses_with(self, value):
        for user in self.uses:
            user.replace_uses_of(self, value)

class Constant(Value):
    """
    A constant value.

    :ivar value: (Python object) value
    """

    def __init__(self, value, typ):
        super().__init__(typ)
        self.value = value

    def as_operand(self):
        return str(self)

    def __str__(self):
        return "{} {}".format(types.TypePrinter().name(self.type),
                              repr(self.value))

class NamedValue(Value):
    """
    An SSA value that has a name.

    :ivar name: (string) name of this value
    :ivar function: (:class:`Function`) function containing this value
    """

    def __init__(self, typ, name):
        super().__init__(typ)
        self.name, self.function = name, None

    def set_name(self, new_name):
        if self.function is not None:
            self.function._remove_name(self.name)
            self.name = self.function._add_name(new_name)
        else:
            self.name = new_name

    def _set_function(self, new_function):
        if self.function != new_function:
            if self.function is not None:
                self.function._remove_name(self.name)
            self.function = new_function
            if self.function is not None:
                self.name = self.function._add_name(self.name)

    def _detach(self):
        self.function = None

    def as_operand(self):
        return "{} %{}".format(types.TypePrinter().name(self.type),
                               escape_name(self.name))

class User(NamedValue):
    """
    An SSA value that has operands.

    :ivar operands: (list of :class:`Value`) operands of this value
    """

    def __init__(self, operands, typ, name):
        super().__init__(typ, name)
        self.operands = []
        if operands is not None:
            self.set_operands(operands)

    def set_operands(self, new_operands):
        for operand in self.operands:
            operand.uses.remove(self)
        self.operands = new_operands
        for operand in self.operands:
            operand.uses.add(self)

    def drop_references(self):
        self.set_operands([])

    def replace_uses_of(self, value, replacement):
        assert value in operands

        for index, operand in enumerate(operands):
            if operand == value:
                operands[index] = replacement

        value.uses.remove(self)
        replacement.uses.add(self)

class Instruction(User):
    """
    An SSA instruction.
    """

    def __init__(self, operands, typ, name=""):
        assert isinstance(operands, list)
        assert isinstance(typ, types.Type)
        super().__init__(operands, typ, name)
        self.basic_block = None
        self.loc = None

    def set_basic_block(self, new_basic_block):
        self.basic_block = new_basic_block
        if self.basic_block is not None:
            self._set_function(self.basic_block.function)
        else:
            self._set_function(None)

    def opcode(self):
        """String representation of the opcode."""
        return "???"

    def _detach(self):
        self.set_basic_block(None)

    def remove_from_parent(self):
        if self.basic_block is not None:
            self.basic_block.remove(self)

    def erase(self):
        self.remove_from_parent()
        self.drop_references()

    def replace_with(self, value):
        self.replace_all_uses_with(value)
        if isinstance(value, Instruction):
            self.basic_block.replace(self, value)
            self.drop_references()
        else:
            self.erase()

    def _operands_as_string(self):
        return ", ".join([operand.as_operand() for operand in self.operands])

    def __str__(self):
        if builtins.is_none(self.type):
            prefix = ""
        else:
            prefix = "%{} = {} ".format(escape_name(self.name),
                                        types.TypePrinter().name(self.type))

        if any(self.operands):
            return "{}{} {}".format(prefix, self.opcode(), self._operands_as_string())
        else:
            return "{}{}".format(prefix, self.opcode())

class Phi(Instruction):
    """
    An SSA instruction that joins data flow.

    Use :meth:`incoming` and :meth:`add_incoming` instead of
    directly reading :attr:`operands` or calling :meth:`set_operands`.
    """

    def __init__(self, typ, name=""):
        super().__init__([], typ, name)

    def opcode(self):
        return "phi"

    def incoming(self):
        operand_iter = iter(self.operands)
        while True:
            yield next(operand_iter), next(operand_iter)

    def incoming_blocks(self):
        (block for (block, value) in self.incoming())

    def incoming_values(self):
        (value for (block, value) in self.incoming())

    def incoming_value_for_block(self, target_block):
        for (block, value) in self.incoming():
            if block == target_block:
                return value
        assert False

    def add_incoming(self, value, block):
        assert value.type == self.type
        self.operands.append(value)
        self.operands.append(block)

    def __str__(self):
        if builtins.is_none(self.type):
            prefix = ""
        else:
            prefix = "%{} = {} ".format(escape_name(self.name),
                                        types.TypePrinter().name(self.type))

        if any(self.operands):
            operand_list = ["%{} => {}".format(escape_name(block.name), value.as_operand())
                            for value, block in self.incoming()]
            return "{}{} [{}]".format(prefix, self.opcode(), ", ".join(operand_list))
        else:
            return "{}{} [???]".format(prefix, self.opcode())

class Terminator(Instruction):
    """
    An SSA instruction that performs control flow.
    """

    def successors(self):
        return [operand for operand in self.operands if isinstance(operand, BasicBlock)]

class BasicBlock(NamedValue):
    """
    A block of instructions with no control flow inside it.

    :ivar instructions: (list of :class:`Instruction`)
    """

    def __init__(self, instructions, name=""):
        super().__init__(TBasicBlock(), name)
        self.instructions = []
        self.set_instructions(instructions)

    def set_instructions(self, new_insns):
        for insn in self.instructions:
            insn.detach()
        self.instructions = new_insns
        for insn in self.instructions:
            insn.set_basic_block(self)

    def remove_from_parent(self):
        if self.function is not None:
            self.function.remove(self)

    def erase(self):
        for insn in self.instructions:
            insn.erase()
        self.remove_from_parent()

    def prepend(self, insn):
        assert isinstance(insn, Instruction)
        insn.set_basic_block(self)
        self.instructions.insert(0, insn)
        return insn

    def append(self, insn):
        assert isinstance(insn, Instruction)
        insn.set_basic_block(self)
        self.instructions.append(insn)
        return insn

    def index(self, insn):
        return self.instructions.index(insn)

    def insert(self, before, insn):
        assert isinstance(insn, Instruction)
        insn.set_basic_block(self)
        self.instructions.insert(self.index(before), insn)
        return insn

    def remove(self, insn):
        assert insn in self.instructions
        insn._detach()
        self.instructions.remove(insn)
        return insn

    def replace(self, insn, replacement):
        self.insert(insn, replacement)
        self.remove(insn)

    def is_terminated(self):
        return any(self.instructions) and isinstance(self.instructions[-1], Terminator)

    def terminator(self):
        assert self.is_terminated()
        return self.instructions[-1]

    def successors(self):
        return self.terminator().successors()

    def predecessors(self):
        return [use.basic_block for use in self.uses if isinstance(use, Terminator)]

    def __str__(self):
        # Header
        lines = ["{}:".format(escape_name(self.name))]
        if self.function is not None:
            lines[0] += " ; predecessors: {}".format(
                ", ".join([escape_name(pred.name) for pred in self.predecessors()]))

        # Annotated instructions
        loc = None
        for insn in self.instructions:
            if loc != insn.loc:
                loc = insn.loc

                if loc is None:
                    lines.append("; <synthesized>")
                else:
                    source_lines = loc.source_lines()
                    beg_col, end_col = loc.column(), loc.end().column()
                    source_lines[-1] = \
                        source_lines[-1][:end_col] + "`" + source_lines[-1][end_col:]
                    source_lines[0] = \
                        source_lines[0][:beg_col] + "`" + source_lines[0][beg_col:]

                    line_desc = "{}:{}".format(loc.source_buffer.name, loc.line())
                    lines += ["; {} {}".format(line_desc, line.rstrip("\n"))
                              for line in source_lines]
            lines.append("  " + str(insn))

        return "\n".join(lines)

    def __repr__(self):
        return "<BasicBlock '{}'>".format(self.name)

class Argument(NamedValue):
    """
    A function argument.
    """

    def __str__(self):
        return self.as_operand()

class Function:
    """
    A function containing SSA IR.
    """

    def __init__(self, typ, name, arguments):
        self.type, self.name = typ, name
        self.names, self.arguments, self.basic_blocks = set(), [], []
        self.set_arguments(arguments)

    def _remove_name(self, name):
        self.names.remove(name)

    def _add_name(self, base_name):
        name, counter = base_name, 1
        while name in self.names or name == "":
            if base_name == "":
                name = "v.{}".format(str(counter))
            else:
                name = "{}.{}".format(name, counter)
            counter += 1

        self.names.add(name)
        return name

    def set_arguments(self, new_arguments):
        for argument in self.arguments:
            argument._set_function(None)
        self.arguments = new_arguments
        for argument in self.arguments:
            argument._set_function(self)

    def add(self, basic_block):
        basic_block._set_function(self)
        self.basic_blocks.append(basic_block)

    def remove(self, basic_block):
        basic_block._detach()
        self.basic_blocks.remove(basic_block)

    def entry(self):
        assert any(self.basic_blocks)
        return self.basic_blocks[0]

    def exits(self):
        return [block for block in self.basic_blocks if not any(block.successors())]

    def instructions(self):
        for basic_block in self.basic_blocks:
            yield from iter(basic_block.instructions)

    def __str__(self):
        printer = types.TypePrinter()
        lines = []
        lines.append("{} {}({}) {{ ; type: {}".format(
                        printer.name(self.type.ret), self.name,
                        ", ".join([arg.as_operand() for arg in self.arguments]),
                        printer.name(self.type)))
        for block in self.basic_blocks:
            lines.append(str(block))
        lines.append("}")
        return "\n".join(lines)

# Python-specific SSA IR classes

class TEnvironment(types.TMono):
    def __init__(self, vars, outer=None):
        if outer is not None:
            assert isinstance(outer, TEnvironment)
            env = OrderedDict({".outer": outer})
            env.update(vars)
        else:
            env = OrderedDict(vars)

        super().__init__("environment", env)

    def type_of(self, name):
        if name in self.params:
            return self.params[name].find()
        elif ".outer" in self.params:
            return self.params[".outer"].type_of(name)
        else:
            assert False

    def outermost(self):
        if ".outer" in self.params:
            return self.params[".outer"].outermost()
        else:
            return self

    """
    Add a new binding, ensuring hygiene.

    :returns: (string) mangled name
    """
    def add(self, base_name, typ):
        name, counter = base_name, 1
        while name in self.params or name == "":
            if base_name == "":
                name = str(counter)
            else:
                name = "{}.{}".format(name, counter)
            counter += 1

        self.params[name] = typ.find()
        return name

def is_environment(typ):
    return isinstance(typ, TEnvironment)

class EnvironmentArgument(NamedValue):
    """
    A function argument specifying an outer environment.
    """

    def as_operand(self):
        return "environment(...) %{}".format(escape_name(self.name))

class Alloc(Instruction):
    """
    An instruction that allocates an object specified by
    the type of the intsruction.
    """

    def __init__(self, operands, typ, name=""):
        for operand in operands: assert isinstance(operand, Value)
        super().__init__(operands, typ, name)

    def opcode(self):
        return "alloc"

    def as_operand(self):
        if is_environment(self.type):
            # Only show full environment in the instruction itself
            return "%{}".format(escape_name(self.name))
        else:
            return super().as_operand()

class GetLocal(Instruction):
    """
    An intruction that loads a local variable from an environment,
    possibly going through multiple levels of indirection.

    :ivar var_name: (string) variable name
    """

    """
    :param env: (:class:`Value`) local environment
    :param var_name: (string) local variable name
    """
    def __init__(self, env, var_name, name=""):
        assert isinstance(env, Value)
        assert isinstance(env.type, TEnvironment)
        assert isinstance(var_name, str)
        super().__init__([env], env.type.type_of(var_name), name)
        self.var_name = var_name

    def opcode(self):
        return "getlocal({})".format(self.var_name)

    def environment(self):
        return self.operands[0]

class SetLocal(Instruction):
    """
    An intruction that stores a local variable into an environment,
    possibly going through multiple levels of indirection.

    :ivar var_name: (string) variable name
    """

    """
    :param env: (:class:`Value`) local environment
    :param var_name: (string) local variable name
    :param value: (:class:`Value`) value to assign
    """
    def __init__(self, env, var_name, value, name=""):
        assert isinstance(env, Value)
        assert isinstance(env.type, TEnvironment)
        assert isinstance(var_name, str)
        assert env.type.type_of(var_name) == value.type
        assert isinstance(value, Value)
        super().__init__([env, value], builtins.TNone(), name)
        self.var_name = var_name

    def opcode(self):
        return "setlocal({})".format(self.var_name)

    def environment(self):
        return self.operands[0]

    def value(self):
        return self.operands[1]

class GetAttr(Instruction):
    """
    An intruction that loads an attribute from an object,
    or extracts a tuple element.

    :ivar attr: (string) variable name
    """

    """
    :param obj: (:class:`Value`) object or tuple
    :param attr: (string or integer) attribute or index
    """
    def __init__(self, obj, attr, name=""):
        assert isinstance(obj, Value)
        assert isinstance(attr, (str, int))
        if isinstance(attr, int):
            assert isinstance(obj.type, types.TTuple)
            typ = obj.type.elts[attr]
        else:
            typ = obj.type.attributes[attr]
        super().__init__([obj], typ, name)
        self.attr = attr

    def opcode(self):
        return "getattr({})".format(repr(self.attr))

    def env(self):
        return self.operands[0]

class SetAttr(Instruction):
    """
    An intruction that stores an attribute to an object.

    :ivar attr: (string) variable name
    """

    """
    :param obj: (:class:`Value`) object or tuple
    :param attr: (string or integer) attribute
    :param value: (:class:`Value`) value to store
    """
    def __init__(self, obj, attr, value, name=""):
        assert isinstance(obj, Value)
        assert isinstance(attr, (str, int))
        assert isinstance(value, Value)
        if isinstance(attr, int):
            assert value.type == obj.type.elts[attr]
        else:
            assert value.type == obj.type.attributes[attr]
        super().__init__([obj, value], typ, name)
        self.attr = attr

    def opcode(self):
        return "setattr({})".format(repr(self.attr))

    def env(self):
        return self.operands[0]

    def value(self):
        return self.operands[1]

class GetElem(Instruction):
    """
    An intruction that loads an element from a list.
    """

    """
    :param lst: (:class:`Value`) list
    :param index: (:class:`Value`) index
    """
    def __init__(self, lst, index, name=""):
        assert isinstance(lst, Value)
        assert isinstance(index, Value)
        super().__init__([lst, index], builtins.get_iterable_elt(lst.type), name)

    def opcode(self):
        return "getelem"

    def list(self):
        return self.operands[0]

    def index(self):
        return self.operands[1]

class SetElem(Instruction):
    """
    An intruction that stores an element into a list.
    """

    """
    :param lst: (:class:`Value`) list
    :param index: (:class:`Value`) index
    :param value: (:class:`Value`) value to store
    """
    def __init__(self, lst, index, value, name=""):
        assert isinstance(lst, Value)
        assert isinstance(index, Value)
        assert isinstance(value, Value)
        assert builtins.get_iterable_elt(lst.type) == value.type.find()
        super().__init__([lst, index, value], builtins.TNone(), name)

    def opcode(self):
        return "setelem"

    def list(self):
        return self.operands[0]

    def index(self):
        return self.operands[1]

    def value(self):
        return self.operands[2]

class Coerce(Instruction):
    """
    A coercion operation for numbers.
    """

    def __init__(self, value, typ, name=""):
        assert isinstance(value, Value)
        assert isinstance(typ, types.Type)
        super().__init__([value], typ, name)

    def opcode(self):
        return "coerce"

    def value(self):
        return self.operands[0]

class Arith(Instruction):
    """
    An arithmetic operation on numbers.

    :ivar op: (:class:`pythonparser.ast.operator`) operation
    """

    """
    :param op: (:class:`pythonparser.ast.operator`) operation
    :param lhs: (:class:`Value`) left-hand operand
    :param rhs: (:class:`Value`) right-hand operand
    """
    def __init__(self, op, lhs, rhs, name=""):
        assert isinstance(op, ast.operator)
        assert isinstance(lhs, Value)
        assert isinstance(rhs, Value)
        assert lhs.type == rhs.type
        super().__init__([lhs, rhs], lhs.type, name)
        self.op = op

    def opcode(self):
        return "arith({})".format(type(self.op).__name__)

    def lhs(self):
        return self.operands[0]

    def rhs(self):
        return self.operands[1]

class Compare(Instruction):
    """
    A comparison operation on numbers.

    :ivar op: (:class:`pythonparser.ast.cmpop`) operation
    """

    """
    :param op: (:class:`pythonparser.ast.cmpop`) operation
    :param lhs: (:class:`Value`) left-hand operand
    :param rhs: (:class:`Value`) right-hand operand
    """
    def __init__(self, op, lhs, rhs, name=""):
        assert isinstance(op, ast.cmpop)
        assert isinstance(lhs, Value)
        assert isinstance(rhs, Value)
        assert lhs.type == rhs.type
        super().__init__([lhs, rhs], builtins.TBool(), name)
        self.op = op

    def opcode(self):
        return "compare({})".format(type(self.op).__name__)

    def lhs(self):
        return self.operands[0]

    def rhs(self):
        return self.operands[1]

class Builtin(Instruction):
    """
    A builtin operation. Similar to a function call that
    never raises.

    :ivar op: (string) operation name
    """

    """
    :param op: (string) operation name
    """
    def __init__(self, op, operands, typ, name=""):
        assert isinstance(op, str)
        for operand in operands: assert isinstance(operand, Value)
        super().__init__(operands, typ, name)
        self.op = op

    def opcode(self):
        return "builtin({})".format(self.op)

class Closure(Instruction):
    """
    A closure creation operation.

    :ivar target_function: (:class:`Function`) function to invoke
    """

    """
    :param func: (:class:`Function`) function
    :param env: (:class:`Value`) outer environment
    """
    def __init__(self, func, env, name=""):
        assert isinstance(func, Function)
        assert isinstance(env, Value)
        assert is_environment(env.type)
        super().__init__([env], func.type, name)
        self.target_function = func

    def opcode(self):
        return "closure({})".format(self.target_function.name)

    def environment(self):
        return self.operands[0]

class Call(Instruction):
    """
    A function call operation.
    """

    """
    :param func: (:class:`Value`) function to call
    :param args: (list of :class:`Value`) function arguments
    """
    def __init__(self, func, args, name=""):
        assert isinstance(func, Value)
        for arg in args: assert isinstance(arg, Value)
        super().__init__([func] + args, func.type.ret, name)

    def opcode(self):
        return "call"

    def function(self):
        return self.operands[0]

    def arguments(self):
        return self.operands[1:]

class Select(Instruction):
    """
    A conditional select instruction.
    """

    """
    :param cond: (:class:`Value`) select condition
    :param if_true: (:class:`Value`) value of select if condition is truthful
    :param if_false: (:class:`Value`) value of select if condition is falseful
    """
    def __init__(self, cond, if_true, if_false, name=""):
        assert isinstance(cond, Value)
        assert isinstance(if_true, Value)
        assert isinstance(if_false, Value)
        assert if_true.type == if_false.type
        super().__init__([cond, if_true, if_false], if_true.type, name)

    def opcode(self):
        return "select"

    def condition(self):
        return self.operands[0]

    def if_true(self):
        return self.operands[1]

    def if_false(self):
        return self.operands[2]

class Branch(Terminator):
    """
    An unconditional branch instruction.
    """

    """
    :param target: (:class:`BasicBlock`) branch target
    """
    def __init__(self, target, name=""):
        assert isinstance(target, BasicBlock)
        super().__init__([target], builtins.TNone(), name)

    def opcode(self):
        return "branch"

    def target(self):
        return self.operands[0]

class BranchIf(Terminator):
    """
    A conditional branch instruction.
    """

    """
    :param cond: (:class:`Value`) branch condition
    :param if_true: (:class:`BasicBlock`) branch target if condition is truthful
    :param if_false: (:class:`BasicBlock`) branch target if condition is falseful
    """
    def __init__(self, cond, if_true, if_false, name=""):
        assert isinstance(cond, Value)
        assert isinstance(if_true, BasicBlock)
        assert isinstance(if_false, BasicBlock)
        super().__init__([cond, if_true, if_false], builtins.TNone(), name)

    def opcode(self):
        return "branchif"

    def condition(self):
        return self.operands[0]

    def if_true(self):
        return self.operands[1]

    def if_false(self):
        return self.operands[2]

class IndirectBranch(Terminator):
    """
    An indirect branch instruction.
    """

    """
    :param target: (:class:`Value`) branch target
    :param destinations: (list of :class:`BasicBlock`) all possible values of `target`
    """
    def __init__(self, target, destinations, name=""):
        assert isinstance(target, Value)
        assert all([isinstance(dest, BasicBlock) for dest in destinations])
        super().__init__([target] + destinations, builtins.TNone(), name)

    def opcode(self):
        return "indirectbranch"

    def target(self):
        return self.operands[0]

    def destinations(self):
        return self.operands[1:]

    def add_destination(self, destination):
        self.operands.append(destination)

    def _operands_as_string(self):
        return "{}, [{}]".format(self.operands[0].as_operand(),
                                 ", ".join([dest.as_operand() for dest in self.operands[1:]]))

class Return(Terminator):
    """
    A return instruction.
    """

    """
    :param value: (:class:`Value`) return value
    """
    def __init__(self, value, name=""):
        assert isinstance(value, Value)
        super().__init__([value], builtins.TNone(), name)

    def opcode(self):
        return "return"

    def value(self):
        return self.operands[0]

class Unreachable(Terminator):
    """
    An instruction used to mark unreachable branches.
    """

    """
    :param target: (:class:`BasicBlock`) branch target
    """
    def __init__(self, name=""):
        super().__init__([], builtins.TNone(), name)

    def opcode(self):
        return "unreachable"

class Raise(Terminator):
    """
    A raise instruction.
    """

    """
    :param value: (:class:`Value`) exception value
    """
    def __init__(self, value, name=""):
        assert isinstance(value, Value)
        super().__init__([value], builtins.TNone(), name)

    def opcode(self):
        return "raise"

    def value(self):
        return self.operands[0]

class Invoke(Terminator):
    """
    A function call operation that supports exception handling.
    """

    """
    :param func: (:class:`Value`) function to call
    :param args: (list of :class:`Value`) function arguments
    :param normal: (:class:`BasicBlock`) normal target
    :param exn: (:class:`BasicBlock`) exceptional target
    """
    def __init__(self, func, args, normal, exn, name=""):
        assert isinstance(func, Value)
        for arg in args: assert isinstance(arg, Value)
        assert isinstance(normal, BasicBlock)
        assert isinstance(exn, BasicBlock)
        super().__init__([func] + args + [normal, exn], func.type.ret, name)

    def opcode(self):
        return "invoke"

    def function(self):
        return self.operands[0]

    def arguments(self):
        return self.operands[1:-2]

    def normal_target(self):
        return self.operands[-2]

    def exception_target(self):
        return self.operands[-1]

    def _operands_as_string(self):
        result = ", ".join([operand.as_operand() for operand in self.operands[:-2]])
        result += " to {} unwind {}".format(self.operands[-2].as_operand(),
                                            self.operands[-1].as_operand())
        return result

class LandingPad(Terminator):
    """
    An instruction that gives an incoming exception a name and
    dispatches it according to its type.

    Once dispatched, the exception should be cast to its proper
    type by calling the "exncast" builtin on the landing pad value.

    :ivar types: (a list of :class:`builtins.TException`)
        exception types corresponding to the basic block operands
    """

    def __init__(self, name=""):
        super().__init__([], builtins.TException(), name)
        self.types = []

    def add_clause(self, target, typ):
        assert isinstance(target, BasicBlock)
        assert builtins.is_exception(typ)
        self.operands.append(target)
        self.types.append(typ.find())

    def opcode(self):
        return "landingpad"

    def _operands_as_string(self):
        table = []
        for typ, target in zip(self.types, self.operands):
            table.append("{} => {}".format(types.TypePrinter().name(typ), target.as_operand()))
        return "[{}]".format(", ".join(table))
