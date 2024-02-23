use core::cell::RefCell;
use kernel_proto as kern;
use sched::{Io, Error as SchedError};
use session::{kern_acknowledge, kern_send, Error};
use rtio_mgt;
use urc::Urc;
use board_misoc::i2c as local_i2c;
use board_artiq::drtio_routing;
use board_artiq::spi as local_spi;

#[cfg(has_drtio)]
mod remote_i2c {
    use drtioaux;
    use rtio_mgt::drtio;
    use sched::Io;

    pub fn start(io: &Io, destination: u8, busno: u8) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true, 
            drtioaux::Payload::I2cStartRequest {
                busno: busno
            });
        match reply {
            Ok(drtioaux::Payload::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("i2c basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err("aux packet error")
            }
        }
    }

    pub fn restart(io: &Io, destination: u8, busno: u8) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true,
            drtioaux::Payload::I2cRestartRequest {
                busno: busno
            });
        match reply {
            Ok(drtioaux::Payload::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("i2c basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err("aux packet error")
            }
        }
    }

    pub fn stop(io: &Io, destination: u8, busno: u8) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true,
            drtioaux::Payload::I2cStopRequest  {
                busno: busno
            });
        match reply {
            Ok(drtioaux::Payload::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("i2c basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err("aux packet error")
            }
        }
    }

    pub fn write(io: &Io, destination: u8, busno: u8, data: u8) -> Result<bool, &'static str> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true, 
            drtioaux::Payload::I2cWriteRequest {
                busno: busno,
                data: data
            });
        match reply {
            Ok(drtioaux::Payload::I2cWriteReply { succeeded, ack }) => {
                if succeeded { Ok(ack) } else { Err("i2c write reply error") }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err("aux packet error")
            }
        }
    }

    pub fn read(io: &Io, destination: u8, busno: u8, ack: bool) -> Result<u8, &'static str> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true,
            drtioaux::Payload::I2cReadRequest {
                busno: busno,
                ack: ack
            });
        match reply {
            Ok(drtioaux::Payload::I2cReadReply { succeeded, data }) => {
                if succeeded { Ok(data) } else { Err("i2c read reply error") }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err("aux packet error")
            }
        }
    }

    pub fn switch_select(io: &Io, destination: u8, busno: u8, 
        address: u8, mask: u8) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true,
            drtioaux::Payload::I2cSwitchSelectRequest {
                busno: busno,
                address: address,
                mask: mask,
            });
        match reply {
            Ok(drtioaux::Payload::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("i2c basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err("aux packet error")
            }
        }
    }
}

#[cfg(has_drtio)]
mod remote_spi {
    use drtioaux;
    use rtio_mgt::drtio;
    use sched::Io;

    pub fn set_config(io: &Io, destination: u8,
        busno: u8, flags: u8, length: u8, div: u8, cs: u8
    ) -> Result<(), ()> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true,
            drtioaux::Payload::SpiSetConfigRequest {
            busno: busno,
            flags: flags,
            length: length,
            div: div,
            cs: cs
        });
        match reply {
            Ok(drtioaux::Payload::SpiBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err(()) }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err(())
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(())
            }
        }
    }

    pub fn write(io: &Io, destination: u8, busno: u8, data: u32) -> Result<(), ()> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true,
            drtioaux::Payload::SpiWriteRequest {
                busno: busno,
                data: data
        });
        match reply {
            Ok(drtioaux::Payload::SpiBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err(()) }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err(())
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(())
            }
        }
    }

    pub fn read(io: &Io, destination: u8, busno: u8
    ) -> Result<u32, ()> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true,
            drtioaux::Payload::SpiReadRequest {
                busno: busno
            });
        match reply {
            Ok(drtioaux::Payload::SpiReadReply { succeeded, data }) => {
                if succeeded { Ok(data) } else { Err(()) }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err(())
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(())
            }
        }
    }
}


#[cfg(has_drtio)]
macro_rules! dispatch {
    ($io:ident, $mod_local:ident, $mod_remote:ident, $routing_table:ident, $busno:expr, $func:ident $(, $param:expr)*) => {{
        let destination = ($busno >> 16) as u8;
        let busno = $busno as u8;
        let hop = $routing_table.0[destination as usize][0];
        if hop == 0 {
            $mod_local::$func(busno, $($param, )*)
        } else {
            $mod_remote::$func($io, destination, busno, $($param, )*)
        }
    }}
}

#[cfg(not(has_drtio))]
macro_rules! dispatch {
    ($io:ident, $mod_local:ident, $mod_remote:ident, $routing_table:ident, $busno:expr, $func:ident $(, $param:expr)*) => {{
        let busno = $busno as u8;
        $mod_local::$func(busno, $($param, )*)
    }}
}

pub fn process_kern_hwreq(io: &Io,
        _routing_table: &drtio_routing::RoutingTable,
        _up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
        request: &kern::Message) -> Result<bool, Error<SchedError>> {
    match request {
        &kern::RtioInitRequest => {
            info!("resetting RTIO");
            rtio_mgt::reset(io);
            kern_acknowledge()
        }

        &kern::RtioDestinationStatusRequest { destination: _destination } => {
            #[cfg(has_drtio)]
            let up = {
                let up_destinations = _up_destinations.borrow();
                up_destinations[_destination as usize]
            };
            #[cfg(not(has_drtio))]
            let up = true;
            kern_send(io, &kern::RtioDestinationStatusReply { up: up })
        }

        &kern::I2cStartRequest { busno } => {
            let succeeded = dispatch!(io, local_i2c, remote_i2c, _routing_table, busno, start).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cRestartRequest { busno } => {
            let succeeded = dispatch!(io, local_i2c, remote_i2c, _routing_table, busno, restart).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cStopRequest { busno } => {
            let succeeded = dispatch!(io, local_i2c, remote_i2c, _routing_table, busno, stop).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cWriteRequest { busno, data } => {
            match dispatch!(io, local_i2c, remote_i2c, _routing_table, busno, write, data) {
                Ok(ack) => kern_send(io, &kern::I2cWriteReply { succeeded: true, ack: ack }),
                Err(_) => kern_send(io, &kern::I2cWriteReply { succeeded: false, ack: false })
            }
        }
        &kern::I2cReadRequest { busno, ack } => {
            match dispatch!(io, local_i2c, remote_i2c, _routing_table, busno, read, ack) {
                Ok(data) => kern_send(io, &kern::I2cReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(io, &kern::I2cReadReply { succeeded: false, data: 0xff })
            }
        }
        &kern::I2cSwitchSelectRequest { busno, address, mask } => {
            let succeeded = dispatch!(io, local_i2c, remote_i2c, _routing_table, busno,
                switch_select, address, mask).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }

        &kern::SpiSetConfigRequest { busno, flags, length, div, cs } => {
            let succeeded = dispatch!(io, local_spi, remote_spi, _routing_table, busno,
                set_config, flags, length, div, cs).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        },
        &kern::SpiWriteRequest { busno, data } => {
            let succeeded = dispatch!(io, local_spi, remote_spi, _routing_table, busno,
                write, data).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        }
        &kern::SpiReadRequest { busno } => {
            match dispatch!(io, local_spi, remote_spi, _routing_table, busno, read) {
                Ok(data) => kern_send(io, &kern::SpiReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(io, &kern::SpiReadReply { succeeded: false, data: 0 })
            }
        }

        _ => return Ok(false)
    }.and(Ok(true))
}
