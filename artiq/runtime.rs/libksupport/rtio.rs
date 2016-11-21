use board::csr;
use core::ptr::{read_volatile, write_volatile};
use core::slice;

const RTIO_O_STATUS_FULL:           u32 = 1;
const RTIO_O_STATUS_UNDERFLOW:      u32 = 2;
const RTIO_O_STATUS_SEQUENCE_ERROR: u32 = 4;
const RTIO_O_STATUS_COLLISION:      u32 = 8;
const RTIO_O_STATUS_BUSY:           u32 = 16;
const RTIO_I_STATUS_EMPTY:          u32 = 1;
const RTIO_I_STATUS_OVERFLOW:       u32 = 2;

pub extern fn init() {
    unsafe {
        csr::rtio::reset_write(1);
        csr::rtio::reset_write(0);
        csr::rtio::reset_phy_write(0);
    }
}

pub extern fn get_counter() -> i64 {
    unsafe {
        csr::rtio::counter_update_write(1);
        csr::rtio::counter_read() as i64
    }
}

#[inline(always)]
pub unsafe fn rtio_o_data_write(w: u32) {
    write_volatile(
        csr::rtio::O_DATA_ADDR.offset((csr::rtio::O_DATA_SIZE - 1) as isize),
        w);
}

#[inline(always)]
pub unsafe fn rtio_i_data_read() -> u32 {
    read_volatile(
        csr::rtio::I_DATA_ADDR.offset((csr::rtio::I_DATA_SIZE - 1) as isize)
        )
}


#[inline(never)]
unsafe fn process_exceptional_status(timestamp: i64, channel: u32, status: u32) {
    if status & RTIO_O_STATUS_FULL != 0 {
        while csr::rtio::o_status_read() & RTIO_O_STATUS_FULL != 0 {}
    }
    if status & RTIO_O_STATUS_UNDERFLOW != 0 {
        csr::rtio::o_underflow_reset_write(1);
        artiq_raise!("RTIOUnderflow",
            "RTIO underflow at {0} mu, channel {1}, slack {2} mu",
            timestamp, channel as i64, timestamp - get_counter())
    }
    if status & RTIO_O_STATUS_SEQUENCE_ERROR != 0 {
        csr::rtio::o_sequence_error_reset_write(1);
        artiq_raise!("RTIOSequenceError",
            "RTIO sequence error at {0} mu, channel {1}",
            timestamp, channel as i64, 0)
    }
    if status & RTIO_O_STATUS_COLLISION != 0 {
        csr::rtio::o_collision_reset_write(1);
        artiq_raise!("RTIOCollision",
            "RTIO collision at {0} mu, channel {1}",
            timestamp, channel as i64, 0)
    }
    if status & RTIO_O_STATUS_BUSY != 0 {
        csr::rtio::o_busy_reset_write(1);
        artiq_raise!("RTIOBusy",
            "RTIO busy on channel {0}",
            channel as i64, 0, 0)
    }
}

pub extern fn output(timestamp: i64, channel: u32, addr: u32, data: u32) {
    unsafe {
        csr::rtio::chan_sel_write(channel);
        csr::rtio::o_timestamp_write(timestamp as u64);
        csr::rtio::o_address_write(addr);
        rtio_o_data_write(data);
        csr::rtio::o_we_write(1);
        let status = csr::rtio::o_status_read();
        if status != 0 {
            process_exceptional_status(timestamp, channel, status);
        }
    }
}

pub extern fn output_list(timestamp: i64, channel: u32, addr: u32,
                          &(len, ptr): &(usize, *const u32)) {
    unsafe {
        csr::rtio::chan_sel_write(channel);
        csr::rtio::o_timestamp_write(timestamp as u64);
        csr::rtio::o_address_write(addr);
        let data = slice::from_raw_parts(ptr, len);
        for i in 0..data.len() {
            write_volatile(
                csr::rtio::O_DATA_ADDR.offset((csr::rtio::O_DATA_SIZE - 1 - i) as isize),
                data[i]);
        }
        csr::rtio::o_we_write(1);
        let status = csr::rtio::o_status_read();
        if status != 0 {
            process_exceptional_status(timestamp, channel, status);
        }
    }
}

pub extern fn input_timestamp(timeout: i64, channel: u32) -> u64 {
    unsafe {
        csr::rtio::chan_sel_write(channel);
        let mut status;
        loop {
            status = csr::rtio::i_status_read();
            if status == 0 { break }

            if status & RTIO_I_STATUS_OVERFLOW != 0 {
                csr::rtio::i_overflow_reset_write(1);
                break
            }
            if get_counter() >= timeout {
                // check empty flag again to prevent race condition.
                // now we are sure that the time limit has been exceeded.
                let status = csr::rtio::i_status_read();
                if status & RTIO_I_STATUS_EMPTY != 0 { break }
            }
            // input FIFO is empty - keep waiting
        }

        if status & RTIO_I_STATUS_OVERFLOW != 0 {
            artiq_raise!("RTIOOverflow",
                "RTIO input overflow on channel {0}",
                channel as i64, 0, 0);
        }
        if status & RTIO_I_STATUS_EMPTY != 0 {
            return !0
        }

        let timestamp = csr::rtio::i_timestamp_read();
        csr::rtio::i_re_write(1);
        timestamp
    }
}

pub extern fn input_data(channel: u32) -> u32 {
    unsafe {
        csr::rtio::chan_sel_write(channel);
        loop {
            let status = csr::rtio::i_status_read();
            if status == 0 { break }

            if status & RTIO_I_STATUS_OVERFLOW != 0 {
                csr::rtio::i_overflow_reset_write(1);
                artiq_raise!("RTIOOverflow",
                    "RTIO input overflow on channel {0}",
                    channel as i64, 0, 0);
            }
        }

        let data = rtio_i_data_read();
        csr::rtio::i_re_write(1);
        data
    }
}

#[cfg(has_rtio_log)]
pub fn log(timestamp: i64, data: &[u8]) {
    unsafe {
        csr::rtio::chan_sel_write(csr::CONFIG_RTIO_LOG_CHANNEL);
        csr::rtio::o_timestamp_write(timestamp as u64);

        let mut word: u32 = 0;
        for i in 0..data.len() {
            word <<= 8;
            word |= data[i] as u32;
            if i % 4 == 0 {
                rtio_o_data_write(word);
                csr::rtio::o_we_write(1);
                word = 0;
            }
        }

        word <<= 8;
        rtio_o_data_write(word);
        csr::rtio::o_we_write(1);
    }
}

#[cfg(not(has_rtio_log))]
pub fn log(timestamp: i64, data: &[u8]) {}
