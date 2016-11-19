use board::csr;
use sched::{Waiter, Spawner};

fn drtio_link_is_up() -> bool {
    unsafe {
        csr::drtio::link_status_read() == 1
    }
}

fn drtio_sync_tsc() {
    unsafe {
        csr::drtio::set_time_write(1);
        while csr::drtio::set_time_read() == 1 {}
    }
}

fn drtio_init_channel(channel: u16) {
    unsafe {
        csr::drtio::chan_sel_override_write(channel);
        csr::drtio::chan_sel_override_en_write(1);
        
        csr::drtio::o_reset_channel_status_write(1);
        csr::drtio::o_get_fifo_space_write(1);
        while csr::drtio::o_wait_read() == 1 {}  // TODO: timeout
        info!("FIFO space on channel {} is {}", channel, csr::drtio::o_dbg_fifo_space_read());

        csr::drtio::chan_sel_override_en_write(0);
    }
}

pub fn link_thread(waiter: Waiter, _spawner: Spawner) {
    loop {
        waiter.until(drtio_link_is_up).unwrap();
        info!("link RX is up");

        waiter.sleep(300).unwrap();
        info!("wait for remote side done");

        drtio_sync_tsc();
        info!("TSC synced");
        for channel in 0..16 {
            drtio_init_channel(channel);
        }
        info!("link initialization completed");

        waiter.until(|| !drtio_link_is_up()).unwrap();
        info!("link is down");
    }
}

fn drtio_packet_error_present() -> bool {
    unsafe {
        csr::drtio::packet_err_present_read() != 0
    }
}

fn drtio_get_packet_error() -> u8 {
    unsafe {
        let err = csr::drtio::packet_err_code_read();
        csr::drtio::packet_err_present_write(1);
        err
    }
}

pub fn error_thread(waiter: Waiter, _spawner: Spawner) {
    loop {
        waiter.until(drtio_packet_error_present).unwrap();
        error!("DRTIO packet error {}", drtio_get_packet_error());
    }
}
