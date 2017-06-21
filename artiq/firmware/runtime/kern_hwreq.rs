use session::{kern_acknowledge, kern_send};
use rtio_mgt;
use kernel_proto as kern;
use std::io;
use sched::Io;

#[cfg(has_drtio)]
mod drtio_i2c {
    use drtioaux;

    fn basic_reply() -> Result<(), ()> {
        match drtioaux::hw::recv_timeout(None) {
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

    pub fn start(busno: u32) -> Result<(), ()> {
        let request = drtioaux::Packet::I2cStartRequest { busno: busno as u8 };
        drtioaux::hw::send(&request).unwrap();
        basic_reply()
    }

    pub fn restart(busno: u32) -> Result<(), ()> {
        let request = drtioaux::Packet::I2cRestartRequest { busno: busno as u8 };
        drtioaux::hw::send(&request).unwrap();
        basic_reply()
    }

    pub fn stop(busno: u32) -> Result<(), ()> {
        let request = drtioaux::Packet::I2cStopRequest { busno: busno as u8 };
        drtioaux::hw::send(&request).unwrap();
        basic_reply()
    }

    pub fn write(busno: u32, data: u8) -> Result<bool, ()> {
        let request = drtioaux::Packet::I2cWriteRequest {
            busno: busno as u8,
            data: data
        };
        drtioaux::hw::send(&request).unwrap();
        match drtioaux::hw::recv_timeout(None) {
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

    pub fn read(busno: u32, ack: bool) -> Result<u8, ()> {
        let request = drtioaux::Packet::I2cReadRequest {
            busno: busno as u8,
            ack: ack
        };
        drtioaux::hw::send(&request).unwrap();
        match drtioaux::hw::recv_timeout(None) {
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

#[cfg(not(has_drtio))]
mod drtio_i2c {
    pub fn start(_busno: u32) -> Result<(), ()> {
        Err(())
    }

    pub fn restart(_busno: u32) -> Result<(), ()> {
        Err(())
    }

    pub fn stop(_busno: u32) -> Result<(), ()> {
        Err(())
    }

    pub fn write(_busno: u32, _data: u8) -> Result<bool, ()> {
        Err(())
    }

    pub fn read(_busno: u32, _ack: bool) -> Result<u8, ()> {
        Err(())
    }
}

mod i2c {
    use board;
    use super::drtio_i2c;

    pub fn start(busno: u32) -> Result<(), ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::i2c::start(dev_busno)
        } else {
            drtio_i2c::start(busno)
        }
    }

    pub fn restart(busno: u32) -> Result<(), ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::i2c::restart(dev_busno)
        } else {
            drtio_i2c::restart(busno)
        }
    }

    pub fn stop(busno: u32) -> Result<(), ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::i2c::stop(dev_busno)
        } else {
            drtio_i2c::stop(busno)
        }
    }

    pub fn write(busno: u32, data: u8) -> Result<bool, ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::i2c::write(dev_busno, data)
        } else {
            drtio_i2c::write(busno, data)
        }
    }

    pub fn read(busno: u32, ack: bool) -> Result<u8, ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::i2c::read(dev_busno, ack)
        } else {
            drtio_i2c::read(busno, ack)
        }
    }
}

#[cfg(has_drtio)]
mod drtio_spi {
    use drtioaux;

