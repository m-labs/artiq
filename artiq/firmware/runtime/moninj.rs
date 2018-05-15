use alloc::btree_map::BTreeMap;

use io::Error as IoError;
use moninj_proto::*;
use sched::{Io, TcpListener, TcpStream, Error as SchedError};
use board_misoc::{clock, csr};
#[cfg(has_drtio)]
use drtioaux;

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
fn read_probe_drtio(nodeno: u8, channel: u16, probe: u8) -> u32 {
    let request = drtioaux::Packet::MonitorRequest { channel: channel, probe: probe };
    match drtioaux::send(nodeno, &request) {
        Ok(_) => (),
        Err(e) => {
            error!("aux packet error ({})", e);
            return 0;
        }
    }
    match drtioaux::recv_timeout(nodeno, None) {
        Ok(drtioaux::Packet::MonitorReply { value }) => return value,
        Ok(_) => error!("received unexpected aux packet"),
        Err(e) => error!("aux packet error ({})", e)
    }
    0
}

fn read_probe(channel: u32, probe: u8) -> u32 {
    let nodeno = (channel >> 16) as u8;
    let node_channel = channel as u16;
    #[cfg(has_rtio_moninj)]
    {
        if nodeno == 0 {
            return read_probe_local(node_channel, probe)
        }
    }
    #[cfg(has_drtio)]
    {
        if nodeno != 0 {
            return read_probe_drtio(nodeno, node_channel, probe)
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
fn inject_drtio(nodeno: u8, channel: u16, overrd: u8, value: u8) {
    let request = drtioaux::Packet::InjectionRequest {
        channel: channel,
        overrd: overrd,
        value: value
    };
    match drtioaux::send(nodeno, &request) {
        Ok(_) => (),
        Err(e) => error!("aux packet error ({})", e)
    }
}

fn inject(channel: u32, overrd: u8, value: u8) {
    let nodeno = (channel >> 16) as u8;
    let node_channel = channel as u16;
    #[cfg(has_rtio_moninj)]
    {
        if nodeno == 0 {
            inject_local(node_channel, overrd, value);
            return
        }
    }
    #[cfg(has_drtio)]
    {
        if nodeno != 0 {
            inject_drtio(nodeno, node_channel, overrd, value);
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
fn read_injection_status_drtio(nodeno: u8, channel: u16, overrd: u8) -> u8 {
    let request = drtioaux::Packet::InjectionStatusRequest {
        channel: channel,
        overrd: overrd
    };
    match drtioaux::send(nodeno, &request) {
        Ok(_) => (),
        Err(e) => {
            error!("aux packet error ({})", e);
            return 0;
        }
    }
    match drtioaux::recv_timeout(nodeno, None) {
        Ok(drtioaux::Packet::InjectionStatusReply { value }) => return value,
        Ok(_) => error!("received unexpected aux packet"),
        Err(e) => error!("aux packet error ({})", e)
    }
    0
}

fn read_injection_status(channel: u32, probe: u8) -> u8 {
    let nodeno = (channel >> 16) as u8;
    let node_channel = channel as u16;
    #[cfg(has_rtio_moninj)]
    {
        if nodeno == 0 {
            return read_injection_status_local(node_channel, probe)
        }
    }
    #[cfg(has_drtio)]
    {
        if nodeno != 0 {
            return read_injection_status_drtio(nodeno, node_channel, probe)
        }
    }
    error!("read_injection_status: unrecognized channel number {}", channel);
    0
}

fn connection_worker(io: &Io, mut stream: &mut TcpStream) -> Result<(), Error<SchedError>> {
    let mut watch_list = BTreeMap::new();
    let mut next_check = 0;

    read_magic(&mut stream)?;
    info!("new connection from {}", stream.remote_endpoint());

    loop {
        if stream.can_recv() {
            let request = HostMessage::read_from(stream)?;
            trace!("moninj<-host {:?}", request);

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

                    trace!("moninj->host {:?}", reply);
                    reply.write_to(stream)?;
                }
            }
        } else if !stream.may_recv() {
            return Ok(())
        }

        if clock::get_ms() > next_check {
            for (&(channel, probe), previous) in watch_list.iter_mut() {
                let current = read_probe(channel, probe);
                if previous.is_none() || previous.unwrap() != current {
                    let message = DeviceMessage::MonitorStatus {
                        channel: channel,
                        probe: probe,
                        value: current
                    };

                    trace!("moninj->host {:?}", message);
                    message.write_to(stream)?;

                    *previous = Some(current);
                }
            }
            next_check = clock::get_ms() + 200;
        }

        io.relinquish().map_err(|err| Error::Io(IoError::Other(err)))?;
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
