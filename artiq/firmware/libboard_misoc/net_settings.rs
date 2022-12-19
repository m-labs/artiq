use core::fmt;
use core::fmt::{Display, Formatter};
use core::str::FromStr;

use smoltcp::wire::{EthernetAddress, IpAddress, IpCidr, Ipv4Address, Ipv4Cidr, Ipv6Address, Ipv6Cidr};

use config;
#[cfg(soc_platform = "kasli")]
use i2c_eeprom;

pub enum Ipv4AddrConfig {
    UseDhcp,
    Static(Ipv4Cidr),
}

impl FromStr for Ipv4AddrConfig {
    type Err = ();

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        if s == "use_dhcp" {
            Ok(Ipv4AddrConfig::UseDhcp)
        } else if let Ok(cidr) = Ipv4Cidr::from_str(s) {
            Ok(Ipv4AddrConfig::Static(cidr))
        } else if let Ok(addr) = Ipv4Address::from_str(s) {
            Ok(Ipv4AddrConfig::Static(Ipv4Cidr::new(addr, 0)))
        } else {
            Err(())
        }
    }
}

impl Display for Ipv4AddrConfig {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Ipv4AddrConfig::UseDhcp => write!(f, "use_dhcp"),
            Ipv4AddrConfig::Static(ipv4) => write!(f, "{}", ipv4)
        }
    }
}


pub struct NetAddresses {
    pub hardware_addr: EthernetAddress,
    pub ipv4_addr: Ipv4AddrConfig,
    pub ipv6_ll_addr: IpCidr,
    pub ipv6_addr: Option<Ipv6Cidr>,
    pub ipv4_default_route: Option<Ipv4Address>,
    pub ipv6_default_route: Option<Ipv6Address>,
}

impl fmt::Display for NetAddresses {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "MAC={} IPv4={} IPv6-LL={} IPv6=",
            self.hardware_addr, self.ipv4_addr, self.ipv6_ll_addr)?;
        match self.ipv6_addr {
            Some(addr) => write!(f, "{}", addr)?,
            None => write!(f, "no configured address")?
        }
        Ok(())
    }
}

pub fn get_adresses() -> NetAddresses {
    let hardware_addr;
    match config::read_str("mac", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => hardware_addr = addr,
        _ => {
            #[cfg(soc_platform = "kasli")]
            {
                let eeprom = i2c_eeprom::EEPROM::new();
                hardware_addr =
                    eeprom.read_eui48()
                    .map(|addr_buf| EthernetAddress(addr_buf))
                    .unwrap_or_else(|_e| EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x21]));
            }
            #[cfg(soc_platform = "kc705")]
            { hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x01]); }
        }
    }

    let ipv4_addr = match config::read_str("ip", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => addr,
        _ => Ipv4AddrConfig::UseDhcp,
    };

    let ipv4_default_route = match config::read_str("ipv4_default_route", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => Some(addr),
        _ => None,
    };

    let ipv6_ll_addr = IpCidr::new(IpAddress::v6(
        0xfe80, 0x0000, 0x0000, 0x0000,
        (((hardware_addr.0[0] ^ 0x02) as u16) << 8) | (hardware_addr.0[1] as u16),
        ((hardware_addr.0[2] as u16) << 8) | 0x00ff,
        0xfe00 | (hardware_addr.0[3] as u16),
        ((hardware_addr.0[4] as u16) << 8) | (hardware_addr.0[5] as u16)), 10);

    let ipv6_addr = match config::read_str("ip6", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => Some(addr),
        _ => None
    };

    let ipv6_default_route = match config::read_str("ipv6_default_route", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => Some(addr),
        _ => None,
    };

    NetAddresses {
        hardware_addr,
        ipv4_addr,
        ipv6_ll_addr,
        ipv6_addr,
        ipv4_default_route,
        ipv6_default_route,
    }
}
