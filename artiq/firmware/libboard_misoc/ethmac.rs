use core::{slice, fmt};
use smoltcp::Result;
use smoltcp::time::Instant;
use smoltcp::phy::{self, DeviceCapabilities, Device};

use csr;
use mem::ETHMAC_BASE;

const RX_SLOTS: usize = csr::ETHMAC_RX_SLOTS as usize;
const TX_SLOTS: usize = csr::ETHMAC_TX_SLOTS as usize;
const SLOT_SIZE: usize = csr::ETHMAC_SLOT_SIZE as usize;

fn next_rx_slot() -> Option<usize> {
    unsafe {
        if csr::ethmac::sram_writer_ev_pending_read() == 0 {
            None
        } else {
            Some(csr::ethmac::sram_writer_slot_read() as usize)
        }
    }
}

fn next_tx_slot() -> Option<usize> {
    unsafe {
        if csr::ethmac::sram_reader_ready_read() == 0 {
            None
        } else {
            Some((csr::ethmac::sram_reader_slot_read() as usize + 1) % TX_SLOTS)
        }
    }
}

fn rx_buffer(slot: usize) -> *mut u8 {
    debug_assert!(slot < RX_SLOTS);
    (ETHMAC_BASE + SLOT_SIZE * slot) as _
}

fn tx_buffer(slot: usize) -> *mut u8 {
    debug_assert!(slot < TX_SLOTS);
    (ETHMAC_BASE + SLOT_SIZE * (RX_SLOTS + slot)) as _
}

pub struct EthernetDevice(());

impl EthernetDevice {
    pub unsafe fn new() -> EthernetDevice {
        EthernetDevice(())
    }

    #[cfg(has_ethphy)]
    pub fn reset_phy(&mut self) {
        use clock;

        unsafe {
            csr::ethphy::crg_reset_write(1);
            clock::spin_us(2_000);
            csr::ethphy::crg_reset_write(0);
            clock::spin_us(2_000);
        }
    }

    pub fn reset_phy_if_any(&mut self) {
        #[cfg(has_ethphy)]
        self.reset_phy();
    }
}

impl<'a> Device<'a> for EthernetDevice {
    type RxToken = EthernetRxSlot;
    type TxToken = EthernetTxSlot;

    fn capabilities(&self) -> DeviceCapabilities {
        let mut caps = DeviceCapabilities::default();
        caps.max_transmission_unit = 1514;
        caps.max_burst_size = Some(RX_SLOTS);
        caps
    }

    fn receive(&mut self) -> Option<(Self::RxToken, Self::TxToken)> {
        if let (Some(rx_slot), Some(tx_slot)) = (next_rx_slot(), next_tx_slot()) {
            Some((EthernetRxSlot(rx_slot), EthernetTxSlot(tx_slot)))
        } else {
            None
        }
    }

    fn transmit(&mut self) -> Option<Self::TxToken> {
        if let Some(tx_slot) = next_tx_slot() {
            Some(EthernetTxSlot(tx_slot))
        } else {
            None
        }
    }
}

pub struct EthernetRxSlot(usize);

impl phy::RxToken for EthernetRxSlot {
    fn consume<R, F>(self, _timestamp: Instant, f: F) -> Result<R>
        where F: FnOnce(&mut [u8]) -> Result<R>
    {
        unsafe {
            let length = csr::ethmac::sram_writer_length_read() as usize;
            let result = f(slice::from_raw_parts_mut(rx_buffer(self.0), length));
            csr::ethmac::sram_writer_ev_pending_write(1);
            result
        }
    }
}

pub struct EthernetTxSlot(usize);

impl phy::TxToken for EthernetTxSlot {
    fn consume<R, F>(self, _timestamp: Instant, length: usize, f: F) -> Result<R>
        where F: FnOnce(&mut [u8]) -> Result<R>
    {
        debug_assert!(length < SLOT_SIZE);

        unsafe {
            let result = f(slice::from_raw_parts_mut(tx_buffer(self.0), length))?;
            csr::ethmac::sram_reader_slot_write(self.0 as u8);
            csr::ethmac::sram_reader_length_write(length as u16);
            csr::ethmac::sram_reader_start_write(1);
            Ok(result)
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct EthernetStatistics {
    rx_preamble_errors: u32,
    rx_crc_errors:      u32,
    rx_dropped:         u32,
}

impl EthernetStatistics {
    pub fn new() -> Self {
        unsafe {
            EthernetStatistics {
                rx_preamble_errors: csr::ethmac::preamble_errors_read(),
                rx_crc_errors:      csr::ethmac::crc_errors_read(),
                rx_dropped:         csr::ethmac::sram_writer_errors_read(),
            }
        }
    }

    pub fn update(&mut self) -> Option<Self> {
        let old = self.clone();
        *self = Self::new();

        let diff = EthernetStatistics {
            rx_preamble_errors: self.rx_preamble_errors.wrapping_sub(old.rx_preamble_errors),
            rx_crc_errors:      self.rx_crc_errors.wrapping_sub(old.rx_crc_errors),
            rx_dropped:         self.rx_dropped.wrapping_sub(old.rx_dropped),
        };
        if diff == EthernetStatistics::default() {
            None
        } else {
            Some(diff)
        }
    }
}

impl fmt::Display for EthernetStatistics {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        if self.rx_preamble_errors > 0 {
            write!(f, " rx preamble errors: {}", self.rx_preamble_errors)?
        }
        if self.rx_crc_errors > 0 {
            write!(f, " rx crc errors: {}", self.rx_crc_errors)?
        }
        if self.rx_dropped > 0 {
            write!(f, " rx dropped: {}", self.rx_dropped)?
        }
        Ok(())
    }
}
