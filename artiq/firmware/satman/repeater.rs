use board_misoc::{csr, clock};
use board_artiq::drtioaux;

#[cfg(has_drtio_routing)]
fn rep_link_rx_up(linkno: u8) -> bool {
    let linkno = linkno as usize;
    unsafe {
        (csr::DRTIOREP[linkno].rx_up_read)() == 1
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

    pub fn service(&mut self) {
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
                        if self.sync_tsc().is_err() {
                            error!("[REP#{}] remote failed to ack TSC", self.repno);
                            self.state = RepeaterState::Failed;
                            return;
                        }
                        // TODO: send routing table and rank
                        self.state = RepeaterState::Up; 
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

    pub fn sync_tsc(&self) -> Result<(), &'static str> {
        if self.state != RepeaterState::Up {
            return Ok(());
        }

        let repno = self.repno as usize;
        unsafe {
            (csr::DRTIOREP[repno].set_time_write)(1);
            while (csr::DRTIOREP[repno].set_time_read)() == 1 {}
        }

        let timeout = clock::get_ms() + 200;
        loop {
            if !rep_link_rx_up(self.repno) {
                return Err("link went down");
            }
            if clock::get_ms() > timeout {
                return Err("timeout");
            }
            // TSCAck is the only aux packet that is sent spontaneously
            // by the satellite, in response to a TSC set on the RT link.
            if let Ok(Some(drtioaux::Packet::TSCAck)) = drtioaux::recv_link(self.auxno) {
                return Ok(());
            }
        }
    }
}

#[cfg(not(has_drtio_routing))]
impl Repeater {
    pub fn new(_repno: u8) -> Repeater { Repeater::default() }

    pub fn service(&self) { }

    pub fn sync_tsc(&self) -> Result<(), &'static str> { Ok(()) }
}
