use board_misoc::clock;
use sched;
use sched::Dhcpv4Socket;
use core::fmt::{Display, Formatter};
use smoltcp::socket::{Dhcpv4Config, Dhcpv4Event};
use smoltcp::wire::{Ipv4Address, Ipv4Cidr};

struct OptionalIpAddressDisplay<'a> (&'a Option<Ipv4Address>);

impl<'a> Display for OptionalIpAddressDisplay<'a> {
    fn fmt(&self, f: &mut Formatter<'_>) -> core::fmt::Result {
        match self.0 {
            Some(ip) => write!(f, "{}", ip),
            None => write!(f, "<not set>"),
        }
    }
}


pub fn dhcp_thread(io: sched::Io) {
    let mut socket = Dhcpv4Socket::new(&io);
    let mut last_config: Option<Dhcpv4Config> = None;
    let mut done_reset = false;
    let start_time = clock::get_ms();

    loop {
        // A significant amount of the time our first discover isn't received
        // by the server. This is likely to be because the ethernet device isn't quite
        // ready at the point that it is sent. The following makes recovery from
        // that faster.
        if !done_reset && last_config.is_none() && start_time + 1000 < clock::get_ms() {
            info!("Didn't get initial config in first second. Assuming packet loss, trying a reset.");
            socket.reset();
            done_reset = true;
        }
        if let Some(event) = socket.poll() {
            match event {
                Dhcpv4Event::Configured(config) => {
                    // Only compare the ip address in the config with previous config because we
                    // ignore the rest of the config i.e. we don't do any DNS or require a default
                    // gateway.
                    let changed = if let Some(last_config) = last_config {
                        let mut changed = false;
                        if config.address != last_config.address {
                            info!("IP address changed {} -> {}", last_config.address, config.address);
                            changed = true;
                        }
                        if config.router != last_config.router {
                            info!("Default route changed {} -> {}",
                                OptionalIpAddressDisplay(&last_config.router),
                                OptionalIpAddressDisplay(&config.router),
                            );
                            changed = true;
                        }
                        changed
                    } else {
                        info!("Acquired DHCP config IP address: None -> {} default route: None -> {}",
                            config.address,
                            OptionalIpAddressDisplay(&config.router),
                        );
                        true
                    };
                    if changed {
                        last_config = Some(config);
                        io.set_ipv4_address(&config.address);
                        match config.router {
                            Some(route) => { io.set_ipv4_default_route(route).unwrap(); }
                            None => { io.remove_ipv4_default_route(); }
                        }
                    }
                }
                Dhcpv4Event::Deconfigured => {
                    if let Some(config) = last_config {
                        info!("Lost DHCP config IP address {} -> None; default route {} -> None",
                            config.address,
                            OptionalIpAddressDisplay(&config.router),
                        );
                        io.set_ipv4_address(&Ipv4Cidr::new(Ipv4Address::UNSPECIFIED, 0));
                        io.remove_ipv4_default_route();
                        last_config = None;
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
