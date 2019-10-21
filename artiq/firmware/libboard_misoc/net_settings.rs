use core::fmt;

use smoltcp::wire::{EthernetAddress, IpAddress};

use config;
#[cfg(soc_platform = "kasli")]
use i2c_eeprom;


pub struct NetAddresses {
    pub hardware_addr: EthernetAddress,
    pub ipv4_addr: IpAddress,
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
                let eeprom = i2c_eeprom::EEPROM::kasli_eeprom();
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
        _ => {
            #[cfg(soc_platform = "kasli")]
            { ipv4_addr = IpAddress::v4(192, 168, 1, 70); }
            #[cfg(soc_platform = "sayma_amc")]
            { ipv4_addr = IpAddress::v4(192, 168, 1, 60); }
            #[cfg(soc_platform = "metlino")]
            { ipv4_addr = IpAddress::v4(192, 168, 1, 65); }
            #[cfg(soc_platform = "kc705")]
            { ipv4_addr = IpAddress::v4(192, 168, 1, 50); }
        }
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
