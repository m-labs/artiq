use session::{kern_acknowledge, kern_send};
use rtio_mgt;
use board;
use kernel_proto as kern;
use std::io;
use sched::Io;

// TODO
mod drtio_spi {
    pub fn set_config(_busno: u32, _flags: u8, _write_div: u8, _read_div: u8) {}
    pub fn set_xfer(_busno: u32, _chip_select: u16, _write_length: u8, _read_length: u8) {}
    pub fn write(_busno: u32, _data: u32) {}
    pub fn read(_busno: u32) -> u32 { 0 }
}

mod spi {
    use board;
    use super::drtio_spi;

    pub fn set_config(busno: u32, flags: u8, write_div: u8, read_div: u8) {
        let drtio = busno >> 16;
        if drtio == 0 {
            board::spi::set_config(flags, write_div, read_div)
        } else {
            drtio_spi::set_config(busno, flags, write_div, read_div)
        }
    }

    pub fn set_xfer(busno: u32, chip_select: u16, write_length: u8, read_length: u8) {
        let drtio = busno >> 16;
        if drtio == 0 {
            board::spi::set_xfer(chip_select, write_length, read_length)
        } else {
            drtio_spi::set_xfer(busno, chip_select, write_length, read_length)
        }
    }

    pub fn write(busno: u32, data: u32) {
        let drtio = busno >> 16;
        if drtio == 0 {
            board::spi::write(data)
        } else {
            drtio_spi::write(busno, data)
        }
    }

    pub fn read(busno: u32) -> u32 {
        let drtio = busno >> 16;
        if drtio == 0 {
            board::spi::read()
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
            board::i2c::start(busno);
            kern_acknowledge()
        }
        &kern::I2cStopRequest { busno } => {
            board::i2c::stop(busno);
            kern_acknowledge()
        }
        &kern::I2cWriteRequest { busno, data } => {
            let ack = board::i2c::write(busno, data);
            kern_send(io, &kern::I2cWriteReply { ack: ack })
        }
        &kern::I2cReadRequest { busno, ack } => {
            let data = board::i2c::read(busno, ack);
            kern_send(io, &kern::I2cReadReply { data: data })
        },

        &kern::SpiSetConfigRequest { busno, flags, write_div, read_div } => {
            spi::set_config(busno, flags, write_div, read_div);
            kern_acknowledge()
        },
        &kern::SpiSetXferRequest { busno, chip_select, write_length, read_length } => {
            spi::set_xfer(busno, chip_select, write_length, read_length);
            kern_acknowledge()
        }
        &kern::SpiWriteRequest { busno, data } => {
            spi::write(busno, data);
            kern_acknowledge()
        }
        &kern::SpiReadRequest { busno } => {
            let data = spi::read(busno);
            kern_send(io, &kern::SpiReadReply { data: data })
        },

        _ => return Ok(false)
    }.and(Ok(true))
}
