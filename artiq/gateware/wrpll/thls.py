import inspect
import ast
from copy import copy


class Isn:
    def __init__(self, immediate=None, inputs=None, outputs=None):
        if inputs is None:
            inputs = []
        if outputs is None:
            outputs = []
        self.immediate = immediate
        self.inputs = inputs
        self.outputs = outputs

    def __repr__(self):
        r = "<"
        r += self.__class__.__name__
        if self.immediate is not None:
            r += " (" + str(self.immediate) + ")"
        for inp in self.inputs:
            r += " r" + str(inp)
        if self.outputs:
            r += " ->"
            for outp in self.outputs:
                r += " r" + str(outp)
        r += ">"
        return r


class NopIsn(Isn):
    opcode = 0

class AddIsn(Isn):
    opcode = 1

class SubIsn(Isn):
    opcode = 2

class MulIsn(Isn):
    opcode = 3

class ShiftIsn(Isn):
    opcode = 4

class CopyIsn(Isn):
    opcode = 5

class InputIsn(Isn):
    opcode = 6

class OutputIsn(Isn):
    opcode = 7


class ASTCompiler:
    def __init__(self):
        self.program = []
        self.data = []
        self.next_ssa_reg = -1
        self.constants = dict()
        self.names = dict()
        self.globals = dict()

    def get_ssa_reg(self):
        r = self.next_ssa_reg
        self.next_ssa_reg -= 1
        return r

    def add_global(self, name):
        r = len(self.data)
        self.data.append(0)
        self.names[name] = r
        self.globals[name] = r
        return r

    def input(self, name):
        target = self.get_ssa_reg()
        self.program.append(InputIsn(outputs=[target]))
        self.names[name] = target

    def emit(self, node):
        if isinstance(node, ast.BinOp):
            left = self.emit(node.left)
            right = self.emit(node.right)
            if isinstance(node.op, ast.Add):
                cls = AddIsn
            elif isinstance(node.op, ast.Sub):
                cls = SubIsn
            elif isinstance(node.op, ast.Mult):
                cls = MulIsn
            else:
                raise NotImplementedError
            output = self.get_ssa_reg()
            self.program.append(cls(inputs=[left, right], outputs=[output]))
            return output
        elif isinstance(node, ast.Num):
            if node.n in self.constants:
                return self.constants[node.n]
            else:
                r = len(self.data)
                self.data.append(node.n)
                self.constants[node.n] = r
                return r
        elif isinstance(node, ast.Name):
            return self.names[node.id]
        elif isinstance(node, ast.Assign):
            output = self.emit(node.value)
            for target in node.targets:
                assert isinstance(target, ast.Name)
                self.names[target.id] = output
        elif isinstance(node, ast.Return):
            value = self.emit(node.value)
            self.program.append(OutputIsn(inputs=[value]))
        elif isinstance(node, ast.Global):
            pass
        else:
            raise NotImplementedError


class Processor:
    def __init__(self, data_width=32, multiplier_stages=2):
        self.data_width = data_width
        self.multiplier_stages = multiplier_stages
        self.program_rom_size = None
        self.data_ram_size = None
        self.opcode_bits = 3
        self.reg_bits = None

    def get_instruction_latency(self, isn):
        return {
            AddIsn: 2,
            SubIsn: 2,
            MulIsn: 1 + self.multiplier_stages,
            ShiftIsn: 2,
            CopyIsn: 1,
            InputIsn: 1
        }[isn.__class__]

    def encode_instruction(self, isn, exit):
        opcode = isn.opcode
        if isn.immediate is not None:
            r0 = isn.immediate
            if len(isn.inputs) >= 1:
                r1 = isn.inputs[0]
            else:
                r1 = 0
        else:
            if len(isn.inputs) >= 1:
                r0 = isn.inputs[0]
            else:
                r0 = 0
            if len(isn.inputs) >= 2:
                r1 = isn.inputs[1]
            else:
                r1 = 0
        r = 0
        for value, bits in ((exit, self.reg_bits), (r1, self.reg_bits), (r0, self.reg_bits), (opcode, self.opcode_bits)):
            r <<= bits
            r |= value
        return r


