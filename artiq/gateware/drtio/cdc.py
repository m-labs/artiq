from migen import *

from migen.genlib.cdc import PulseSynchronizer


class CrossDomainRequest(Module):
    def __init__(self, domain,
                 req_stb, req_ack, req_data,
                 srv_stb, srv_ack, srv_data):
        dsync = getattr(self.sync, domain)

        request = PulseSynchronizer("sys", domain)
        reply = PulseSynchronizer(domain, "sys")
        self.submodules += request, reply

        ongoing = Signal()
        self.comb += request.i.eq(~ongoing & req_stb)
        self.sync += [
            req_ack.eq(reply.o),
            If(req_stb, ongoing.eq(1)),
            If(req_ack, ongoing.eq(0))
        ]
        if req_data is not None:
            req_data_r = Signal.like(req_data)
            req_data_r.attr.add("no_retiming")
            self.sync += If(req_stb, req_data_r.eq(req_data))
        dsync += [
            If(request.o, srv_stb.eq(1)),
            If(srv_ack, srv_stb.eq(0))
        ]
        if req_data is not None:
            dsync += If(request.o, srv_data.eq(req_data_r))
        self.comb += reply.i.eq(srv_stb & srv_ack)


class CrossDomainNotification(Module):
    def __init__(self, domain, rdomain,
                 emi_stb, emi_data,
                 rec_stb, rec_ack, rec_data):
        emi_data_r = Signal(len(emi_data))
        emi_data_r.attr.add("no_retiming")
        dsync = getattr(self.sync, domain)
        dsync += If(emi_stb, emi_data_r.eq(emi_data))

        ps = PulseSynchronizer(domain, rdomain)
        self.submodules += ps
        self.comb += ps.i.eq(emi_stb)
        rsync = getattr(self.sync, rdomain)
        rsync += [
            If(rec_ack, rec_stb.eq(0)),
            If(ps.o,
                rec_data.eq(emi_data_r),
                rec_stb.eq(1)
            )
        ]
