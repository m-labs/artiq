use board_artiq::{drtioaux, drtio_routing};
#[cfg(has_drtio_routing)]
use board_misoc::{csr, clock};
use aux;

#[cfg(has_drtio_routing)]
fn rep_link_rx_up(repno: u8) -> bool {
    let repno = repno as usize;
    unsafe {
        (csr::DRTIOREP[repno].rx_up_read)() == 1
    }
}

#[cfg(has_drtio_routing)]
#[derive(Clone, Copy, PartialEq)]
enum RepeaterState {
    Down,
    SendPing { ping_count: u16 },
    WaitPingReply { ping_count: u16, timeout: u64 },
    Up { last_action_time: u64 },
    Failed
}

#[cfg(has_drtio_routing)]
impl Default for RepeaterState {
    fn default() -> RepeaterState { RepeaterState::Down }
}

#[cfg(has_drtio_routing)]
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

    #[allow(dead_code)]
    pub fn is_up(&self) -> bool {
        match self.state {
            RepeaterState::Up { .. } => true,
            _ => false
        }
    }

    pub fn service(&mut self, routing_table: &drtio_routing::RoutingTable, rank: u8) -> Result<Option<drtioaux::Packet>, drtioaux::Error<!>> {
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
                    drtioaux::send(self.auxno, &drtioaux::Packet {
                        source: 0,
                        destination: 0,
                        transaction_id: 0,
                        payload: drtioaux::Payload::EchoRequest }).unwrap();
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
                    if let Ok(Some(drtioaux::Packet {
                        source: 0,
                        destination: 0,
                        transaction_id: _,
                        payload: drtioaux::Payload::EchoReply
                    })) = drtioaux::recv(self.auxno) {
                        info!("[REP#{}] remote replied after {} packets", self.repno, ping_count);
                        self.state = RepeaterState::Up { last_action_time: 0 };
                        if let Err(e) = self.sync_tsc() {
                            error!("[REP#{}] failed to sync TSC ({})", self.repno, e);
                            self.state = RepeaterState::Failed;
                            return Ok(None);
                        }
                        if let Err(e) = self.load_routing_table(routing_table) {
                            error!("[REP#{}] failed to load routing table ({})", self.repno, e);
                            self.state = RepeaterState::Failed;
                            return Ok(None);
                        }
                        if let Err(e) = self.set_rank(rank + 1) {
                            error!("[REP#{}] failed to set rank ({})", self.repno, e);
                            self.state = RepeaterState::Failed;
                            return Ok(None);
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
            RepeaterState::Up { last_action_time: _ } => {
                if rep_link_rx_up(self.repno) {
                    return drtioaux::recv(self.auxno);
                } else {
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
        Ok(None)
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

    fn recv_aux_timeout(&self, timeout: u32) -> Result<drtioaux::Packet, drtioaux::Error<!>> {
        let max_time = clock::get_ms() + timeout as u64;
        loop {
            if !rep_link_rx_up(self.repno) {
                return Err(drtioaux::Error::LinkDown);
            }
            if clock::get_ms() > max_time {
                return Err(drtioaux::Error::TimedOut);
            }
            match drtioaux::recv(self.auxno) {
                Ok(Some(packet)) => return Ok(packet),
                Ok(None) => (),
                Err(e) => return Err(e)
            }
        }
    }

    pub fn aux_send(&mut self, current_time: u64, request: &drtioaux::Packet) -> Result<bool, drtioaux::Error<!>> {
        if let RepeaterState::Up { last_action_time } = self.state {
            if current_time > last_action_time + aux::LINK_COOLDOWN {
                self.state = RepeaterState::Up { last_action_time: current_time };
                drtioaux::send(self.auxno, request)?;
                Ok(true)
            } else {
                Ok(false)
            }
        }
        else {
            Err(drtioaux::Error::LinkDown)
        }
    }

    pub fn sync_tsc(&self) -> Result<(), drtioaux::Error<!>> {
        if !self.is_up() {
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
        if reply.payload == drtioaux::Payload::TSCAck {
            return Ok(());
        } else {
            return Err(drtioaux::Error::UnexpectedReply);
        }
    }

    pub fn set_path(&self, destination: u8, hops: &[u8; drtio_routing::MAX_HOPS]) -> Result<(), drtioaux::Error<!>> {
        if !self.is_up() {
            return Ok(());
        }

        drtioaux::send(self.auxno, &drtioaux::Packet {
            source: 0,
            destination: 0,
            transaction_id: 0,
            payload: drtioaux::Payload::RoutingSetPath {
                destination: destination,
                hops: *hops
        }}).unwrap();
        let reply = self.recv_aux_timeout(200)?;
        if reply.payload != drtioaux::Payload::RoutingAck {
            return Err(drtioaux::Error::UnexpectedReply);
        }
        Ok(())
    }

    pub fn load_routing_table(&self, routing_table: &drtio_routing::RoutingTable) -> Result<(), drtioaux::Error<!>> {
        for i in 0..drtio_routing::DEST_COUNT {
            self.set_path(i as u8, &routing_table.0[i])?;
        }
        Ok(())
    }

    pub fn set_rank(&self, rank: u8) -> Result<(), drtioaux::Error<!>> {
        if !self.is_up() {
            return Ok(());
        }
        drtioaux::send(self.auxno, &drtioaux::Packet {
            source: 0,
            destination: 0,
            transaction_id: 0,
            payload: drtioaux::Payload::RoutingSetRank {
                rank: rank
        }}).unwrap();
        let reply = self.recv_aux_timeout(200)?;
        if reply.payload != drtioaux::Payload::RoutingAck {
            return Err(drtioaux::Error::UnexpectedReply);
        }
        Ok(())
    }

    pub fn rtio_reset(&self) -> Result<(), drtioaux::Error<!>> {
        let repno = self.repno as usize;
        unsafe { (csr::DRTIOREP[repno].reset_write)(1); }
        clock::spin_us(100);
        unsafe { (csr::DRTIOREP[repno].reset_write)(0); }

        if !self.is_up() {
            return Ok(());
        }

        // todo: replace with aux transact
        drtioaux::send(self.auxno, &drtioaux::Packet {
            source: 0,
            destination: 0,
            transaction_id: 0,
            payload: drtioaux::Payload::ResetRequest }).unwrap();
        let reply = self.recv_aux_timeout(200)?;
        if reply.payload != drtioaux::Payload::ResetAck {
            return Err(drtioaux::Error::UnexpectedReply);
        }
        Ok(())
    }
}

#[cfg(not(has_drtio_routing))]
#[derive(Clone, Copy, Default)]
pub struct Repeater {
}

#[cfg(not(has_drtio_routing))]
impl Repeater {
    pub fn new(_repno: u8) -> Repeater { Repeater::default() }

    pub fn service(&self, _routing_table: &drtio_routing::RoutingTable, _rank: u8, _destination: u8) { }

    pub fn sync_tsc(&self) -> Result<(), drtioaux::Error<!>> { Ok(()) }

    pub fn rtio_reset(&self) -> Result<(), drtioaux::Error<!>> { Ok(()) }
}
