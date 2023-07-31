use core::cell::RefCell;
use kernel_proto as kern;
use sched::{Io, Mutex, Error as SchedError};
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
    use sched::{Io, Mutex};

    pub fn start(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::I2cStartRequest {
            destination: destination,
            busno: busno
        });
        match reply {
            Ok(drtioaux::Packet::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("i2c basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }

    pub fn restart(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::I2cRestartRequest {
            destination: destination,
            busno: busno
        });
        match reply {
            Ok(drtioaux::Packet::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("i2c basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }

    pub fn stop(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::I2cStopRequest  {
            destination: destination,
            busno: busno
        });
        match reply {
            Ok(drtioaux::Packet::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("i2c basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }

    pub fn write(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8, data: u8) -> Result<bool, &'static str> {
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::I2cWriteRequest {
            destination: destination,
            busno: busno,
            data: data
        });
        match reply {
            Ok(drtioaux::Packet::I2cWriteReply { succeeded, ack }) => {
                if succeeded { Ok(ack) } else { Err("i2c write reply error") }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }

    pub fn read(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8, ack: bool) -> Result<u8, &'static str> {
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::I2cReadRequest {
            destination: destination,
            busno: busno,
            ack: ack
        });
        match reply {
            Ok(drtioaux::Packet::I2cReadReply { succeeded, data }) => {
                if succeeded { Ok(data) } else { Err("i2c read reply error") }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }

    pub fn switch_select(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8, address: u8, mask: u8) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::I2cSwitchSelectRequest {
            destination: destination,
            busno: busno,
            address: address,
            mask: mask,
        });
        match reply {
            Ok(drtioaux::Packet::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("i2c basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }
}

#[cfg(has_drtio)]
mod remote_spi {
    use drtioaux;
    use rtio_mgt::drtio;
    use sched::{Io, Mutex};
    use board_artiq::spi;

    pub fn set_config(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8, flags: spi::Flags, length: u8) -> Result<(), &'static str> {
        let flags_u8 = (flags.spi_offline as u8) |
            (flags.spi_end as u8) << 1 |
            (flags.spi_cs_polarity as u8) << 3 |
            (flags.spi_clk_polarity as u8) << 4 |
            (flags.spi_clk_phase as u8) << 5 |
            (flags.spi_lsb_first as u8) << 6 |
            (flags.spi_half_duplex as u8) << 7;
        
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::SpiSetConfigRequest {
            destination: destination,
            busno: busno,
            flags: flags_u8,
            length: length,
        });
        match reply {
            Ok(drtioaux::Packet::SpiBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("spi basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }

    pub fn write(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8, data: u32) -> Result<(), &'static str> {
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::SpiWriteRequest {
            destination: destination,
            busno: busno,
            data: data
        });
        match reply {
            Ok(drtioaux::Packet::SpiBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err("spi basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }

    pub fn read(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, linkno: u8, destination: u8, busno: u8) -> Result<u32, &'static str> {
        let reply = drtio::aux_transact(io, aux_mutex, ddma_mutex, linkno, &drtioaux::Packet::SpiReadRequest {
            destination: destination,
            busno: busno
        });
        match reply {
            Ok(drtioaux::Packet::SpiReadReply { succeeded, data }) => {
                if succeeded { Ok(data) } else { Err("spi basic reply error") }
            }
            Ok(packet) => {
                error!("received unexpected aux packet: {:?}", packet);
                Err("received unexpected aux packet")
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(e)
            }
        }
    }
}


#[cfg(has_drtio)]
macro_rules! dispatch {
    ($io:ident, $aux_mutex:ident, $ddma_mutex:ident, $mod_local:ident, $mod_remote:ident, $routing_table:ident, $busno:expr, $func:ident $(, $param:expr)*) => {{
        let destination = ($busno >> 16) as u8;
        let busno = $busno as u8;
        let hop = $routing_table.0[destination as usize][0];
        if hop == 0 {
            $mod_local::$func(busno, $($param, )*)
        } else {
            let linkno = hop - 1;
            $mod_remote::$func($io, $aux_mutex, $ddma_mutex, linkno, destination, busno, $($param, )*)
        }
    }}
}

#[cfg(not(has_drtio))]
macro_rules! dispatch {
    ($io:ident, $aux_mutex:ident, $ddma_mutex:ident, $mod_local:ident, $mod_remote:ident, $routing_table:ident, $busno:expr, $func:ident $(, $param:expr)*) => {{
        let busno = $busno as u8;
        $mod_local::$func(busno, $($param, )*)
    }}
}

pub fn process_kern_hwreq(io: &Io, aux_mutex: &Mutex,
        ddma_mutex: &Mutex,
        _routing_table: &drtio_routing::RoutingTable,
        _up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
        request: &kern::Message) -> Result<bool, Error<SchedError>> {
    match request {
        &kern::RtioInitRequest => {
            info!("resetting RTIO");
            rtio_mgt::reset(io, aux_mutex, ddma_mutex);
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
            let succeeded = dispatch!(io, aux_mutex, ddma_mutex, local_i2c, remote_i2c, _routing_table, busno, start).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cRestartRequest { busno } => {
            let succeeded = dispatch!(io, aux_mutex, ddma_mutex, local_i2c, remote_i2c, _routing_table, busno, restart).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cStopRequest { busno } => {
            let succeeded = dispatch!(io, aux_mutex, ddma_mutex, local_i2c, remote_i2c, _routing_table, busno, stop).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cWriteRequest { busno, data } => {
            match dispatch!(io, aux_mutex, ddma_mutex, local_i2c, remote_i2c, _routing_table, busno, write, data) {
                Ok(ack) => kern_send(io, &kern::I2cWriteReply { succeeded: true, ack: ack }),
                Err(_) => kern_send(io, &kern::I2cWriteReply { succeeded: false, ack: false })
            }
        }
        &kern::I2cReadRequest { busno, ack } => {
            match dispatch!(io, aux_mutex, ddma_mutex, local_i2c, remote_i2c, _routing_table, busno, read, ack) {
                Ok(data) => kern_send(io, &kern::I2cReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(io, &kern::I2cReadReply { succeeded: false, data: 0xff })
            }
        }
        &kern::I2cSwitchSelectRequest { busno, address, mask } => {
            let succeeded = dispatch!(io, aux_mutex, ddma_mutex, local_i2c, remote_i2c, _routing_table, busno,
                switch_select, address, mask).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }

        &kern::SpiSetConfigRequest { busno, flags, length } => {
            let spi_flags = local_spi::Flags {
                spi_offline: flags & 1 << 0 != 0,
                spi_end: flags & 1 << 1 != 0,
                spi_cs_polarity: flags & 1 << 3 != 0,
                spi_clk_polarity: flags & 1 << 4 != 0,
                spi_clk_phase: flags & 1 << 5 != 0,
                spi_lsb_first: flags & 1 << 6 != 0,
                spi_half_duplex: flags & 1 << 7 != 0,
            };
            let succeeded = dispatch!(io, aux_mutex, ddma_mutex, local_spi, remote_spi, _routing_table, busno,
                set_config, spi_flags, length).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        },
        &kern::SpiWriteRequest { busno, data } => {
            let succeeded = dispatch!(io, aux_mutex, ddma_mutex, local_spi, remote_spi, _routing_table, busno,
                write, data).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        }
        &kern::SpiReadRequest { busno } => {
            match dispatch!(io, aux_mutex, ddma_mutex, local_spi, remote_spi, _routing_table, busno, read) {
                Ok(data) => kern_send(io, &kern::SpiReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(io, &kern::SpiReadReply { succeeded: false, data: 0 })
            }
        }

        _ => return Ok(false)
    }.and(Ok(true))
}
