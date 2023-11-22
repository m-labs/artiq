use alloc::collections::vec_deque::VecDeque;
use board_artiq::{drtioaux, drtio_routing};
use board_misoc::csr;

// Packets from downstream (further satellites) are received and routed appropriately.
// they're passed immediately if it's possible (within the subtree), or sent upstream.
// for rank 1 (connected to master) satellites, these packets are passed as an answer to DestinationStatusRequest;
// for higher ranks, straight upstream, but awaiting for an ACK to make sure the upstream is not overwhelmed.

// forward! macro is not deprecated, as routable packets are only these that can originate
// from both master and satellite, e.g. DDMA and Subkernel.

pub fn get_routable_packet_destination(packet: &drtioaux::Packet) -> Option<u8> {
    let destination = match packet {
        // received from downstream
        drtioaux::Packet::DmaAddTraceRequest      { destination, .. } => destination,
        drtioaux::Packet::DmaAddTraceReply        { destination, .. } => destination,
        drtioaux::Packet::DmaRemoveTraceRequest   { destination, .. } => destination,
        drtioaux::Packet::DmaRemoveTraceReply     { destination, .. } => destination,
        drtioaux::Packet::DmaPlaybackRequest      { destination, .. } => destination,
        drtioaux::Packet::DmaPlaybackReply        { destination, .. } => destination,
        drtioaux::Packet::SubkernelLoadRunRequest { destination, .. } => destination,
        drtioaux::Packet::SubkernelLoadRunReply   { destination, .. } => destination,
        // received from downstream or produced locally
        drtioaux::Packet::SubkernelMessage        { destination, .. } => destination,
        drtioaux::Packet::SubkernelMessageAck     { destination, .. } => destination,
        // "async" - master gets them by deststatreq, satellites would get it through the router
        drtioaux::Packet::DmaPlaybackStatus       { destination, .. } => destination,
        drtioaux::Packet::SubkernelFinished       { destination, .. } => destination,
        _ => return None
    };
    Some(*destination)
}

pub struct Router {
    out_messages: VecDeque<drtioaux::Packet>, 
    local_messages: VecDeque<drtioaux::Packet>,
    upstream_ready: bool
}

impl Router {
    pub fn new() -> Router {
        Router {
            out_messages: VecDeque::new(),
            local_messages: VecDeque::new(),
            upstream_ready: true
        }
    }


    // called by local sources (DDMA, kernel) and by repeaters on receiving unsolicited data
    // messages are always buffered for upstream, or passed downstream directly
    pub fn route(&mut self, packet: drtioaux::Packet,
        _routing_table: &drtio_routing::RoutingTable, _rank: u8
    ) -> Result<(), drtioaux::Error<!>>  {
        #[cfg(has_drtio_routing)]
        {
            let destination = get_routable_packet_destination(&packet);
            if let Some(destination) = destination {
                let hop = _routing_table.0[destination as usize][_rank as usize];
                let auxno = if destination == 0 { 0 } else { hop };
                if hop != 0 {
                    if hop as usize <= csr::DRTIOREP.len() {
                        drtioaux::send(auxno, &packet)?;
                    } else {
                        self.out_messages.push_back(packet);
                    }
                } else {
                    self.local_messages.push_back(packet);
                }
            } else {
                return Err(drtioaux::Error::RoutingError);
            }
        }
        #[cfg(not(has_drtio_routing))]
        {
            self.out_messages.push_back(packet);
        }
        Ok(())
    }

    // Sends a packet to a required destination, routing if it's necessary
    pub fn send(&mut self, packet: drtioaux::Packet,
        _routing_table: &drtio_routing::RoutingTable, _rank: u8) -> Result<(), drtioaux::Error<!>> {
        #[cfg(has_drtio_routing)]
        {
            let destination = get_routable_packet_destination(&packet);
            if destination.is_none() || destination == Some(0) {
                // send upstream directly (response to master)
                drtioaux::send(0, &packet)
            } else {
                self.route(packet, _routing_table, _rank)
            }
        }
        #[cfg(not(has_drtio_routing))]
        {
            drtioaux::send(0, &packet)
        }
    }

    pub fn get_upstream_packet(&mut self, rank: u8) -> Option<drtioaux::Packet> {
        // called on DestinationStatusRequest on rank 1, in loop in others
        if self.upstream_ready {
            let packet = self.out_messages.pop_front();
            if rank > 1 && packet.is_some() {
                // packet will be sent out, awaiting ACK
                self.upstream_ready = false;
            }
            packet
        } else {
            None
        }
    }

    pub fn routing_ack_received(&mut self) {
        self.upstream_ready = true;
    }

    pub fn get_local_packet(&mut self) -> Option<drtioaux::Packet> {
        self.local_messages.pop_front()
    }
}