"""
The :mod:`ir` module contains the intermediate representation
of the ARTIQ compiler.
"""

from . import types, builtins

# Generic SSA IR classes

def escape_name(name):
    if all([isalnum(x) or x == "." for x in name]):
        return name
    else:
        return "\"{}\"".format(name.replace("\"", "\\\""))

class TSSABasicBlock(types.TMono):
    def __init__(self):
        super().__init__("ssa.basic_block")

class TSSAOption(types.TMono):
    def __init__(self, inner):
        super().__init__("ssa.option", {"inner": inner})

class Value:
    """
    An SSA value that keeps track of its uses.

    :ivar type: (:class:`.types.Type`) type of this value
    :ivar uses: (list of :class:`Value`) values that use this value
    """

    def __init__(self, typ):
        self.uses, self.type = set(), typ

    def replace_all_uses_with(self, value):
        for user in self.uses:
            user.replace_uses_of(self, value)

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
        super().__init__(operands, typ, name)
        self.basic_block = None

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

    def __str__(self):
        if builtins.is_none(self.type):
            prefix = ""
        else:
            prefix = "%{} = {} ".format(escape_name(self.name),
                                        types.TypePrinter().name(self.type))

        if any(self.operands):
            return "{} {} {}".format(prefix, self.opcode(),
                ", ".join([operand.as_operand() for operand in self.operands]))
        else:
            return "{} {}".format(prefix, self.opcode())

class Phi(Instruction):
    """
    An SSA instruction that joins data flow.

    Use :meth:`incoming` and :meth:`add_incoming` instead of
    directly reading :attr:`operands` or calling :meth:`set_operands`.
    """

    def __init__(self, typ, name=""):
        super().__init__(typ, name)

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
            operand_list = ["%{} => %{}".format(escape_name(block.name), escape_name(value.name))
                            for operand in self.operands]
            return "{} {} [{}]".format(prefix, self.opcode(), ", ".join(operand_list))

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
        super().__init__(TSSABasicBlock(), name)
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

    def prepend(self, insn):
        insn.set_basic_block(self)
        self.instructions.insert(0, insn)

    def append(self, insn):
        insn.set_basic_block(self)
        self.instructions.append(insn)

    def index(self, insn):
        return self.instructions.index(insn)

    def insert(self, before, insn):
        insn.set_basic_block(self)
        self.instructions.insert(self.index(before), insn)

    def remove(self, insn):
        insn._detach()
        self.instructions.remove(insn)

    def replace(self, insn, replacement):
        self.insert(insn, replacement)
        self.remove(insn)

    def terminator(self):
        assert isinstance(self.instructions[-1], Terminator)
        return self.instructions[-1]

    def successors(self):
        return self.terminator().successors()

    def predecessors(self):
        assert self.function is not None
        self.function.predecessors_of(self)

    def __str__(self):
        lines = ["{}:".format(escape_name(self.name))]
        for insn in self.instructions:
            lines.append(str(insn))
        return "\n".join(lines)

class Argument(NamedValue):
    """
    A function argument.
    """

    def __str__(self):
        return self.as_operand()

class Function(Value):
    """
    A function containing SSA IR.
    """

    def __init__(self, typ, name, arguments):
        self.type, self.name = typ, name
        self.arguments = []
        self.basic_blocks = set()
        self.names = set()
        self.set_arguments(arguments)

    def _remove_name(self, name):
        self.names.remove(name)

    def _add_name(self, base_name):
        name, counter = base_name, 1
        while name in self.names or name == "":
            if base_name == "":
                name = str(counter)
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
        self.basic_blocks.add(basic_blocks)

    def remove(self, basic_block):
        basic_block._detach()
        self.basic_block.remove(basic_block)

    def predecessors_of(self, successor):
        return set(block for block in self.basic_blocks if successor in block.successors())

    def as_operand(self):
        return "{} @{}".format(types.TypePrinter().name(self.type),
                               escape_name(self.name))

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
