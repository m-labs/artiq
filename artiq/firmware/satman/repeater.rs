use board_misoc::{csr, clock};
use board_artiq::{drtioaux, drtio_routing};

#[cfg(has_drtio_routing)]
fn rep_link_rx_up(repno: u8) -> bool {
    let repno = repno as usize;
    unsafe {
        (csr::DRTIOREP[repno].rx_up_read)() == 1
    }
}

#[derive(Clone, Copy, PartialEq)]
enum RepeaterState {
    Down,
    SendPing { ping_count: u16 },
    WaitPingReply { ping_count: u16, timeout: u64 },
    Up,
    Failed
}

impl Default for RepeaterState {
    fn default() -> RepeaterState { RepeaterState::Down }
}

#[derive(Clone, Copy, Default)]
pub struct Repeater {
    repno: u8,
    auxno: u8,
    state: RepeaterState
}

#[cfg(has_drtio_routing)]
impl Repeater {
    pub fn new(repno: u8) -> Repeater {
        Repeater {
            repno: repno,
            auxno: repno + 1,
            state: RepeaterState::Down
        }
    }

    pub fn service(&mut self, routing_table: &drtio_routing::RoutingTable, rank: u8) {
        self.process_local_errors();

        match self.state {
            RepeaterState::Down => {
                if rep_link_rx_up(self.repno) {
                    info!("[REP#{}] link RX became up, pinging", self.repno);
                    self.state = RepeaterState::SendPing { ping_count: 0 };
                }
            }
            RepeaterState::SendPing { ping_count } => {
                if rep_link_rx_up(self.repno) {
                    drtioaux::send_link(self.auxno, &drtioaux::Packet::EchoRequest).unwrap();
                    self.state = RepeaterState::WaitPingReply {
                        ping_count: ping_count + 1,
                        timeout: clock::get_ms() + 100
                    }
                } else {
                    error!("[REP#{}] link RX went down during ping", self.repno);
                    self.state = RepeaterState::Down;
                }
            }
            RepeaterState::WaitPingReply { ping_count, timeout } => {
                if rep_link_rx_up(self.repno) {
                    if let Ok(Some(drtioaux::Packet::EchoReply)) = drtioaux::recv_link(self.auxno) {
                        info!("[REP#{}] remote replied after {} packets", self.repno, ping_count);
                        self.state = RepeaterState::Up;
                        if let Err(e) = self.sync_tsc() {
                            error!("[REP#{}] failed to sync TSC ({})", self.repno, e);
                            self.state = RepeaterState::Failed;
                            return;
                        }
                        if let Err(e) = self.load_routing_table(routing_table) {
                            error!("[REP#{}] failed to load routing table ({})", self.repno, e);
                            self.state = RepeaterState::Failed;
                            return;
                        }
                        if let Err(e) = self.set_rank(rank + 1) {
                            error!("[REP#{}] failed to set rank ({})", self.repno, e);
                            self.state = RepeaterState::Failed;
                            return;
                        }
                    } else {
                        if clock::get_ms() > timeout {
                            if ping_count > 200 {
                                error!("[REP#{}] ping failed", self.repno);
                                self.state = RepeaterState::Failed;
                            } else {
                                self.state = RepeaterState::SendPing { ping_count: ping_count };
                            }
                        }
                    }
                } else {
                    error!("[REP#{}] link RX went down during ping", self.repno);
                    self.state = RepeaterState::Down;
                }
            }
            RepeaterState::Up => {
                self.process_unsolicited_aux();
                if !rep_link_rx_up(self.repno) {
                    info!("[REP#{}] link is down", self.repno);
                    self.state = RepeaterState::Down;
                }
            }
            RepeaterState::Failed => {
                if !rep_link_rx_up(self.repno) {
                    info!("[REP#{}] link is down", self.repno);
                    self.state = RepeaterState::Down;
                }
            }
        }
    }

    fn process_unsolicited_aux(&self) {
        match drtioaux::recv_link(self.auxno) {
            Ok(Some(packet)) => warn!("[REP#{}] unsolicited aux packet: {:?}", self.repno, packet),
            Ok(None) => (),
            Err(_) => warn!("[REP#{}] aux packet error", self.repno)
        }
    }

