use board_misoc::clock;
use sched;
use sched::Dhcpv4Socket;
use smoltcp::socket::Dhcpv4Event;
use smoltcp::wire::{Ipv4Address, Ipv4Cidr};

pub fn dhcp_thread(io: sched::Io) {
    let mut socket = Dhcpv4Socket::new(&io);
    let mut last_ip: Option<Ipv4Cidr> = None;
    let mut done_reset = false;
    let start_time = clock::get_ms();

    loop {
        // A significant amount of the time our first discover isn't received
        // by the server. This is likely to be because the ethernet device isn't quite
        // ready at the point that it is sent. The following makes recovery from
        // that faster.
        if !done_reset && last_ip.is_none() && start_time + 1000 < clock::get_ms() {
            info!("Didn't get initial IP in first second. Assuming packet loss, trying a reset.");
            socket.reset();
            done_reset = true;
        }
        if let Some(event) = socket.poll() {
            match event {
                Dhcpv4Event::Configured(config) => {
                    // Only compare the ip address in the config with previous config because we
                    // ignore the rest of the config i.e. we don't do any DNS or require a default
                    // gateway.
                    let changed = if let Some(last_ip) = last_ip {
                        if config.address != last_ip {
                            info!("IP address changed {} -> {}", last_ip, config.address);
                            true
                        } else {
                            false
                        }
                    } else {
                        info!("Acquired IP address: None -> {}", config.address);
                        true
                    };
                    if changed {
                        last_ip = Some(config.address);
                        io.set_ipv4_address(&config.address);
                    }
                }
                Dhcpv4Event::Deconfigured => {
                    if let Some(ip) = last_ip {
                        info!("Lost IP address {} -> None", ip);
                        io.set_ipv4_address(&Ipv4Cidr::new(Ipv4Address::UNSPECIFIED, 0));
                        last_ip = None;
                    }
                    // We always get one of these events at the start, ignore that one
                }
            }
        }
        // We want to poll after every poll of the interface. So we need to
        // do a minimal yield here.
        io.relinquish().unwrap();
    }
}
