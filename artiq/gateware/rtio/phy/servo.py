from migen import *

from artiq.gateware.rtio import rtlink


class RTServoCtrl(Module):
    """Per channel RTIO control interface"""
    def __init__(self, ctrl):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(len(ctrl)))

        # # #

        self.sync.rio += [
                If(self.rtlink.o.stb,
                    Cat(ctrl.profile, ctrl.en_out, ctrl.en_iir).eq(
                        self.rtlink.o.data),
                )
        ]
        self.comb += [
                ctrl.stb.eq(self.rtlink.o.stb)
        ]


class RTServoMem(Module):
    """All-channel all-profile coefficient and state RTIO control
    interface."""
    def __init__(self, w, servo):
        m_coeff = servo.m_coeff.get_port(write_capable=True,
                we_granularity=w.coeff)
        assert len(m_coeff.we) == 2
        m_state = servo.m_state.get_port(write_capable=True)
        self.specials += m_state, m_coeff

        assert w.coeff >= w.state
        assert w.coeff >= w.word

        self.rtlink = rtlink.Interface(
            rtlink.OInterface(
                w.coeff,
                # coeff, profile, channel, 2 mems, rw
                3 + w.profile + w.channel + 1 + 1,
                enable_replace=False),
            rtlink.IInterface(
                w.coeff,
                timestamped=False)
            )

        # # #

        we = self.rtlink.o.address[-1]
        state_sel = self.rtlink.o.address[-2]
        high_coeff = self.rtlink.o.address[0]
        self.comb += [
            self.rtlink.o.busy.eq(active),
                m_coeff.adr.eq(self.rtlink.o.address[1:]),
                m_coeff.dat_w.eq(Cat(self.rtlink.o.data, self.rtlink.o.data)),
                m_coeff.we[0].eq(self.rtlink.o.stb & ~high_coeff &
                    we & ~state_sel),
                m_coeff.we[1].eq(self.rtlink.o.stb & high_coeff &
                    we & ~state_sel),
                m_state.adr.eq(self.rtlink.o.address),
                m_state.dat_w.eq(self.rtlink.o.data << w.state - w.coeff),
                m_state.we.eq(self.rtlink.o.stb & we & state_sel),
        ]
        read = Signal()
        read_sel = Signal()
        read_high = Signal()
        self.sync.rio += [
                If(read,
                    read.eq(0)
                ),
                If(self.rtlink.o.stb & ~we,
                    read.eq(1),
                    read_sel.eq(state_sel),
                    read_high.eq(high_coeff),
                )
        ]
        self.comb += [
                self.rtlink.i.stb.eq(read),
                self.rtlink.i.data.eq(Mux(state_sel,
                    m_state.dat_r >> w.state - w.coeff,
                    Mux(read_high, m_coeff.dat_r[w.coeff:],
                        m_coeff.dat_r)))
        ]