    fn process_local_errors(&self) {
        let repno = self.repno as usize;
        let errors;
        unsafe {
            errors = (csr::DRTIOREP[repno].protocol_error_read)();
        }
        if errors & 1 != 0 {
            error!("[REP#{}] received packet of an unknown type", repno);
        }
        if errors & 2 != 0 {
            error!("[REP#{}] received truncated packet", repno);
        }
        if errors & 4 != 0 {
            let cmd;
            let chan_sel;
            unsafe {
                cmd = (csr::DRTIOREP[repno].command_missed_cmd_read)();
                chan_sel = (csr::DRTIOREP[repno].command_missed_chan_sel_read)();
            }
            error!("[REP#{}] CRI command missed, cmd={}, chan_sel=0x{:06x}", repno, cmd, chan_sel)
        }
        if errors & 8 != 0 {
            let destination;
            unsafe {
                destination = (csr::DRTIOREP[repno].buffer_space_timeout_dest_read)();
            }
            error!("[REP#{}] timeout attempting to get remote buffer space, destination=0x{:02x}", repno, destination);
        }
        unsafe {
            (csr::DRTIOREP[repno].protocol_error_write)(errors);
        }
    }

    fn recv_aux_timeout(&self, timeout: u32) -> Result<drtioaux::Packet, &'static str> {
        let max_time = clock::get_ms() + timeout as u64;
        loop {
            if !rep_link_rx_up(self.repno) {
                return Err("link went down");
            }
            if clock::get_ms() > max_time {
                return Err("timeout");
            }
            match drtioaux::recv_link(self.auxno) {
                Ok(Some(packet)) => return Ok(packet),
                Ok(None) => (),
                Err(_) => return Err("aux packet error")
            }
        }
    }

    pub fn sync_tsc(&self) -> Result<(), &'static str> {
        if self.state != RepeaterState::Up {
            return Ok(());
        }

        let repno = self.repno as usize;
        unsafe {
            (csr::DRTIOREP[repno].set_time_write)(1);
            while (csr::DRTIOREP[repno].set_time_read)() == 1 {}
        }

        // TSCAck is the only aux packet that is sent spontaneously
        // by the satellite, in response to a TSC set on the RT link.
        let reply = self.recv_aux_timeout(10000)?;
        if reply == drtioaux::Packet::TSCAck {
            return Ok(());
        } else {
            return Err("unexpected reply");
        }
    }

    pub fn set_path(&self, destination: u8, hops: &[u8; drtio_routing::MAX_HOPS]) -> Result<(), &'static str> {
        if self.state != RepeaterState::Up {
            return Ok(());
        }

        drtioaux::send_link(self.auxno, &drtioaux::Packet::RoutingSetPath {
            destination: destination,
            hops: *hops
        }).unwrap();
        let reply = self.recv_aux_timeout(200)?;
        if reply != drtioaux::Packet::RoutingAck {
            return Err("unexpected reply");
        }
        Ok(())
    }

    pub fn load_routing_table(&self, routing_table: &drtio_routing::RoutingTable) -> Result<(), &'static str> {
        for i in 0..drtio_routing::DEST_COUNT {
            self.set_path(i as u8, &routing_table.0[i])?;
        }
        Ok(())
    }

    pub fn set_rank(&self, rank: u8) -> Result<(), &'static str> {
        if self.state != RepeaterState::Up {
            return Ok(());
        }
        drtioaux::send_link(self.auxno, &drtioaux::Packet::RoutingSetRank {
            rank: rank
        }).unwrap();
        let reply = self.recv_aux_timeout(200)?;
        if reply != drtioaux::Packet::RoutingAck {
            return Err("unexpected reply");
        }
        Ok(())
    }
}

#[cfg(not(has_drtio_routing))]
impl Repeater {
    pub fn new(_repno: u8) -> Repeater { Repeater::default() }

    pub fn service(&self) { }

    pub fn sync_tsc(&self) -> Result<(), &'static str> { Ok(()) }
}