class Scheduler:
    def __init__(self, processor, reserved_data, program):
        self.processor = processor
        self.reserved_data = reserved_data
        self.used_registers = set(range(self.reserved_data))
        self.exits = dict()
        self.program = program
        self.remaining = copy(program)
        self.output = []

    def allocate_register(self):
        r = min(set(range(max(self.used_registers) + 2)) - self.used_registers)
        self.used_registers.add(r)
        return r

    def free_register(self, r):
        assert r >= self.reserved_data
        self.used_registers.discard(r)

    def find_inputs(self, cycle, isn):
        mapped_inputs = []
        for inp in isn.inputs:
            if inp >= 0:
                mapped_inputs.append(inp)
            else:
                found = False
                for i in range(cycle):
                    if i in self.exits:
                        r, rm = self.exits[i]
                        if r == inp:
                            mapped_inputs.append(rm)
                            found = True
                            break
                if not found:
                    return None
        return mapped_inputs

    def schedule_one(self, isn):
        cycle = len(self.output)
        mapped_inputs = self.find_inputs(cycle, isn)
        if mapped_inputs is None:
            return False

        if isn.outputs:
            latency = self.processor.get_instruction_latency(isn)
            exit = cycle + latency
            if exit in self.exits:
                return False

        # Instruction can be scheduled

        self.remaining.remove(isn)            

        for inp, minp in zip(isn.inputs, mapped_inputs):
            can_free = inp < 0 and all(inp != rinp for risn in self.remaining for rinp in risn.inputs)
            if can_free:
                self.free_register(minp)

        if isn.outputs:
            assert len(isn.outputs) == 1
            output = self.allocate_register()
            self.exits[exit] = (isn.outputs[0], output)
        self.output.append(isn.__class__(immediate=isn.immediate, inputs=mapped_inputs))

        return True

    def schedule(self):
        while self.remaining:
            success = False
            for isn in self.remaining:
                if self.schedule_one(isn):
                    success = True
                    break
            if not success:
                self.output.append(NopIsn())
        self.output += [NopIsn()]*(max(self.exits.keys()) - len(self.output) + 1)
        return self.output


class CompiledProgram:
    def __init__(self, processor, program, exits, data, glbs):
        self.processor = processor
        self.program = program
        self.exits = exits
        self.data = data
        self.globals = glbs

    def pretty_print(self):
        for cycle, isn in enumerate(self.program):
            l = "{:4d} {:15}".format(cycle, str(isn))
            if cycle in self.exits:
                l += " -> r{}".format(self.exits[cycle])
            print(l)

    def dimension_memories(self):
        self.processor.program_rom_size = len(self.program)
        self.processor.data_ram_size = len(self.data)
        self.processor.reg_bits = (self.processor.data_ram_size - 1).bit_length()

    def encode(self):
        r = []
        for i, isn in enumerate(self.program):
            exit = self.exits.get(i, 0)
            r.append(self.processor.encode_instruction(isn, exit))
        return r


def compile(processor, function):
    node = ast.parse(inspect.getsource(function))
    assert isinstance(node, ast.Module)
    assert len(node.body) == 1
    node = node.body[0]
    assert isinstance(node, ast.FunctionDef)
    assert len(node.args.args) == 1
    arg = node.args.args[0].arg
    body = node.body
    
    astcompiler = ASTCompiler()
    for node in body:
        if isinstance(node, ast.Global):
            for name in node.names:
                astcompiler.add_global(name)
    arg_r = astcompiler.input(arg)
    for node in body:
        astcompiler.emit(node)
        if isinstance(node, ast.Return):
            break

    scheduler = Scheduler(processor, len(astcompiler.data), astcompiler.program)
    scheduler.schedule()

    return CompiledProgram(
        processor=processor,
        program=scheduler.output,
        exits={k: v[1] for k,v in scheduler.exits.items()},
        data=astcompiler.data,
        glbs=astcompiler.globals)


a = 0
b = 0
c = 0

def foo(x):
    global a, b, c
    c = b
    b = a
    a = x
    return 4748*a + 259*b - 155*c 


cp = compile(Processor(), foo)
cp.pretty_print()
cp.dimension_memories()
print(cp.encode())
