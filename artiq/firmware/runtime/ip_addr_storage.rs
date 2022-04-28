use smoltcp::iface::{Interface, InterfaceBuilder};
use smoltcp::phy::Device;
use smoltcp::wire::{IpAddress, IpCidr, Ipv4Address, Ipv4Cidr};
use board_misoc::net_settings::{Ipv4AddrConfig, NetAddresses};


const IPV4_INDEX: usize = 0;
const IPV6_LL_INDEX: usize = 1;
const IPV6_INDEX: usize = 2;
const IP_ADDRESS_STORAGE_SIZE: usize = 3;

pub trait InterfaceBuilderEx {
    fn init_ip_addrs(self, net_addresses: &NetAddresses) -> Self;
}

impl<'a, DeviceT: for<'d> Device<'d>> InterfaceBuilderEx for InterfaceBuilder<'a, DeviceT> {
    fn init_ip_addrs(self, net_addresses: &NetAddresses) -> Self {
        let mut storage = [
            IpCidr::new(IpAddress::Ipv4(Ipv4Address::UNSPECIFIED), 0);  IP_ADDRESS_STORAGE_SIZE
        ];
        if let Ipv4AddrConfig::Static(ipv4) = net_addresses.ipv4_addr {
            storage[IPV4_INDEX] = IpCidr::new(IpAddress::Ipv4(ipv4), 0);
        }
        storage[IPV6_LL_INDEX] = IpCidr::new(net_addresses.ipv6_ll_addr, 0);
        if let Some(ipv6) = net_addresses.ipv6_addr {
            storage[IPV6_INDEX] = IpCidr::new(ipv6, 0);
        }
        self.ip_addrs(storage)
    }
}

pub trait InterfaceEx {
    fn update_ipv4_addr(&mut self, addr: &Ipv4Cidr);
}

impl<'a, DeviceT: for<'d> Device<'d>> InterfaceEx for Interface<'a, DeviceT> {
    fn update_ipv4_addr(&mut self, addr: &Ipv4Cidr) {
        self.update_ip_addrs(|storage| storage[IPV4_INDEX] = IpCidr::Ipv4(*addr))
    }
}
