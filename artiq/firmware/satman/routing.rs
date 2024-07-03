use alloc::{vec::Vec, collections::vec_deque::VecDeque};
use board_artiq::{drtioaux, drtio_routing};
#[cfg(has_drtio_routing)]
use board_misoc::csr;
use core::cmp::min;
use proto_artiq::drtioaux_proto::PayloadStatus;
use MASTER_PAYLOAD_MAX_SIZE;

/* represents data that has to be sent with the aux protocol */
#[derive(Debug)]
pub struct Sliceable {
    it: usize,
    data: Vec<u8>,
    destination: u8
}

pub struct SliceMeta {
    pub destination: u8,
    pub len: u16,
    pub status: PayloadStatus
}

macro_rules! get_slice_fn {
    ( $name:tt, $size:expr ) => {
        pub fn $name(&mut self, data_slice: &mut [u8; $size]) -> SliceMeta {
            let first = self.it == 0;
            let len = min($size, self.data.len() - self.it);
            let last = self.it + len == self.data.len();
            let status = PayloadStatus::from_status(first, last);
            data_slice[..len].clone_from_slice(&self.data[self.it..self.it+len]);
            self.it += len;
    
            SliceMeta {
                destination: self.destination,
                len: len as u16,
                status: status
            }
        }
    };
}

impl Sliceable {
    pub fn new(destination: u8, data: Vec<u8>) -> Sliceable {
        Sliceable {
            it: 0,
            data: data,
            destination: destination
        }
    }

    pub fn at_end(&self) -> bool {
        self.it == self.data.len()
    }

    pub fn extend(&mut self, data: &[u8]) {
        self.data.extend(data);
    }

    get_slice_fn!(get_slice_master, MASTER_PAYLOAD_MAX_SIZE);
}

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
    #[cfg(has_drtio_routing)]
    downstream_queue: VecDeque<(usize, drtioaux::Packet)>,
}

impl Router {
    pub fn new() -> Router {
        Router {
            upstream_queue: VecDeque::new(),
            local_queue: VecDeque::new(),
            #[cfg(has_drtio_routing)]
            downstream_queue: VecDeque::new(),
        }
    }

    // called by local sources (DDMA, kernel) and by repeaters on receiving async data
    // messages are always buffered for both upstream and downstream
    pub fn route(&mut self, packet: drtioaux::Packet,
        _routing_table: &drtio_routing::RoutingTable, _rank: u8,
        self_destination: u8
    ) {
        let destination = packet.routable_destination();
        #[cfg(has_drtio_routing)]
        {
            if let Some(destination) = destination {
                let hop = _routing_table.0[destination as usize][_rank as usize] as usize;
                if destination == self_destination {
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
            if destination == Some(self_destination) {
                self.local_queue.push_back(packet);
            } else {
                self.upstream_queue.push_back(packet);
            }
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

    pub fn get_upstream_packet(&mut self) -> Option<drtioaux::Packet> {
        let packet = self.upstream_queue.pop_front();
        packet
    }

    #[cfg(has_drtio_routing)]
    pub fn get_downstream_packet(&mut self) -> Option<(usize, drtioaux::Packet)> {
        self.downstream_queue.pop_front()
    }

    pub fn get_local_packet(&mut self) -> Option<drtioaux::Packet> {
        self.local_queue.pop_front()
    }
}