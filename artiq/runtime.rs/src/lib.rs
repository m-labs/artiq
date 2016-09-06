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

fn test1(mut waiter: io::Waiter) {
    loop {
        println!("A");
        waiter.sleep(std::time::Duration::from_millis(1000));
    }
}

fn test2(mut waiter: io::Waiter) {
    loop {
        println!("B");
        waiter.sleep(std::time::Duration::from_millis(500));
    }
}

#[no_mangle]
pub unsafe extern fn rust_main() {
    println!("Accepting network sessions in Rust.");
    network_init();

    let addr = lwip::SocketAddr::new(lwip::IP4_ANY, 1234);
    let mut listener = lwip::TcpListener::bind(addr).unwrap();
    let mut stream = None;
    loop {
        lwip_service();
        if let Some(new_stream) = listener.try_accept() {
            stream = Some(new_stream)
        }
        if let Some(ref mut stream) = stream {
            if let Some(pbuf) = stream.try_read().expect("read") {
                println!("{:?}", pbuf.as_slice());
                stream.write(pbuf.as_slice()).expect("write");
            }
        }
    }
}
