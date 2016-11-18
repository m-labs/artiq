def set_dict(e, **k):
    for k, v in k.items():
        if isinstance(v, dict):
            yield from set_dict(getattr(e, k), **v)
        else:
            yield getattr(e, k).eq(v)


def xfer(dut, **kw):
    ep = []
    for e, v in kw.items():
        e = getattr(dut, e)
        yield from set_dict(e, **v)
        ep.append(e)
    for e in ep:
        yield e.stb.eq(1)
    while ep:
        yield
        for e in ep[:]:
            if hasattr(e, "busy") and (yield e.busy):
                raise ValueError(e, "busy")
            if not hasattr(e, "ack") or (yield e.ack):
                yield e.stb.eq(0)
                ep.remove(e)


def szip(*iters):
    active = {it: None for it in iters}
    while active:
        for it in list(active):
            while True:
                try:
                    val = it.send(active[it])
                except StopIteration:
                    del active[it]
                    break
                if val is None:
                    break
                else:
                    active[it] = (yield val)
        val = (yield None)
        for it in active:
            active[it] = val


def rtio_xfer(dut, **kwargs):
    yield from szip(*(
        xfer(dut.phys_named[k].rtlink, o={"data": v})
        for k, v in kwargs.items()))
