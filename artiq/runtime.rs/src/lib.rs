#![no_std]

#[macro_use]
extern crate std_artiq as std;
extern crate fringe;
extern crate lwip;

use std::prelude::v1::*;

pub mod io;

extern {
    fn network_init();
    fn lwip_service();
}

fn timer(mut waiter: io::Waiter) {
    loop {
        println!("tick");
        waiter.sleep(std::time::Duration::from_millis(1000)).unwrap();
    }
}

fn echo(mut waiter: io::Waiter) {
    let mut socket = lwip::UdpSocket::new().unwrap();
    socket.bind(lwip::SocketAddr::new(lwip::IP_ANY, 1234)).unwrap();
    loop {
        waiter.udp_readable(&socket).unwrap();
        let (addr, pbuf) = socket.try_recv().unwrap();
        println!("{:?}", core::str::from_utf8(pbuf.as_slice()));
        socket.send_to(addr, pbuf).unwrap();
    }
}

#[no_mangle]
pub unsafe extern fn rust_main() {
    println!("Accepting network sessions in Rust.");
    network_init();

    let mut scheduler = io::Scheduler::new();
    scheduler.spawn(4096, timer);
    scheduler.spawn(4096, echo);
    loop {
        lwip_service();
        scheduler.run()
    }
}
