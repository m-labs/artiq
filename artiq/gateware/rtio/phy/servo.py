from migen import *

from artiq.gateware.rtio import rtlink


class RTServoCtrl(Module):
    """Per channel RTIO control interface"""
    def __init__(self, ctrl):
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(len(ctrl.profile) + 2))

        # # #

        self.comb += [
                ctrl.stb.eq(self.rtlink.o.stb),
                self.rtlink.o.busy.eq(0)
        ]
        self.sync.rio_phy += [
                If(self.rtlink.o.stb,
                    Cat(ctrl.en_out, ctrl.en_iir, ctrl.profile).eq(
                            self.rtlink.o.data)
                )
        ]


class RTServoMem(Module):
    """All-channel all-profile coefficient and state RTIO control
    interface."""
    def __init__(self, w, servo):
        m_coeff = servo.iir.m_coeff.get_port(write_capable=True,
                mode=READ_FIRST,
                we_granularity=w.coeff, clock_domain="rio")
        assert len(m_coeff.we) == 2
        m_state = servo.iir.m_state.get_port(write_capable=True,
                # mode=READ_FIRST,
                clock_domain="rio")
        self.specials += m_state, m_coeff

        # just expose the w.coeff (18) MSBs of state
        assert w.state >= w.coeff
        # ensure that we can split the coefficient storage correctly
        assert len(m_coeff.dat_w) == 2*w.coeff
        # ensure that the DDS word data fits into the coefficient mem
        assert w.coeff >= w.word

        # coeff, profile, channel, 2 mems, rw
        # this exceeds the 8-bit RTIO address, so we move the extra ("overflow")
        # address bits into data.
        internal_address_width = 3 + w.profile + w.channel + 1 + 1
        rtlink_address_width = min(8, internal_address_width)
        overflow_address_width = internal_address_width - rtlink_address_width
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(
                data_width=overflow_address_width + w.coeff,
                address_width=rtlink_address_width,
                enable_replace=False),
            rtlink.IInterface(
                data_width=w.coeff,
                timestamped=False)
            )

        # # #

        config = Signal(w.coeff, reset=0)
        status = Signal(w.coeff)
        pad = Signal(6)
        self.comb += [
                Cat(servo.start).eq(config),
                status.eq(Cat(servo.start, servo.done, pad,
                    [_.clip for _ in servo.iir.ctrl]))
        ]

        assert len(self.rtlink.o.address) + len(self.rtlink.o.data) - w.coeff == (
                1 +  # we
                1 +  # state_sel
                1 +  # high_coeff
                len(m_coeff.adr))
        # ensure that we can fit config/status into the state address space
        assert len(self.rtlink.o.address) + len(self.rtlink.o.data) - w.coeff >= (
                1 +  # we
                1 +  # state_sel
                1 +  # config_sel
                len(m_state.adr))

        internal_address = Signal(internal_address_width)
        self.comb += internal_address.eq(Cat(self.rtlink.o.address,
                                             self.rtlink.o.data[w.coeff:]))

        coeff_data = Signal(w.coeff)
        self.comb += coeff_data.eq(self.rtlink.o.data[:w.coeff])

        we = internal_address[-1]
        state_sel = internal_address[-2]
        config_sel = internal_address[-3]
        high_coeff = internal_address[0]
        self.comb += [
                self.rtlink.o.busy.eq(0),
                m_coeff.adr.eq(internal_address[1:]),
                m_coeff.dat_w.eq(Cat(coeff_data, coeff_data)),
                m_coeff.we[0].eq(self.rtlink.o.stb & ~high_coeff &
                    we & ~state_sel),
                m_coeff.we[1].eq(self.rtlink.o.stb & high_coeff &
                    we & ~state_sel),
                m_state.adr.eq(internal_address),
                m_state.dat_w[w.state - w.coeff:].eq(self.rtlink.o.data),
                m_state.we.eq(self.rtlink.o.stb & we & state_sel & ~config_sel),
        ]
        read = Signal()
        read_state = Signal()
        read_high = Signal()
        read_config = Signal()
        self.sync.rio += [
                If(read,
                    read.eq(0)
                ),
                If(self.rtlink.o.stb,
                    read.eq(~we),
                    read_state.eq(state_sel),
                    read_high.eq(high_coeff),
                    read_config.eq(config_sel),
                )
        ]
        self.sync.rio_phy += [
                If(self.rtlink.o.stb & we & state_sel & config_sel,
                    config.eq(self.rtlink.o.data)
                ),
                If(read & read_config & read_state,
                    [_.clip.eq(0) for _ in servo.iir.ctrl]
                )
        ]
        self.comb += [
                self.rtlink.i.stb.eq(read),
                self.rtlink.i.data.eq(
                    Mux(read_state,
                        Mux(read_config,
                            status,
                            m_state.dat_r[w.state - w.coeff:]),
                        Mux(read_high,
                            m_coeff.dat_r[w.coeff:],
                            m_coeff.dat_r[:w.coeff])))
        ]
