use alloc::{collections::BTreeMap, vec::Vec};
use core::{cmp::min, cell::RefCell};
use board_misoc::{csr, clock};
use board_artiq::{drtioaux, drtio_routing};
use proto_artiq::drtioaux_proto::{MASTER_PAYLOAD_MAX_SIZE, SAT_PAYLOAD_MAX_SIZE, PayloadStatus};

use repeater;
use drtiosat_tsc_loaded;
use drtiosat_link_rx_up;

type TransactionHandle = u8;

pub const LINK_COOLDOWN: u64 = 5;
pub const DEFAULT_TIMEOUT: u64 = 200;
const DEFAULT_ACK_TIMEOUT: u64 = 50;

/* represents large data that has to be sent with the aux protocol */
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

    get_slice_fn!(get_slice_sat, SAT_PAYLOAD_MAX_SIZE);
    get_slice_fn!(get_slice_master, MASTER_PAYLOAD_MAX_SIZE);
}

#[derive(Debug)]
pub enum Error {
    TransactionLimitReached,
    Timeout
}

/* represents packets that arrive to this device */
#[derive(PartialEq)]
enum IncomingTransactionState {
    Received,
    Handled(u64) // handling timestamp
}

struct IncomingTransaction {
    pub payload: drtioaux::Payload,
    pub state: IncomingTransactionState,
}

impl IncomingTransaction {
    fn new(payload: drtioaux::Payload) -> IncomingTransaction {
        IncomingTransaction {
            payload: payload,
            state: IncomingTransactionState::Received
        }
    }
    fn can_be_deleted(&self, current_time: u64) -> bool {
        match self.state {
            IncomingTransactionState::Handled(last_action_time) => current_time > last_action_time + DEFAULT_TIMEOUT,
            _ => false
        }
    }
}

#[derive(PartialEq, Debug)]
enum TransactionState {
    Unsent,
    Sent,
    Acknowledged,
    Received(drtioaux::Payload),
    TimedOut,
}

/* represents transactions started by this device */
struct OutgoingTransaction {
    packet: drtioaux::Packet,
    last_action_time: u64,
    max_time: u64,
    state: TransactionState,
    requires_response: bool,  // transactions to which normal ACK is enough
    force_linkno: Option<u8>, // linkno not determined by routing table (reset packets need that)
}

impl OutgoingTransaction {
    pub fn new(packet: drtioaux::Packet, timeout: u64, requires_response: bool, force_linkno: Option<u8>) -> OutgoingTransaction {
        let last_action_time = clock::get_ms();
        OutgoingTransaction {
            packet: packet,
            last_action_time: last_action_time,
            max_time: last_action_time + timeout,
            state: TransactionState::Unsent,
            requires_response: requires_response,
            force_linkno: force_linkno,
        }
    }

    pub fn check_state(&self) -> Result<Option<drtioaux::Payload>, Error> {
        // called by subkernel handler code
        match self.state {
            TransactionState::Acknowledged => {
                if !self.requires_response { 
                    Ok(Some(drtioaux::Payload::PacketAck))
                } else {
                    Ok(None)
                }
            }
            TransactionState::Received(response) => Ok(Some(response)),
            TransactionState::TimedOut => Err(Error::Timeout),
            _ => Ok(None)
        }
    }

    pub fn record_response(&mut self, response: &drtioaux::Payload) {
        if *response == drtioaux::Payload::PacketAck && self.state == TransactionState::Sent {
            self.state = TransactionState::Acknowledged;
        } else if self.state == TransactionState::Sent || self.state == TransactionState::Acknowledged {
            self.state = TransactionState::Received(*response);
        }
    }

    pub fn can_be_deleted(&self, current_time: u64) -> bool {
        match self.state {
            TransactionState::TimedOut |
                TransactionState::Received(_) => current_time + 2*self.max_time >= self.last_action_time,
            TransactionState::Acknowledged => !self.requires_response && (current_time + 2*self.max_time >= self.last_action_time),
            _ => false
        }
    }

