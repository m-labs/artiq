#![no_std]

#[macro_use]
extern crate std_artiq as std;

use std::prelude::v1::*;

pub mod io;

extern {
    fn network_init();
    fn lwip_service();
}

fn timer(waiter: io::Waiter) {
    loop {
        println!("tick");
        waiter.sleep(std::time::Duration::from_millis(1000)).unwrap();
    }
}

fn echo(waiter: io::Waiter) {
    let addr = io::SocketAddr::new(io::IP_ANY, 1234);
    let listener = io::TcpListener::bind(waiter, addr).unwrap();
    loop {
        let (mut stream, _addr) = listener.accept().unwrap();
        loop {
            let mut buf = [0];
            stream.read(&mut buf).unwrap();
            stream.write(&buf).unwrap();
        }
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
