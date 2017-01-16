use std::io;
use board::csr;
use sched::{Io, UdpSocket};
use moninj_proto::*;

const MONINJ_TTL_OVERRIDE_ENABLE: u8 = 0;
const MONINJ_TTL_OVERRIDE_O: u8 = 1;
const MONINJ_TTL_OVERRIDE_OE: u8 = 2;

fn worker(socket: &mut UdpSocket) -> io::Result<()> {
    let mut buf = vec![0; 512];
    loop {
        let (size, addr) = try!(socket.recv_from(&mut buf));
        let request = try!(Request::read_from(&mut io::Cursor::new(&buf[..size])));
        trace!("{} -> {:?}", addr, request);

        match request {
            Request::Monitor => {
                #[cfg(has_dds)]
                let mut dds_ftws = [0u32; (csr::CONFIG_RTIO_DDS_COUNT as usize *
                                           csr::CONFIG_DDS_CHANNELS_PER_BUS as usize)];
                let mut reply = Reply::default();

                for i in 0..csr::CONFIG_RTIO_REGULAR_TTL_COUNT as u8 {
                    unsafe {
                        csr::rtio_moninj::mon_chan_sel_write(i);
                        csr::rtio_moninj::mon_probe_sel_write(0);
                        csr::rtio_moninj::mon_value_update_write(1);
                        if csr::rtio_moninj::mon_value_read() != 0 {
                            reply.ttl_levels |= 1 << i;
                        }
                        csr::rtio_moninj::mon_probe_sel_write(1);
                        csr::rtio_moninj::mon_value_update_write(1);
                        if csr::rtio_moninj::mon_value_read() != 0 {
                            reply.ttl_oes |= 1 << i;
                        }
                        csr::rtio_moninj::inj_chan_sel_write(i);
                        csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
                        if csr::rtio_moninj::inj_value_read() != 0 {
                            reply.ttl_overrides |= 1 << i;
                        }
                    }
                }

                #[cfg(has_dds)]
                {
                    reply.dds_rtio_first_channel = csr::CONFIG_RTIO_FIRST_DDS_CHANNEL as u16;
                    reply.dds_channels_per_bus = csr::CONFIG_DDS_CHANNELS_PER_BUS as u16;

                    for j in 0..csr::CONFIG_RTIO_DDS_COUNT {
                        unsafe {
                            csr::rtio_moninj::mon_chan_sel_write(
                                (csr::CONFIG_RTIO_FIRST_DDS_CHANNEL + j) as u8);
                            for i in 0..csr::CONFIG_DDS_CHANNELS_PER_BUS {
                                csr::rtio_moninj::mon_probe_sel_write(i as u8);
                                csr::rtio_moninj::mon_value_update_write(1);
                                dds_ftws[(csr::CONFIG_DDS_CHANNELS_PER_BUS * j + i) as usize] =
                                    csr::rtio_moninj::mon_value_read() as u32;
                            }
                        }
                    }
                    reply.dds_ftws = &dds_ftws;
                }

                trace!("{} <- {:?}", addr, reply);
                buf.clear();
                try!(reply.write_to(&mut buf));
                try!(socket.send_to(&buf, addr));
            },

            Request::TtlSet { channel, mode: TtlMode::Experiment } => {
                unsafe {
                    csr::rtio_moninj::inj_chan_sel_write(channel);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
                    csr::rtio_moninj::inj_value_write(0);
                }
            },

            Request::TtlSet { channel, mode: TtlMode::High } => {
                unsafe {
                    csr::rtio_moninj::inj_chan_sel_write(channel);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_O);
                    csr::rtio_moninj::inj_value_write(1);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_OE);
                    csr::rtio_moninj::inj_value_write(1);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
                    csr::rtio_moninj::inj_value_write(1);
                }
            },

            Request::TtlSet { channel, mode: TtlMode::Low } => {
                unsafe {
                    csr::rtio_moninj::inj_chan_sel_write(channel);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_O);
                    csr::rtio_moninj::inj_value_write(0);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_OE);
                    csr::rtio_moninj::inj_value_write(1);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
                    csr::rtio_moninj::inj_value_write(1);
                }
            },

            Request::TtlSet { channel, mode: TtlMode::Input } => {
                unsafe {
                    csr::rtio_moninj::inj_chan_sel_write(channel);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_OE);
                    csr::rtio_moninj::inj_value_write(0);
                    csr::rtio_moninj::inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
                    csr::rtio_moninj::inj_value_write(1);
                }
            }
        }
    }
}

pub fn thread(io: Io) {
    let mut socket = UdpSocket::with_buffer_size(&io, 1, 512);
    socket.bind(3250);

    loop {
        match worker(&mut socket) {
            Ok(())   => unreachable!(),
            Err(err) => error!("moninj aborted: {}", err)
        }
    }
}
