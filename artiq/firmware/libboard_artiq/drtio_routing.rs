use board_misoc::config;
#[cfg(has_drtio_routing)]
use board_misoc::csr;
use core::fmt;

pub const DEST_COUNT: usize = 256;
pub const MAX_HOPS: usize = 32;
pub const INVALID_HOP: u8 = 0xff;

pub struct RoutingTable(pub [[u8; MAX_HOPS]; DEST_COUNT]);

impl RoutingTable {
    // default routing table is for star topology with no hops
    pub fn default_master(default_n_links: usize) -> RoutingTable {
        let mut ret = RoutingTable([[INVALID_HOP; MAX_HOPS]; DEST_COUNT]);
        for i in 0..default_n_links {
            ret.0[i][0] = i as u8;
        }
        for i in 1..default_n_links {
            ret.0[i][1] = 0x00;
        }
        ret
    }

    // use this by default on satellite, as they receive
    // the routing table from the master
    pub fn default_empty() -> RoutingTable {
        RoutingTable([[INVALID_HOP; MAX_HOPS]; DEST_COUNT])
    }
}

impl fmt::Display for RoutingTable {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "RoutingTable {{")?;
        for i in 0..DEST_COUNT {
            if self.0[i][0] != INVALID_HOP {
                write!(f, " {}:", i)?;
                for j in 0..MAX_HOPS {
                    if self.0[i][j] == INVALID_HOP {
                        break;
                    }
                    write!(f, " {}", self.0[i][j])?;
                }
                write!(f, ";")?;
            }
        }
        write!(f, " }}")?;
        Ok(())
    }
}

pub fn config_routing_table(default_n_links: usize) -> RoutingTable {
    let mut ret = RoutingTable::default_master(default_n_links);
    let ok = config::read("routing_table", |result| {
        if let Ok(data) = result {
            if data.len() == DEST_COUNT*MAX_HOPS {
                for i in 0..DEST_COUNT {
                    for j in 0..MAX_HOPS {
                        ret.0[i][j] = data[i*MAX_HOPS+j];
                    }
                }
                return true;
            }
        }
        false
    });
    if !ok {
        warn!("could not read routing table from configuration, using default");
    }
    info!("routing table: {}", ret);
    ret
}

#[cfg(has_drtio_routing)]
pub fn program_interconnect(rt: &RoutingTable, rank: u8)
{
    for i in 0..DEST_COUNT {
        let hop = rt.0[i][rank as usize];
        unsafe {
            csr::routing_table::destination_write(i as _);
            csr::routing_table::hop_write(hop);
        }
    }
}