    fn basic_reply() -> Result<(), ()> {
        match drtioaux::hw::recv_timeout(None) {
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

    pub fn set_config(busno: u32, flags: u8, write_div: u8, read_div: u8) -> Result<(), ()> {
        let request = drtioaux::Packet::SpiSetConfigRequest {
            busno: busno as u8,
            flags: flags,
            write_div: write_div,
            read_div: read_div
        };
        drtioaux::hw::send(&request).unwrap();
        basic_reply()
    }

    pub fn set_xfer(busno: u32, chip_select: u16, write_length: u8, read_length: u8) -> Result<(), ()> {
        let request = drtioaux::Packet::SpiSetXferRequest {
            busno: busno as u8,
            chip_select: chip_select,
            write_length: write_length,
            read_length: read_length
        };
        drtioaux::hw::send(&request).unwrap();
        basic_reply()
    }

    pub fn write(busno: u32, data: u32) -> Result<(), ()> {
        let request = drtioaux::Packet::SpiWriteRequest {
            busno: busno as u8,
            data: data
        };
        drtioaux::hw::send(&request).unwrap();
        basic_reply()
    }

    pub fn read(busno: u32) -> Result<u32, ()> {
        let request = drtioaux::Packet::SpiReadRequest { busno: busno as u8 };
        drtioaux::hw::send(&request).unwrap();
        match drtioaux::hw::recv_timeout(None) {
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

#[cfg(not(has_drtio))]
mod drtio_spi {
    pub fn set_config(_busno: u32, _flags: u8, _write_div: u8, _read_div: u8) -> Result<(), ()> {
        Err(())
    }

    pub fn set_xfer(_busno: u32, _chip_select: u16, _write_length: u8, _read_length: u8) -> Result<(), ()> {
        Err(())
    }

    pub fn write(_busno: u32, _data: u32) -> Result<(), ()> {
        Err(())
    }

    pub fn read(_busno: u32) -> Result<u32, ()> {
        Err(())
    }
}

mod spi {
    use board;
    use super::drtio_spi;

    pub fn set_config(busno: u32, flags: u8, write_div: u8, read_div: u8) -> Result<(), ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::spi::set_config(dev_busno, flags, write_div, read_div)
        } else {
            drtio_spi::set_config(busno, flags, write_div, read_div)
        }
    }

    pub fn set_xfer(busno: u32, chip_select: u16, write_length: u8, read_length: u8) -> Result<(), ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::spi::set_xfer(dev_busno, chip_select, write_length, read_length)
        } else {
            drtio_spi::set_xfer(busno, chip_select, write_length, read_length)
        }
    }

    pub fn write(busno: u32, data: u32) -> Result<(), ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::spi::write(dev_busno, data)
        } else {
            drtio_spi::write(busno, data)
        }
    }

    pub fn read(busno: u32) -> Result<u32, ()> {
        let drtio = busno >> 16;
        let dev_busno = busno as u8;
        if drtio == 0 {
            board::spi::read(dev_busno)
        } else {
            drtio_spi::read(busno)
        }
    }
}

pub fn process_kern_hwreq(io: &Io, request: &kern::Message) -> io::Result<bool> {
    match request {
        &kern::RtioInitRequest => {
            info!("resetting RTIO");
            rtio_mgt::init_core();
            kern_acknowledge()
        }

        &kern::DrtioChannelStateRequest { channel } => {
            let (fifo_space, last_timestamp) = rtio_mgt::drtio_dbg::get_channel_state(channel);
            kern_send(io, &kern::DrtioChannelStateReply { fifo_space: fifo_space,
                                                          last_timestamp: last_timestamp })
        }
        &kern::DrtioResetChannelStateRequest { channel } => {
            rtio_mgt::drtio_dbg::reset_channel_state(channel);
            kern_acknowledge()
        }
        &kern::DrtioGetFifoSpaceRequest { channel } => {
            rtio_mgt::drtio_dbg::get_fifo_space(channel);
            kern_acknowledge()
        }
        &kern::DrtioPacketCountRequest => {
            let (tx_cnt, rx_cnt) = rtio_mgt::drtio_dbg::get_packet_counts();
            kern_send(io, &kern::DrtioPacketCountReply { tx_cnt: tx_cnt, rx_cnt: rx_cnt })
        }
        &kern::DrtioFifoSpaceReqCountRequest => {
            let cnt = rtio_mgt::drtio_dbg::get_fifo_space_req_count();
            kern_send(io, &kern::DrtioFifoSpaceReqCountReply { cnt: cnt })
        }

        &kern::I2cStartRequest { busno } => {
            let succeeded = i2c::start(busno).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cRestartRequest { busno } => {
            let succeeded = i2c::restart(busno).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cStopRequest { busno } => {
            let succeeded = i2c::stop(busno).is_ok();
            kern_send(io, &kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cWriteRequest { busno, data } => {
            match i2c::write(busno, data) {
                Ok(ack) => kern_send(io, &kern::I2cWriteReply { succeeded: true, ack: ack }),
                Err(_) => kern_send(io, &kern::I2cWriteReply { succeeded: false, ack: false })
            }
        }
        &kern::I2cReadRequest { busno, ack } => {
            match i2c::read(busno, ack) {
                Ok(data) => kern_send(io, &kern::I2cReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(io, &kern::I2cReadReply { succeeded: false, data: 0xff })
            }
        }

        &kern::SpiSetConfigRequest { busno, flags, write_div, read_div } => {
            let succeeded = spi::set_config(busno, flags, write_div, read_div).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        },
        &kern::SpiSetXferRequest { busno, chip_select, write_length, read_length } => {
            let succeeded = spi::set_xfer(busno, chip_select, write_length, read_length).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        }
        &kern::SpiWriteRequest { busno, data } => {
            let succeeded = spi::write(busno, data).is_ok();
            kern_send(io, &kern::SpiBasicReply { succeeded: succeeded })
        }
        &kern::SpiReadRequest { busno } => {
            match spi::read(busno) {
                Ok(data) => kern_send(io, &kern::SpiReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(io, &kern::SpiReadReply { succeeded: false, data: 0 })
            }
        }

        _ => return Ok(false)
    }.and(Ok(true))
}
