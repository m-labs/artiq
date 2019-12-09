import inspect
import ast
from copy import copy
import operator
from functools import reduce
from collections import OrderedDict

from migen import *
from migen.genlib.fsm import *


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

class MulShiftIsn(Isn):
    opcode = 3

# opcode = 4: MulShift with alternate shift

class MinIsn(Isn):
    opcode = 5

class MaxIsn(Isn):
    opcode = 6

class CopyIsn(Isn):
    opcode = 7

class InputIsn(Isn):
    opcode = 8

class OutputIsn(Isn):
    opcode = 9

class EndIsn(Isn):
    opcode = 10


class ASTCompiler:
    def __init__(self):
        self.program = []
        self.data = []
        self.next_ssa_reg = -1
        self.constants = dict()
        self.names = dict()
        self.globals = OrderedDict()

    def get_ssa_reg(self):
        r = self.next_ssa_reg
        self.next_ssa_reg -= 1
        return r

    def add_global(self, name):
        if name not in self.globals:
            r = len(self.data)
            self.data.append(0)
            self.names[name] = r
            self.globals[name] = r

    def input(self, name):
        target = self.get_ssa_reg()
        self.program.append(InputIsn(outputs=[target]))
        self.names[name] = target

    def emit(self, node):
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.RShift):
                if not isinstance(node.left, ast.BinOp) or not isinstance(node.left.op, ast.Mult):
                    raise NotImplementedError
                if not isinstance(node.right, ast.Num):
                    raise NotImplementedError
                left = self.emit(node.left.left)
                right = self.emit(node.left.right)
                cons = lambda **kwargs: MulShiftIsn(immediate=node.right.n, **kwargs)
            else:
                left = self.emit(node.left)
                right = self.emit(node.right)
                if isinstance(node.op, ast.Add):
                    cons = AddIsn
                elif isinstance(node.op, ast.Sub):
                    cons = SubIsn
                elif isinstance(node.op, ast.Mult):
                    cons = lambda **kwargs: MulShiftIsn(immediate=0, **kwargs)
                else:
                    raise NotImplementedError
            output = self.get_ssa_reg()
            self.program.append(cons(inputs=[left, right], outputs=[output]))
            return output
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise NotImplementedError
            funcname = node.func.id
            if node.keywords:
                raise NotImplementedError
            inputs = [self.emit(x) for x in node.args]
            if funcname == "min":
                cons = MinIsn
            elif funcname == "max":
                cons = MaxIsn
            else:
                raise NotImplementedError
            output = self.get_ssa_reg()
            self.program.append(cons(inputs=inputs, outputs=[output]))
            return output
        elif isinstance(node, (ast.Num, ast.UnaryOp)):
            if isinstance(node, ast.UnaryOp):
                if not isinstance(node.operand, ast.Num):
                    raise NotImplementedError
                if isinstance(node.op, ast.UAdd):
                    transform = lambda x: x
                elif isinstance(node.op, ast.USub):
                    transform = operator.neg
                elif isinstance(node.op, ast.Invert):
                    transform = operator.invert
                else:
                    raise NotImplementedError
                node = node.operand
            else:
                transform = lambda x: x
            n = transform(node.n)
            if n in self.constants:
                return self.constants[n]
            else:
                r = len(self.data)
                self.data.append(n)
                self.constants[n] = r
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
        self.multiplier_shifts = []
        self.program_rom_size = None
        self.data_ram_size = None
        self.opcode_bits = 4
        self.reg_bits = None

    def get_instruction_latency(self, isn):
        return {
            AddIsn: 2,
            SubIsn: 2,
            MulShiftIsn: 1 + self.multiplier_stages,
            MinIsn: 2,
            MaxIsn: 2,
            CopyIsn: 1,
            InputIsn: 1
        }[isn.__class__]

    def encode_instruction(self, isn, exit):
        opcode = isn.opcode
        if isn.immediate is not None and not isinstance(isn, MulShiftIsn):
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

    def instruction_bits(self):
        return 3*self.reg_bits + self.opcode_bits

    def implement(self, program, data):
        return ProcessorImpl(self, program, data)


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
            # check that exit slot is free
            latency = self.processor.get_instruction_latency(isn)
            exit = cycle + latency
            if exit in self.exits:
                return False

            # avoid RAW hazard with global writeback
            for output in isn.outputs:
                if output >= 0:
                    for risn in self.remaining:
                        for inp in risn.inputs:
                            if inp == output:
                                return False

        # Instruction can be scheduled

        self.remaining.remove(isn)            

        for inp, minp in zip(isn.inputs, mapped_inputs):
            can_free = inp < 0 and all(inp != rinp for risn in self.remaining for rinp in risn.inputs)
            if can_free:
                self.free_register(minp)

        if isn.outputs:
            assert len(isn.outputs) == 1
            if isn.outputs[0] < 0:
                output = self.allocate_register()
            else:
                output = isn.outputs[0]
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

    def dimension_processor(self):
        self.processor.program_rom_size = len(self.program)
        self.processor.data_ram_size = len(self.data)
        self.processor.reg_bits = (self.processor.data_ram_size - 1).bit_length()
        for isn in self.program:
            if isinstance(isn, MulShiftIsn) and isn.immediate not in self.processor.multiplier_shifts:
                self.processor.multiplier_shifts.append(isn.immediate)

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
    for glbl, location in astcompiler.globals.items():
        new_location = astcompiler.names[glbl]
        if new_location != location:
            astcompiler.program.append(CopyIsn(inputs=[new_location], outputs=[location]))

    scheduler = Scheduler(processor, len(astcompiler.data), astcompiler.program)
    scheduler.schedule()

    program = copy(scheduler.output)
    program.append(EndIsn())

    max_reg = max(max(max(isn.inputs + [0]) for isn in program), max(v[1] for k, v in scheduler.exits.items()))

    return CompiledProgram(
        processor=processor,
        program=program,
        exits={k: v[1] for k, v in scheduler.exits.items()},
        data=astcompiler.data + [0]*(max_reg - len(astcompiler.data) + 1),
        glbs=astcompiler.globals)


