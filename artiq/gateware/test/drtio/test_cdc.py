import unittest
import random

from migen import *

from artiq.gateware.drtio.cdc import CrossDomainRequest, CrossDomainNotification


class TestCDC(unittest.TestCase):
    def test_cross_domain_request(self):
        prng = random.Random(1)
        for sys_freq in 3, 6, 11:
            for srv_freq in 3, 6, 11:
                req_stb = Signal()
                req_ack = Signal()
                req_data = Signal(8)
                srv_stb = Signal()
                srv_ack = Signal()
                srv_data = Signal(8)
                test_seq = [93, 92, 19, 39, 91, 30, 12, 91, 38, 42]
                received_seq = []

                def requester():
                    for data in test_seq:
                        yield req_data.eq(data)
                        yield req_stb.eq(1)
                        yield
                        while not (yield req_ack):
                            yield
                        yield req_stb.eq(0)
                        for j in range(prng.randrange(0, 10)):
                            yield

                def server():
                    for i in range(len(test_seq)):
                        while not (yield srv_stb):
                            yield
                        received_seq.append((yield srv_data))
                        for j in range(prng.randrange(0, 10)):
                            yield
                        yield srv_ack.eq(1)
                        yield
                        yield srv_ack.eq(0)
                        yield

                dut = CrossDomainRequest("srv",
                         req_stb, req_ack, req_data,
                         srv_stb, srv_ack, srv_data)
                run_simulation(dut,
                    {"sys": requester(), "srv": server()},
                    {"sys": sys_freq, "srv": srv_freq})
                self.assertEqual(test_seq, received_seq)

    def test_cross_domain_notification(self):
        prng = random.Random(1)

        emi_stb = Signal()
        emi_data = Signal(8)
        rec_stb = Signal()
        rec_ack = Signal()
        rec_data = Signal(8)

        test_seq = [23, 12, 8, 3, 28]
        received_seq = []

        def emitter():
            for data in test_seq:
                yield emi_stb.eq(1)
                yield emi_data.eq(data)
                yield
                yield emi_stb.eq(0)
                yield
                for j in range(prng.randrange(0, 3)):
                    yield

        def receiver():
            for i in range(len(test_seq)):
                while not (yield rec_stb):
                    yield
                received_seq.append((yield rec_data))
                yield rec_ack.eq(1)
                yield
                yield rec_ack.eq(0)
                yield
                for j in range(prng.randrange(0, 3)):
                    yield

        dut = CrossDomainNotification("emi", "sys",
            emi_stb, emi_data,
            rec_stb, rec_ack, rec_data)
        run_simulation(dut,
            {"emi": emitter(), "sys": receiver()},
            {"emi": 13, "sys": 3})
        self.assertEqual(test_seq, received_seq)
