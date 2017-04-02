use std::io::{self, Read};
use std::btree_map::BTreeMap;

use sched::Io;
use sched::{TcpListener, TcpStream};
use board::{clock, csr};
#[cfg(has_drtio)]
use drtioaux;
#[cfg(has_drtio)]
use rtio_mgt;

use moninj_proto::*;


fn check_magic(stream: &mut TcpStream) -> io::Result<()> {
    const MAGIC: &'static [u8] = b"ARTIQ moninj\n";

    let mut magic: [u8; 13] = [0; 13];
    stream.read_exact(&mut magic)?;
    if magic != MAGIC {
        Err(io::Error::new(io::ErrorKind::InvalidData, "unrecognized magic"))
    } else {
        Ok(())
    }
}

#[cfg(has_rtio_moninj)]
fn read_probe_local(channel: u16, probe: u8) -> u32 {
    unsafe {
        csr::rtio_moninj::mon_chan_sel_write(channel as _);
        csr::rtio_moninj::mon_probe_sel_write(probe);
        csr::rtio_moninj::mon_value_update_write(1);
        csr::rtio_moninj::mon_value_read() as u32
    }
}

#[cfg(has_drtio)]
fn read_probe_drtio(channel: u16, probe: u8) -> u32 {
    if rtio_mgt::drtio::link_is_running() {
        let request = drtioaux::Packet::MonitorRequest { channel: channel, probe: probe };
        drtioaux::hw::send(&request).unwrap();
        match drtioaux::hw::recv_timeout(10) {
            Ok(drtioaux::Packet::MonitorReply { value }) => return value,
            Ok(_) => error!("received unexpected aux packet"),
            Err(e) => error!("aux packet error ({})", e)
        }
        0
    } else {
        0
    }
}

fn read_probe(channel: u32, probe: u8) -> u32 {
    #[cfg(has_rtio_moninj)]
    {
        if channel & 0xff0000 == 0 {
            return read_probe_local(channel as u16, probe)
        }
    }
    #[cfg(has_drtio)]
    {
        if channel & 0xff0000 != 0 {
            return read_probe_drtio(channel as u16, probe)
        }
    }
    error!("read_probe: unrecognized channel number {}", channel);
    0
}

#[cfg(has_rtio_moninj)]
fn inject_local(channel: u16, overrd: u8, value: u8) {
    unsafe {
        csr::rtio_moninj::inj_chan_sel_write(channel as _);
        csr::rtio_moninj::inj_override_sel_write(overrd);
        csr::rtio_moninj::inj_value_write(value);
    }
}

#[cfg(has_drtio)]
fn inject_drtio(channel: u16, overrd: u8, value: u8) {
    if rtio_mgt::drtio::link_is_running() {
        let request = drtioaux::Packet::InjectionRequest {
            channel: channel,
            overrd: overrd,
            value: value
        };
        drtioaux::hw::send(&request).unwrap();
    }
}

fn inject(channel: u32, overrd: u8, value: u8) {
    #[cfg(has_rtio_moninj)]
    {
        if channel & 0xff0000 == 0 {
            inject_local(channel as u16, overrd, value);
            return
        }
    }
    #[cfg(has_drtio)]
    {
        if channel & 0xff0000 != 0 {
            inject_drtio(channel as u16, overrd, value);
            return
        }
    }
    error!("inject: unrecognized channel number {}", channel);
}

#[cfg(has_rtio_moninj)]
fn read_injection_status_local(channel: u16, overrd: u8) -> u8 {
    unsafe {
        csr::rtio_moninj::inj_chan_sel_write(channel as _);
        csr::rtio_moninj::inj_override_sel_write(overrd);
        csr::rtio_moninj::inj_value_read()
    }
}

#[cfg(has_drtio)]
fn read_injection_status_drtio(channel: u16, overrd: u8) -> u8 {
    if rtio_mgt::drtio::link_is_running() {
        let request = drtioaux::Packet::InjectionStatusRequest {
            channel: channel,
            overrd: overrd
        };
        drtioaux::hw::send(&request).unwrap();
        match drtioaux::hw::recv_timeout(10) {
            Ok(drtioaux::Packet::InjectionStatusReply { value }) => return value,
            Ok(_) => error!("received unexpected aux packet"),
            Err(e) => error!("aux packet error ({})", e)
        }
        0
    } else {
        0
    }
}

fn read_injection_status(channel: u32, probe: u8) -> u8 {
    #[cfg(has_rtio_moninj)]
    {
        if channel & 0xff0000 == 0 {
            return read_injection_status_local(channel as u16, probe)
        }
    }
    #[cfg(has_drtio)]
    {
        if channel & 0xff0000 != 0 {
            return read_injection_status_drtio(channel as u16, probe)
        }
    }
    error!("read_injection_status: unrecognized channel number {}", channel);
    0
}

fn connection_worker(io: &Io, mut stream: &mut TcpStream) -> io::Result<()> {
    let mut watch_list = BTreeMap::new();
    let mut next_check = 0;

    check_magic(&mut stream)?;
    info!("new connection from {}", stream.remote_endpoint());

    loop {
        if stream.can_recv() {
            let request = HostMessage::read_from(stream)?;
            match request {
                HostMessage::Monitor { enable, channel, probe } => {
                    if enable {
                        let _ = watch_list.entry((channel, probe)).or_insert(None);
                    } else {
                        let _ = watch_list.remove(&(channel, probe));
                    }
                },
                HostMessage::Inject { channel, overrd, value } => inject(channel, overrd, value),
                HostMessage::GetInjectionStatus { channel, overrd } => {
                    let value = read_injection_status(channel, overrd);
                    let reply = DeviceMessage::InjectionStatus {
                        channel: channel,
                        overrd: overrd,
                        value: value
                    };
                    reply.write_to(stream)?;
                }
            }
        } else if !stream.may_recv() {
            return Ok(())
        }

        if clock::get_ms() > next_check {
            for (&(channel, probe), previous) in watch_list.iter_mut() {
                let current = read_probe(channel, probe);
                if previous.is_none() || (previous.unwrap() != current) {
                    let message = DeviceMessage::MonitorStatus {
                        channel: channel,
                        probe: probe,
                        value: current
                    };
                    message.write_to(stream)?;
                    *previous = Some(current);
                }
            }
            next_check = clock::get_ms() + 200;
        }

        io.relinquish().unwrap();
    }
}

pub fn thread(io: Io) {
    let listener = TcpListener::new(&io, 2047);
    listener.listen(1383).expect("moninj: cannot listen");

    loop {
        let stream = listener.accept().expect("moninj: cannot accept").into_handle();
        io.spawn(16384, move |io| {
            let mut stream = TcpStream::from_handle(&io, stream);
            match connection_worker(&io, &mut stream) {
                Ok(()) => {},
                Err(err) => error!("moninj aborted: {}", err)
            }
        });
    }
}