class BaseUnit(Module):
    def __init__(self, data_width):
        self.stb_i = Signal()
        self.i0 = Signal((data_width, True))
        self.i1 = Signal((data_width, True))
        self.stb_o = Signal()
        self.o = Signal((data_width, True))


class NopUnit(BaseUnit):
    pass


class OpUnit(BaseUnit):
    def __init__(self, op, data_width, stages):
        BaseUnit.__init__(self, data_width)

        o = op(self.i0, self.i1)
        stb_o = self.stb_i
        for i in range(stages):
            n_o = Signal(data_width)
            n_stb_o = Signal()
            self.sync += [
                n_o.eq(o),
                n_stb_o.eq(stb_o)
            ]
            o = n_o
            stb_o = n_stb_o
        self.comb += [
            self.o.eq(o),
            self.stb_o.eq(stb_o)
        ]


class SelectUnit(BaseUnit):
    def __init__(self, op, data_width):
        BaseUnit.__init__(self, data_width)

        self.sync += [
            self.stb_o.eq(self.stb_i),
            If(op(self.i0, self.i1),
                self.o.eq(self.i0)
            ).Else(
                self.o.eq(self.i1)
            )
        ]


class CopyUnit(BaseUnit):
    def __init__(self, data_width):
        BaseUnit.__init__(self, data_width)

        self.comb += [
            self.stb_o.eq(self.stb_i),
            self.o.eq(self.i0)
        ]


class InputUnit(BaseUnit):
    def __init__(self, data_width, input_stb, input):
        BaseUnit.__init__(self, data_width)
        self.buffer = Signal(data_width)

        self.comb += [
            self.stb_o.eq(self.stb_i),
            self.o.eq(self.buffer)
        ]


class OutputUnit(BaseUnit):
    def __init__(self, data_width, output_stb, output):
        BaseUnit.__init__(self, data_width)

        self.sync += [
            output_stb.eq(self.stb_i),
            output.eq(self.i0)
        ]


