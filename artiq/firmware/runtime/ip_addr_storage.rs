use smoltcp::iface::{Interface, InterfaceBuilder};
use smoltcp::phy::Device;
use smoltcp::wire::{IpAddress, IpCidr, Ipv4Address, Ipv4Cidr, Ipv6Cidr};
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
            IpCidr::new(IpAddress::Ipv4(Ipv4Address::UNSPECIFIED), 32);  IP_ADDRESS_STORAGE_SIZE
        ];
        if let Ipv4AddrConfig::Static(ipv4) = net_addresses.ipv4_addr {
            storage[IPV4_INDEX] = IpCidr::Ipv4(ipv4);
        }
        storage[IPV6_LL_INDEX] = net_addresses.ipv6_ll_addr;
        if let Some(ipv6) = net_addresses.ipv6_addr {
            storage[IPV6_INDEX] = IpCidr::Ipv6(ipv6);
        }
        self.ip_addrs(storage)
    }
}

pub trait InterfaceEx {
    fn update_ipv4_addr(&mut self, addr: &Ipv4Cidr);
    fn update_ipv6_addr(&mut self, addr: &Ipv6Cidr);
}

impl<'a, DeviceT: for<'d> Device<'d>> InterfaceEx for Interface<'a, DeviceT> {
    fn update_ipv4_addr(&mut self, addr: &Ipv4Cidr) {
        self.update_ip_addrs(|storage| storage[IPV4_INDEX] = IpCidr::Ipv4(*addr))
    }
    fn update_ipv6_addr(&mut self, addr: &Ipv6Cidr) {
        self.update_ip_addrs(|storage| storage[IPV6_INDEX] = IpCidr::Ipv6(*addr))
    }
}
