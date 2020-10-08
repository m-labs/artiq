import unittest

from migen import *

from artiq.gateware.drtio.wrpll import thls


a = 0

def simple_test(x):
    global a
    a = a + (x*4 >> 1)
    return a


class TestTHLS(unittest.TestCase):
    def test_thls(self):
        global a

        proc = thls.Processor()
        a = 0
        cp = thls.compile(proc, simple_test)
        print("Program:")
        cp.pretty_print()
        cp.dimension_processor()
        print("Encoded program:", cp.encode())
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

        send_list = [42, 40, 10, 10]
        receive_list = []

        run_simulation(proc_impl, [send_values(send_list), receive_values(receive_list.append)])
        print("Execution:", send_list, "->", receive_list)

        a = 0
        expected_list = [simple_test(x) for x in send_list]
        self.assertEqual(receive_list, expected_list)