class ProcessorImpl(Module):
    def __init__(self, pd, program, data):
        self.input_stb = Signal()
        self.input = Signal((pd.data_width, True))

        self.output_stb = Signal()
        self.output = Signal((pd.data_width, True))

        self.busy = Signal()

        # # #

        program_mem = Memory(pd.instruction_bits(), pd.program_rom_size, init=program)
        data_mem0 = Memory(pd.data_width, pd.data_ram_size, init=data)
        data_mem1 = Memory(pd.data_width, pd.data_ram_size, init=data)
        self.specials += program_mem, data_mem0, data_mem1

        pc = Signal(pd.instruction_bits())
        pc_next = Signal.like(pc)
        pc_en = Signal()
        self.sync += pc.eq(pc_next)
        self.comb += [
            If(pc_en,
                pc_next.eq(pc + 1)
            ).Else(
                pc_next.eq(0)
            )
        ]
        program_mem_port = program_mem.get_port()
        self.specials += program_mem_port
        self.comb += program_mem_port.adr.eq(pc_next)

        s = 0
        opcode = Signal(pd.opcode_bits)
        self.comb += opcode.eq(program_mem_port.dat_r[s:s+pd.opcode_bits])
        s += pd.opcode_bits
        r0 = Signal(pd.reg_bits)
        self.comb += r0.eq(program_mem_port.dat_r[s:s+pd.reg_bits])
        s += pd.reg_bits
        r1 = Signal(pd.reg_bits)
        self.comb += r1.eq(program_mem_port.dat_r[s:s+pd.reg_bits])
        s += pd.reg_bits
        exit = Signal(pd.reg_bits)
        self.comb += exit.eq(program_mem_port.dat_r[s:s+pd.reg_bits])

        data_read_port0 = data_mem0.get_port()
        data_read_port1 = data_mem1.get_port()
        self.specials += data_read_port0, data_read_port1
        self.comb += [
            data_read_port0.adr.eq(r0),
            data_read_port1.adr.eq(r1)
        ]

        data_write_port = data_mem0.get_port(write_capable=True)
        data_write_port_dup = data_mem1.get_port(write_capable=True)
        self.specials += data_write_port, data_write_port_dup
        self.comb += [
            data_write_port_dup.we.eq(data_write_port.we),
            data_write_port_dup.adr.eq(data_write_port.adr),
            data_write_port_dup.dat_w.eq(data_write_port.dat_w),
            data_write_port.adr.eq(exit)
        ]

        nop = NopUnit(pd.data_width)
        adder = OpUnit(operator.add, pd.data_width, 1)
        subtractor = OpUnit(operator.sub, pd.data_width, 1)
        if pd.multiplier_shifts:
            if len(pd.multiplier_shifts) != 1:
                raise NotImplementedError
            multiplier = OpUnit(lambda a, b: a * b >> pd.multiplier_shifts[0],
                pd.data_width, pd.multiplier_stages)
        else:
            multiplier = NopUnit(pd.data_width)
        minu = SelectUnit(operator.lt, pd.data_width)
        maxu = SelectUnit(operator.gt, pd.data_width)
        copier = CopyUnit(pd.data_width)
        inu = InputUnit(pd.data_width, self.input_stb, self.input)
        outu = OutputUnit(pd.data_width, self.output_stb, self.output)
        units = [nop, adder, subtractor, multiplier, minu, maxu, copier, inu, outu]
        self.submodules += units

        for unit in units:
            self.sync += unit.stb_i.eq(0)
            self.comb += [
                unit.i0.eq(data_read_port0.dat_r),
                unit.i1.eq(data_read_port1.dat_r),
                If(unit.stb_o,
                    data_write_port.we.eq(1),
                    data_write_port.dat_w.eq(unit.o)
                )
            ]

        decode_table = [
            (NopIsn.opcode,            nop),
            (AddIsn.opcode,            adder),
            (SubIsn.opcode,            subtractor),
            (MulShiftIsn.opcode,       multiplier),
            (MulShiftIsn.opcode + 1,   multiplier),
            (MinIsn.opcode,            minu),
            (MaxIsn.opcode,            maxu),
            (CopyIsn.opcode,           copier),
            (InputIsn.opcode,          inu),
            (OutputIsn.opcode,         outu)
        ]
        for allocated_opcode, unit in decode_table:
            self.sync += If(pc_en & (opcode == allocated_opcode), unit.stb_i.eq(1))

        fsm = FSM()
        self.submodules += fsm
        fsm.act("IDLE",
            pc_en.eq(0),
            NextValue(inu.buffer, self.input),
            If(self.input_stb, NextState("PROCESSING"))
        )
        fsm.act("PROCESSING",
            self.busy.eq(1),
            pc_en.eq(1),
            If(opcode == EndIsn.opcode,
                pc_en.eq(0),
                NextState("IDLE")
            )
        )


def make(function, **kwargs):
    proc = Processor(**kwargs)
    cp = compile(proc, simple_test)
    cp.dimension_processor()
    return proc.implement(cp.encode(), cp.data)


a = 0
b = 0
c = 0

def foo(x):
    global a, b, c
    c = b
    b = a
    a = x
    return 4748*a + 259*b - 155*c 


def simple_test(x):
    global a
    a = a + (x*4 >> 1)
    return a


if __name__ == "__main__":
    proc = Processor()
    cp = compile(proc, simple_test)
    cp.pretty_print()
    cp.dimension_processor()
    print(cp.encode())
    proc_impl = proc.implement(cp.encode(), cp.data)

    def send_values(values):
        for value in values:
            yield proc_impl.input.eq(value)
            yield proc_impl.input_stb.eq(1)
            yield
            yield proc_impl.input.eq(0)
            yield proc_impl.input_stb.eq(0)
            yield
            while (yield proc_impl.busy):
                yield
    @passive
    def receive_values(callback):
        while True:
            while not (yield proc_impl.output_stb):
                yield
            callback((yield proc_impl.output))
            yield

    run_simulation(proc_impl, [send_values([42, 40, 10, 10]), receive_values(print)])
