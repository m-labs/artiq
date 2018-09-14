use kernel_proto as kern;
use sched::{Io, Error as SchedError};
use session::{kern_acknowledge, kern_send, Error};
use rtio_mgt;
use board_artiq::drtio_routing;
use board_artiq::i2c as local_i2c;
use board_artiq::spi as local_spi;

#[cfg(has_drtio)]
mod remote_i2c {
    use drtioaux;

    fn basic_reply(linkno: u8) -> Result<(), ()> {
        match drtioaux::recv_timeout(linkno, None) {
            Ok(drtioaux::Packet::I2cBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err(()) }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
                Err(())
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(())
            }
        }
    }

    pub fn start(linkno: u8, destination: u8, busno: u8) -> Result<(), ()> {
        let request = drtioaux::Packet::I2cStartRequest {
            destination: destination,
            busno: busno
        };
        if drtioaux::send(linkno, &request).is_err() {
            return Err(())
        }
        basic_reply(linkno)
    }

    pub fn restart(linkno: u8, destination: u8, busno: u8) -> Result<(), ()> {
        let request = drtioaux::Packet::I2cRestartRequest {
            destination: destination,
            busno: busno
        };
        if drtioaux::send(linkno, &request).is_err() {
            return Err(())
        }
        basic_reply(linkno)
    }

    pub fn stop(linkno: u8, destination: u8, busno: u8) -> Result<(), ()> {
        let request = drtioaux::Packet::I2cStopRequest  {
            destination: destination,
            busno: busno
        };
        if drtioaux::send(linkno, &request).is_err() {
            return Err(())
        }
        basic_reply(linkno)
    }

    pub fn write(linkno: u8, destination: u8, busno: u8, data: u8) -> Result<bool, ()> {
        let request = drtioaux::Packet::I2cWriteRequest {
            destination: destination,
            busno: busno,
            data: data
        };
        if drtioaux::send(linkno, &request).is_err() {
            return Err(())
        }
        match drtioaux::recv_timeout(linkno, None) {
            Ok(drtioaux::Packet::I2cWriteReply { succeeded, ack }) => {
                if succeeded { Ok(ack) } else { Err(()) }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
                Err(())
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(())
            }
        }
    }

    pub fn read(linkno: u8, destination: u8, busno: u8, ack: bool) -> Result<u8, ()> {
        let request = drtioaux::Packet::I2cReadRequest {
            destination: destination,
            busno: busno,
            ack: ack
        };
        if drtioaux::send(linkno, &request).is_err() {
            return Err(())
        }
        match drtioaux::recv_timeout(linkno, None) {
            Ok(drtioaux::Packet::I2cReadReply { succeeded, data }) => {
                if succeeded { Ok(data) } else { Err(()) }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
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
mod remote_spi {
    use drtioaux;

    fn basic_reply(linkno: u8) -> Result<(), ()> {
        match drtioaux::recv_timeout(linkno, None) {
            Ok(drtioaux::Packet::SpiBasicReply { succeeded }) => {
                if succeeded { Ok(()) } else { Err(()) }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
                Err(())
            }
            Err(e) => {
                error!("aux packet error ({})", e);
                Err(())
            }
        }
    }

    pub fn set_config(linkno: u8, destination: u8, busno: u8, flags: u8, length: u8, div: u8, cs: u8) -> Result<(), ()> {
        let request = drtioaux::Packet::SpiSetConfigRequest {
            destination: destination,
            busno: busno,
            flags: flags,
            length: length,
            div: div,
            cs: cs
        };
        if drtioaux::send(linkno, &request).is_err() {
            return Err(())
        }
        basic_reply(linkno)
    }

    pub fn write(linkno: u8, destination: u8, busno: u8, data: u32) -> Result<(), ()> {
        let request = drtioaux::Packet::SpiWriteRequest {
            destination: destination,
            busno: busno,
            data: data
        };
        if drtioaux::send(linkno, &request).is_err() {
            return Err(())
        }
        basic_reply(linkno)
    }

    pub fn read(linkno: u8, destination: u8, busno: u8) -> Result<u32, ()> {
        let request = drtioaux::Packet::SpiReadRequest {
            destination: destination,
            busno: busno
        };
        if drtioaux::send(linkno, &request).is_err() {
            return Err(())
        }
        match drtioaux::recv_timeout(linkno, None) {
            Ok(drtioaux::Packet::SpiReadReply { succeeded, data }) => {
                if succeeded { Ok(data) } else { Err(()) }
            }
            Ok(_) => {
                error!("received unexpected aux packet");
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
    ($mod_local:ident, $mod_remote:ident, $routing_table:ident, $busno:expr, $func:ident $(, $param:expr)*) => {{
        let destination = ($busno >> 16) as u8;
        let busno = $busno as u8;
        let hop = $routing_table.0[destination as usize][0];
        if hop == 0 {
            $mod_local::$func(busno, $($param, )*)
        } else {
            let linkno = hop - 1;
            $mod_remote::$func(linkno, destination, busno, $($param, )*)
        }
    }}
}

#[cfg(not(has_drtio))]
macro_rules! dispatch {
    ($mod_local:ident, $mod_remote:ident, $routing_table:ident, $busno:expr, $func:ident $(, $param:expr)*) => {{
        let busno = $busno as u8;
        $mod_local::$func(busno, $($param, )*)
    }}
}

pub fn process_kern_hwreq(io: &Io, _routing_table: &drtio_routing::RoutingTable,
        request: &kern::Message) -> Result<bool, Error<SchedError>> {
    match request {
        &kern::RtioInitRequest => {
            info!("resetting RTIO");
            rtio_mgt::init_core(false);
            kern_acknowledge()
        }

        &kern::DrtioLinkStatusRequest { linkno } => {
            let up = rtio_mgt::drtio::link_up(linkno);
            kern_send(io, &kern::DrtioLinkStatusReply { up: up })
        }

        &kern::I2cStartRequest { busno } => {
            let succeeded = dispatch!(local_i2c, remote_i2c, _routing_table, busno, start).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cRestartRequest { busno } => {
            let succeeded = dispatch!(local_i2c, remote_i2c, _routing_table, busno, restart).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cStopRequest { busno } => {
            let succeeded = dispatch!(local_i2c, remote_i2c, _routing_table, busno, stop).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cWriteRequest { busno, data } => {
            match dispatch!(local_i2c, remote_i2c, _routing_table, busno, write, data) {
                Ok(ack) => kern_send(io, &kern::I2cWriteReply { succeeded: true, ack: ack }),
                Err(_) => kern_send(io, &kern::I2cWriteReply { succeeded: false, ack: false })
            }
        }
        &kern::I2cReadRequest { busno, ack } => {
            match dispatch!(local_i2c, remote_i2c, _routing_table, busno, read, ack) {
                Ok(data) => kern_send(io, &kern::I2cReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(io, &kern::I2cReadReply { succeeded: false, data: 0xff })
            }
        }

        &kern::SpiSetConfigRequest { busno, flags, length, div, cs } => {
            let succeeded = dispatch!(local_spi, remote_spi, _routing_table, busno,
                set_config, flags, length, div, cs).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        },
        &kern::SpiWriteRequest { busno, data } => {
            let succeeded = dispatch!(local_spi, remote_spi, _routing_table, busno,
                write, data).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        }
        &kern::SpiReadRequest { busno } => {
            match dispatch!(local_spi, remote_spi, _routing_table, busno, read) {
                Ok(data) => kern_send(io, &kern::SpiReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(io, &kern::SpiReadReply { succeeded: false, data: 0 })
            }
        }

        _ => return Ok(false)
    }.and(Ok(true))
}
