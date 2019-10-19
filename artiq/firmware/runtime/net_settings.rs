use smoltcp::wire::{EthernetAddress, IpAddress};

use board_misoc::config;
#[cfg(soc_platform = "kasli")]
use board_artiq::i2c_eeprom;


pub struct NetAddresses {
    pub hardware_addr: EthernetAddress,
    pub ipv4_addr: IpAddress,
    pub ipv6_ll_addr: IpAddress,
    pub ipv6_addr: Option<IpAddress>
}

pub fn get_adresses() -> NetAddresses {
    let hardware_addr;
    match config::read_str("mac", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => {
            hardware_addr = addr;
            info!("using MAC address {}", hardware_addr);
        }
        _ => {
            #[cfg(soc_platform = "kasli")]
            {
                let eeprom = i2c_eeprom::EEPROM::kasli_eeprom();
                hardware_addr =
                    eeprom.read_eui48()
                    .map(|addr_buf| {
                        let hardware_addr = EthernetAddress(addr_buf);
                        info!("using MAC address {} from EEPROM", hardware_addr);
                        hardware_addr
                    })
                    .unwrap_or_else(|e| {
                        error!("failed to read MAC address from EEPROM: {}", e);
                        let hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x21]);
                        warn!("using default MAC address {}; consider changing it", hardware_addr);
                        hardware_addr
                    });
            }
            #[cfg(soc_platform = "sayma_amc")]
            {
                hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x11]);
                warn!("using default MAC address {}; consider changing it", hardware_addr);
            }
            #[cfg(soc_platform = "metlino")]
            {
                hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x19]);
                warn!("using default MAC address {}; consider changing it", hardware_addr);
            }
            #[cfg(soc_platform = "kc705")]
            {
                hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x01]);
                warn!("using default MAC address {}; consider changing it", hardware_addr);
            }
        }
    }

    let ipv4_addr;
    match config::read_str("ip", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => {
            ipv4_addr = addr;
            info!("using IPv4 address {}", ipv4_addr);
        }
        _ => {
            #[cfg(soc_platform = "kasli")]
            {
                ipv4_addr = IpAddress::v4(192, 168, 1, 70);
            }
            #[cfg(soc_platform = "sayma_amc")]
            {
                ipv4_addr = IpAddress::v4(192, 168, 1, 60);
            }
            #[cfg(soc_platform = "metlino")]
            {
                ipv4_addr = IpAddress::v4(192, 168, 1, 65);
            }
            #[cfg(soc_platform = "kc705")]
            {
                ipv4_addr = IpAddress::v4(192, 168, 1, 50);
            }
            info!("using default IPv4 address {}", ipv4_addr);
        }
    }

    let ipv6_ll_addr = IpAddress::v6(
        0xfe80, 0x0000, 0x0000, 0x0000,
        (((hardware_addr.0[0] ^ 0x02) as u16) << 8) | (hardware_addr.0[1] as u16),
        ((hardware_addr.0[2] as u16) << 8) | 0x00ff,
        0xfe00 | (hardware_addr.0[3] as u16),
        ((hardware_addr.0[4] as u16) << 8) | (hardware_addr.0[5] as u16));
    info!("using IPv6 link-local address {}", ipv6_ll_addr);

    let ipv6_addr = match config::read_str("ip6", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => {
            info!("using IPv6 configured address {}", addr);
            Some(addr)
        },
        _ => {
            info!("no IPv6 configured address");
            None
        }
    };

    NetAddresses {
        hardware_addr: hardware_addr,
        ipv4_addr: ipv4_addr,
        ipv6_ll_addr: ipv6_ll_addr,
        ipv6_addr: ipv6_addr
    }
}
