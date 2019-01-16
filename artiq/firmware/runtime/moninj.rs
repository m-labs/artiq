use alloc::btree_map::BTreeMap;
use core::cell::RefCell;

use io::Error as IoError;
use moninj_proto::*;
use sched::{Io, Mutex, TcpListener, TcpStream, Error as SchedError};
use urc::Urc;
use board_misoc::clock;
use board_artiq::drtio_routing;

#[cfg(has_rtio_moninj)]
mod local_moninj {
    use board_misoc::csr;

    pub fn read_probe(channel: u16, probe: u8) -> u32 {
        unsafe {
            csr::rtio_moninj::mon_chan_sel_write(channel as _);
            csr::rtio_moninj::mon_probe_sel_write(probe);
            csr::rtio_moninj::mon_value_update_write(1);
            csr::rtio_moninj::mon_value_read() as u32
        }
    }

    pub fn inject(channel: u16, overrd: u8, value: u8) {
        unsafe {
            csr::rtio_moninj::inj_chan_sel_write(channel as _);
            csr::rtio_moninj::inj_override_sel_write(overrd);
            csr::rtio_moninj::inj_value_write(value);
        }
    }

    pub fn read_injection_status(channel: u16, overrd: u8) -> u8 {
        unsafe {
            csr::rtio_moninj::inj_chan_sel_write(channel as _);
            csr::rtio_moninj::inj_override_sel_write(overrd);
            csr::rtio_moninj::inj_value_read()
        }
    }
}

#[cfg(not(has_rtio_moninj))]
mod local_moninj {
    pub fn read_probe(_channel: u16, _probe: u8) -> u32 { 0 }

    pub fn inject(_channel: u16, _overrd: u8, _value: u8) { }

    pub fn read_injection_status(_channel: u16, _overrd: u8) -> u8 { 0 }
}

#[cfg(has_drtio)]
mod remote_moninj {
    use drtioaux;
    use rtio_mgt::drtio;
    use sched::{Io, Mutex};

    pub fn read_probe(io: &Io, aux_mutex: &Mutex, linkno: u8, destination: u8, channel: u16, probe: u8) -> u32 {
        let reply = drtio::aux_transact(io, aux_mutex, linkno, &drtioaux::Packet::MonitorRequest { 
            destination: destination,
            channel: channel,
            probe: probe
        });
        match reply {
            Ok(drtioaux::Packet::MonitorReply { value }) => return value,
            Ok(packet) => error!("received unexpected aux packet: {:?}", packet),
            Err(e) => error!("aux packet error ({})", e)
        }
        0
    }

    pub fn inject(io: &Io, aux_mutex: &Mutex, linkno: u8, destination: u8, channel: u16, overrd: u8, value: u8) {
        let _lock = aux_mutex.lock(io).unwrap();
        drtioaux::send(linkno, &drtioaux::Packet::InjectionRequest {
            destination: destination,
            channel: channel,
            overrd: overrd,
            value: value
        }).unwrap();
    }

    pub fn read_injection_status(io: &Io, aux_mutex: &Mutex, linkno: u8, destination: u8, channel: u16, overrd: u8) -> u8 {
        let reply = drtio::aux_transact(io, aux_mutex, linkno, &drtioaux::Packet::InjectionStatusRequest {
            destination: destination,
            channel: channel,
            overrd: overrd
        });
        match reply {
            Ok(drtioaux::Packet::InjectionStatusReply { value }) => return value,
            Ok(packet) => error!("received unexpected aux packet: {:?}", packet),
            Err(e) => error!("aux packet error ({})", e)
        }
        0
    }
}

#[cfg(has_drtio)]
macro_rules! dispatch {
    ($io:ident, $aux_mutex:ident, $routing_table:ident, $channel:expr, $func:ident $(, $param:expr)*) => {{
        let destination = ($channel >> 16) as u8;
        let channel = $channel as u16;
        let hop = $routing_table.0[destination as usize][0];
        if hop == 0 {
            local_moninj::$func(channel, $($param, )*)
        } else {
            let linkno = hop - 1;
            remote_moninj::$func($io, $aux_mutex, linkno, destination, channel, $($param, )*)
        }
    }}
}

#[cfg(not(has_drtio))]
macro_rules! dispatch {
    ($io:ident, $aux_mutex:ident, $routing_table:ident, $channel:expr, $func:ident $(, $param:expr)*) => {{
        let channel = $channel as u16;
        local_moninj::$func(channel, $($param, )*)
    }}
}

fn connection_worker(io: &Io, _aux_mutex: &Mutex, _routing_table: &drtio_routing::RoutingTable,
        mut stream: &mut TcpStream) -> Result<(), Error<SchedError>> {
    let mut probe_watch_list = BTreeMap::new();
    let mut inject_watch_list = BTreeMap::new();
    let mut next_check = 0;

    read_magic(&mut stream)?;
    info!("new connection from {}", stream.remote_endpoint());

    loop {
        if stream.can_recv() {
            let request = HostMessage::read_from(stream)?;
            trace!("moninj<-host {:?}", request);

            match request {
                HostMessage::MonitorProbe { enable, channel, probe } => {
                    if enable {
                        let _ = probe_watch_list.entry((channel, probe)).or_insert(None);
                    } else {
                        let _ = probe_watch_list.remove(&(channel, probe));
                    }
                },
                HostMessage::MonitorInjection { enable, channel, overrd } => {
                    if enable {
                        let _ = inject_watch_list.entry((channel, overrd)).or_insert(None);
                    } else {
                        let _ = inject_watch_list.remove(&(channel, overrd));
                    }
                },
                HostMessage::Inject { channel, overrd, value } => dispatch!(io, _aux_mutex, _routing_table, channel, inject, overrd, value),
                HostMessage::GetInjectionStatus { channel, overrd } => {
                    let value = dispatch!(io, _aux_mutex, _routing_table, channel, read_injection_status, overrd);
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
            for (&(channel, probe), previous) in probe_watch_list.iter_mut() {
                let current = dispatch!(io, _aux_mutex, _routing_table, channel, read_probe, probe);
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
            for (&(channel, overrd), previous) in inject_watch_list.iter_mut() {
                let current = dispatch!(io, _aux_mutex, _routing_table, channel, read_injection_status, overrd);
                if previous.is_none() || previous.unwrap() != current {
                    let message = DeviceMessage::InjectionStatus {
                        channel: channel,
                        overrd: overrd,
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

pub fn thread(io: Io, aux_mutex: &Mutex, routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>) {
    let listener = TcpListener::new(&io, 2047);
    listener.listen(1383).expect("moninj: cannot listen");

    loop {
        let aux_mutex = aux_mutex.clone();
        let routing_table = routing_table.clone();
        let stream = listener.accept().expect("moninj: cannot accept").into_handle();
        io.spawn(16384, move |io| {
            let routing_table = routing_table.borrow();
            let mut stream = TcpStream::from_handle(&io, stream);
            match connection_worker(&io, &aux_mutex, &routing_table, &mut stream) {
                Ok(()) => {},
                Err(err) => error!("moninj aborted: {}", err)
            }
        });
    }
}