    pub fn should_send(&mut self, current_time: u64) -> bool {
        // returns true if message needs to be sent
        // checks for timeout first
        if (self.state == TransactionState::Unsent ||
                self.state == TransactionState::Sent ||
                self.state == TransactionState::Acknowledged) &&
                current_time > self.max_time {
            self.state = TransactionState::TimedOut;
            false
        } else {
            match self.state {
                TransactionState::Unsent => true,
                TransactionState::Sent => current_time >= self.last_action_time + DEFAULT_ACK_TIMEOUT,
                _ => false
            }
        }
    }

    pub fn update_last_action_time(&mut self, current_time: u64) {
        // state updated only after successful send
        if self.state == TransactionState::Unsent {
            self.state = TransactionState::Sent;
            self.last_action_time = current_time;
        } else if self.state == TransactionState::Sent {
            self.last_action_time = current_time;
        }
    }
}

#[derive(PartialEq)]
enum UpstreamState {
    Down,
    SettingUp,
    Up { last_action_time: u64 }
}

pub struct AuxManager {
    incoming_transactions: BTreeMap<(TransactionHandle, u8), IncomingTransaction>,
    scheduled_acks: Vec<(TransactionHandle, u8)>,
    outgoing_transactions: BTreeMap<TransactionHandle, OutgoingTransaction>,
    routable_packets: Vec<drtioaux::Packet>,
    next_id: TransactionHandle,
    self_destination: u8,
    rank: u8,
    routing_table: RefCell<drtio_routing::RoutingTable>,
    upstream_state: UpstreamState,
}

impl AuxManager {
    pub fn new() -> AuxManager {
        AuxManager {
            incoming_transactions: BTreeMap::new(),
            scheduled_acks: Vec::new(),
            outgoing_transactions: BTreeMap::new(),
            routable_packets: Vec::new(),
            next_id: 0,
            self_destination: 1,
            rank: 1,
            routing_table: RefCell::new(drtio_routing::RoutingTable::default_empty()),
            upstream_state: UpstreamState::Down
        }
    }

    pub fn transact(&mut self, destination: u8, requires_response: bool, 
        payload: drtioaux::Payload) -> Result<TransactionHandle, Error> {
        if self.outgoing_transactions.len() >= 128 {
            return Err(Error::TransactionLimitReached)
        }
        self.next_id = (self.next_id + 1) % 128;
        while self.outgoing_transactions.get(&self.next_id).is_some() {
            self.next_id = (self.next_id + 1) % 128;
        }
        let transaction_id = self.next_id;
        let transaction = OutgoingTransaction::new(
            drtioaux::Packet { 
                source: self.self_destination,
                destination: destination,
                transaction_id: transaction_id,
                payload: payload
            }, DEFAULT_TIMEOUT, requires_response, None);
        // will be dealt with by the send thread
        self.outgoing_transactions.insert(transaction_id, transaction);
        Ok(transaction_id)
    }

    pub fn rtio_reset(&mut self, repeaters: &mut [repeater::Repeater]) {
        // todo: fill it in
    }

    pub fn check_transaction(&self, transaction_id: TransactionHandle) -> Result<Option<drtioaux::Payload>, Error> {
        self.outgoing_transactions.get(&transaction_id).unwrap().check_state()
    }

    pub fn get_destination(&self, transaction_id: TransactionHandle) -> u8 {
        self.outgoing_transactions.get(&transaction_id).unwrap().packet.destination
    }

