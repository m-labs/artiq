use alloc::collections::vec_deque::VecDeque;
use board_artiq::{drtioaux, drtio_routing};
use board_misoc::csr;

// Packets from downstream (further satellites) are received and routed appropriately.
// they're passed as soon as possible downstream (within the subtree), or sent upstream,
// which is notified about pending packets.
// for rank 1 (connected to master) satellites, these packets are passed as an answer to DestinationStatusRequest;
// for higher ranks, after getting a notification, it will transact with downstream to get the pending packets.

// forward! macro is not deprecated, as routable packets are only these that can originate
// from both master and satellite, e.g. DDMA and Subkernel.

pub struct Router {
    upstream_queue: VecDeque<drtioaux::Packet>, 
    local_queue: VecDeque<drtioaux::Packet>,
    downstream_queue: VecDeque<(usize, drtioaux::Packet)>,
    upstream_notified: bool,
}

impl Router {
    pub fn new() -> Router {
        Router {
            upstream_queue: VecDeque::new(),
            local_queue: VecDeque::new(),
            downstream_queue: VecDeque::new(),
            upstream_notified: false,
        }
    }

    // called by local sources (DDMA, kernel) and by repeaters on receiving async data
    // messages are always buffered for both upstream and downstream
    pub fn route(&mut self, packet: drtioaux::Packet,
        _routing_table: &drtio_routing::RoutingTable, _rank: u8,
        _self_destination: u8
    ) {
        #[cfg(has_drtio_routing)]
        {
            let destination = packet.routable_destination();
            if let Some(destination) = destination {
                let hop = _routing_table.0[destination as usize][_rank as usize] as usize;
                if destination == _self_destination {
                    self.local_queue.push_back(packet);
                } else if hop > 0 && hop < csr::DRTIOREP.len() {
                    let repno = (hop - 1) as usize;
                    self.downstream_queue.push_back((repno, packet));
                } else {
                    self.upstream_queue.push_back(packet);
                }
            } else {
                error!("Received an unroutable packet: {:?}", packet);
            }
        }
        #[cfg(not(has_drtio_routing))]
        {
            self.upstream_queue.push_back(packet);
        }
    }

    // Sends a packet to a required destination, routing if it's necessary
    pub fn send(&mut self, packet: drtioaux::Packet,
        _routing_table: &drtio_routing::RoutingTable,
        _rank: u8, _destination: u8
    ) -> Result<(), drtioaux::Error<!>> {
        #[cfg(has_drtio_routing)]
        {
            let destination = packet.routable_destination();
            if let Some(destination) = destination {
                let hop = _routing_table.0[destination as usize][_rank as usize] as usize;
                if destination == 0 {
                    // response is needed immediately if master required it
                    drtioaux::send(0, &packet)?;
                } else if !(hop > 0 && hop < csr::DRTIOREP.len()) {
                    // higher rank can wait
                    self.upstream_queue.push_back(packet);
                } else {
                    let repno = (hop - 1) as usize;
                    // transaction will occur at closest possible opportunity
                    self.downstream_queue.push_back((repno, packet));
                }
                Ok(())
            } else {
                // packet not supported in routing, fallback - sent directly
                drtioaux::send(0, &packet)
            }
        }
        #[cfg(not(has_drtio_routing))]
        {
            drtioaux::send(0, &packet)
        }
    }

    pub fn any_upstream_waiting(&mut self) -> bool {
        let empty = self.upstream_queue.is_empty();
        if !empty && !self.upstream_notified {
            self.upstream_notified = true; // so upstream will not get spammed with notifications
            true
        } else {
            false
        }
    }

    pub fn get_upstream_packet(&mut self) -> Option<drtioaux::Packet> {
        self.upstream_notified = false;
        self.upstream_queue.pop_front()
    }

    pub fn get_downstream_packet(&mut self) -> Option<(usize, drtioaux::Packet)> {
        self.downstream_queue.pop_front()
    }

    pub fn get_local_packet(&mut self) -> Option<drtioaux::Packet> {
        self.local_queue.pop_front()
    }
}