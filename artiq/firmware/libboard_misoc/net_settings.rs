use core::fmt;
use core::fmt::{Display, Formatter};
use core::str::FromStr;

use smoltcp::wire::{EthernetAddress, IpAddress, Ipv4Address};

use config;
#[cfg(soc_platform = "kasli")]
use i2c_eeprom;

pub enum Ipv4AddrConfig {
    UseDhcp,
    Static(Ipv4Address),
}

impl FromStr for Ipv4AddrConfig {
    type Err = ();

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Ok(if s == "use_dhcp" {
            Ipv4AddrConfig::UseDhcp
        } else {
            Ipv4AddrConfig::Static(Ipv4Address::from_str(s)?)
        })
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
    pub ipv6_ll_addr: IpAddress,
    pub ipv6_addr: Option<IpAddress>
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
            #[cfg(soc_platform = "sayma_amc")]
            { hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x11]); }
            #[cfg(soc_platform = "metlino")]
            { hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x19]); }
            #[cfg(soc_platform = "kc705")]
            { hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x01]); }
        }
    }

    let ipv4_addr;
    match config::read_str("ip", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => ipv4_addr = addr,
        _ => ipv4_addr = Ipv4AddrConfig::UseDhcp,
    }

    let ipv6_ll_addr = IpAddress::v6(
        0xfe80, 0x0000, 0x0000, 0x0000,
        (((hardware_addr.0[0] ^ 0x02) as u16) << 8) | (hardware_addr.0[1] as u16),
        ((hardware_addr.0[2] as u16) << 8) | 0x00ff,
        0xfe00 | (hardware_addr.0[3] as u16),
        ((hardware_addr.0[4] as u16) << 8) | (hardware_addr.0[5] as u16));

    let ipv6_addr = match config::read_str("ip6", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => Some(addr),
        _ => None
    };

    NetAddresses {
        hardware_addr: hardware_addr,
        ipv4_addr: ipv4_addr,
        ipv6_ll_addr: ipv6_ll_addr,
        ipv6_addr: ipv6_addr
    }
}