    pub fn service(&mut self, repeaters: &mut [repeater::Repeater]) {
        for rep in repeaters.iter_mut() {
            let packet = rep.service(&self.routing_table.borrow(), self.rank);
            if let Ok(Some(packet)) = packet {
                self.route_packet(&packet);
            }
        }
        if !drtiosat_link_rx_up() {
            self.upstream_state = UpstreamState::Down;
        } else {
            if self.upstream_state == UpstreamState::Down {
                self.upstream_state = UpstreamState::SettingUp;
            }
            if drtiosat_tsc_loaded() {
                info!("TSC loaded from uplink");
                for rep in repeaters.iter() {
                    if let Err(e) = rep.sync_tsc() {
                        error!("failed to sync TSC ({})", e);
                    }
                }
                if let Err(e) = drtioaux::send(0, &drtioaux::Packet {
                    source: 0, destination: 0, transaction_id: 0,
                    payload: drtioaux::Payload::TSCAck 
                }) {
                    error!("aux packet error: {}", e);
                }
            }
            // receive packets from upstream
            let upstream_recv = drtioaux::recv(0);
            if let Err(e) = upstream_recv {
                error!("error receiving packet from upstream: {:?}", e);
            } else if let Some(packet) = upstream_recv.unwrap() {
                let current_time = clock::get_ms();
                if !self.handle_setup_packet(&packet, repeaters, current_time) {
                    if self.upstream_state != UpstreamState::SettingUp {
                        self.route_packet(&packet);
                    }
                }
            }
        }
        // deal with sending and incoming transactions
        let current_time = clock::get_ms();
        // satisfy borrow checker by extracting fields we need for sending
        let routing_table = self.routing_table.borrow();
        let rank = self.rank;
        let upstream_state = &mut self.upstream_state;
        let source = self.self_destination;
    
        self.scheduled_acks.retain(|(transaction_id, destination)| {
            match send(repeaters, current_time, None,
                &routing_table, rank, upstream_state,
                &drtioaux::Packet {
                source: source,
                destination: *destination,
                transaction_id: *transaction_id,
                payload: drtioaux::Payload::PacketAck
            }) {
                Ok(value) => !value, // send returns true on successful send, retain needs false to delete element
                Err(e) => { error!("error sending ack: {:?}", e); true }
            }
        });
        self.routable_packets.retain(|packet| {
            match send(repeaters, current_time, None, 
                &routing_table, rank, upstream_state, 
                packet) {
                Ok(value) => !value,
                // repeater errors (link down) end in discarding the packet
                Err(e) => { error!("error sending routable packet: {:?}", e); false }
            }
        });
        let mut keep_vec: Vec<bool> = Vec::new();
        for (_transaction_id, transaction) in self.outgoing_transactions.iter_mut() {
            let keep = if transaction.should_send(current_time) {
                match send(repeaters, current_time, transaction.force_linkno, 
                    &routing_table, rank, upstream_state, 
                    &transaction.packet) {
                    Ok(true) => transaction.update_last_action_time(current_time),
                    Ok(false) => (),
                    Err(e) => error!("error sending outgoing transaction: {:?}", e)
                };
                true
            } else {
               !transaction.can_be_deleted(current_time)
            };
            keep_vec.push(keep);
        }
        let mut iter = keep_vec.iter();
        self.outgoing_transactions.retain(|_, _| *iter.next().unwrap() );
        self.incoming_transactions.retain(|_, transaction| {
            !transaction.can_be_deleted(current_time)
        });

    }

    fn route_packet(&mut self, packet: &drtioaux::Packet) {
        // route the packet either to local transaction or up/downstream
        if packet.destination == self.self_destination {
            if packet.payload != drtioaux::Payload::PacketAck {
                self.scheduled_acks.push((packet.transaction_id, packet.source));
            }
            if packet.payload == drtioaux::Payload::PacketAck && packet.transaction_id & 0x80 != 0 {
                // acknowledge responses
                let transaction = self.outgoing_transactions.get_mut(&packet.transaction_id);
                if let Some(local_transaction) = transaction {
                    local_transaction.record_response(&packet.payload);
                } else {
                    error!("received PacketAck for non-existing transaction")
                }
            } else {
                // incoming transactions and responses to local outgoing
                let transaction = self.outgoing_transactions.get_mut(&(packet.transaction_id & 0x7F));
                let is_expected = packet.transaction_id & 0x80 != 0 && match transaction {
                        Some(ref transaction) => transaction.packet.destination == packet.source,
                        _ => false
                    };
                if is_expected {
                    transaction.unwrap().record_response(&packet.payload);
                } else {
                    self.incoming_transactions.insert((packet.transaction_id, packet.source), IncomingTransaction::new(packet.payload));
                }
            }

        } else {
            #[cfg(has_drtio_routing)]
            self.routable_packets.push(packet.clone());
            #[cfg(not(has_drtio_routing))]
            error!("received packet to be routed without routing support: {:?}", packet);
        }
    }

    fn handle_setup_packet(&mut self, packet: &drtioaux::Packet, _repeaters: &mut [repeater::Repeater], current_time: u64) -> bool {
        // returns true if packet was consumed
        match packet.payload {
            drtioaux::Payload::EchoRequest => {
                drtioaux::send(0, &drtioaux::Packet { 
                    source: 0,
                    destination: 0,
                    transaction_id: 0,
                    payload: drtioaux::Payload::EchoReply
                }).unwrap();
                true
            }
            drtioaux::Payload::RoutingSetPath { destination: _destination, hops: _hops } => {
                #[cfg(has_drtio_routing)]
                {
                    let mut routing_table = self.routing_table.borrow_mut();
                    routing_table.0[_destination as usize] = _hops;
                    for rep in _repeaters.iter() {
                        if let Err(e) = rep.set_path(_destination, &_hops) {
                            error!("failed to set path ({})", e);
                        }
                    }
                }
                drtioaux::send(0, &drtioaux::Packet { 
                    source: 0,
                    destination: 0,
                    transaction_id: 0,
                    payload: drtioaux::Payload::RoutingAck
                }).unwrap();
                true
            }
            drtioaux::Payload::RoutingSetRank { rank } => {
                self.rank = rank;
                #[cfg(has_drtio_routing)]
                {
                    drtio_routing::interconnect_enable_all(&self.routing_table.borrow(), rank);
                    let rep_rank = rank + 1;
                    for rep in _repeaters.iter() {
                        if let Err(e) = rep.set_rank(rep_rank) {
                            error!("failed to set rank ({})", e);
                        }
                    }
                    info!("rank: {}", rank);
                    info!("routing table: {}", self.routing_table.borrow());
                }
                drtioaux::send(0, &drtioaux::Packet { 
                    source: 0,
                    destination: 0,
                    transaction_id: 0,
                    payload: drtioaux::Payload::RoutingAck
                }).unwrap();
                self.upstream_state = UpstreamState::Up { last_action_time: current_time };
                true
            }
            // DestinationStatusRequest will come only from the master, so it is not handled in route_packet
            drtioaux::Payload::DestinationStatusRequest => {
                #[cfg(has_drtio_routing)]
                if packet.destination != self.self_destination {
                    let repno = self.routing_table.borrow().0[packet.destination as usize][self.rank as usize] as usize - 1;
                    if !_repeaters[repno].is_up() {
                        self.respond(packet.source, packet.transaction_id, drtioaux::Payload::DestinationDownReply);
                        return true;
                    }
                }
                false
            }
            // packet is not consumed, returned
            _ => false
        }
    }

    pub fn respond(&mut self, transaction_id: u8, source: u8, response: drtioaux::Payload) {
        // respond to a packet (schedule a transaction reply), by
        // creating a new transaction that's satiable by an ack
        let transaction_id = transaction_id | 0x80;
        let transaction = OutgoingTransaction::new(
            drtioaux::Packet { 
                source: self.self_destination,
                destination: source,
                transaction_id: transaction_id,
                payload: response
            }, DEFAULT_TIMEOUT, false, None);
        self.outgoing_transactions.insert(transaction_id, transaction);
    }

    pub fn get_incoming_packet(&mut self, current_time: u64) -> Option<(u8, u8, drtioaux::Payload)> {
        for ((transaction_id, source), transaction) in self.incoming_transactions.iter_mut() {
            if transaction.state == IncomingTransactionState::Received {
                transaction.state = IncomingTransactionState::Handled(current_time);
                return Some((*transaction_id, *source, transaction.payload))
            }
        }
        None
    }

    pub fn self_destination(&self) -> u8 {
        self.self_destination
    }
}

fn send(_repeaters: &mut [repeater::Repeater], current_time: u64, _force_linkno: Option<u8>,
    routing_table: &drtio_routing::RoutingTable, rank: u8, upstream_state: &mut UpstreamState,
    packet: &drtioaux::Packet,
) -> Result<bool, drtioaux::Error<!>> {
    #[cfg(has_drtio_routing)]
    {
        let hop = _force_linkno.unwrap_or(routing_table.0[packet.destination as usize][rank as usize]) as usize;
        if hop > 0 && hop < csr::DRTIOREP.len() {
            let repno = (hop - 1) as usize;
            return _repeaters[repno].aux_send(current_time, packet);
        }
    }
    if let UpstreamState::Up { last_action_time } = *upstream_state {
        if current_time > last_action_time + LINK_COOLDOWN {
            drtioaux::send(0, packet)?;
            *upstream_state = UpstreamState::Up { last_action_time: current_time };
            return Ok(true);
        }
    }
    Ok(false)
}