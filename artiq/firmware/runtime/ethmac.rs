use core::slice;
use board::{csr, mem};
use smoltcp::Error;
use smoltcp::phy::{DeviceLimits, Device};

const RX_SLOTS: usize = csr::ETHMAC_RX_SLOTS as usize;
const TX_SLOTS: usize = csr::ETHMAC_TX_SLOTS as usize;
const SLOT_SIZE: usize = csr::ETHMAC_SLOT_SIZE as usize;

fn rx_buffer(slot: usize) -> *const u8 {
    debug_assert!(slot < RX_SLOTS);
    (mem::ETHMAC_BASE + SLOT_SIZE * slot) as _
}

fn tx_buffer(slot: usize) -> *mut u8 {
    debug_assert!(slot < TX_SLOTS);
    (mem::ETHMAC_BASE + SLOT_SIZE * (RX_SLOTS + slot)) as _
}

pub struct EthernetDevice;

impl Device for EthernetDevice {
    type RxBuffer = RxBuffer;
    type TxBuffer = TxBuffer;

    fn limits(&self) -> DeviceLimits {
        let mut limits = DeviceLimits::default();
        limits.max_transmission_unit = 1514;
        limits.max_burst_size = Some(RX_SLOTS);
        limits
    }

    fn receive(&mut self, _timestamp: u64) -> Result<Self::RxBuffer, Error> {
        unsafe {
            if csr::ethmac::sram_writer_ev_pending_read() == 0 {
                return Err(Error::Exhausted)
            }

            let slot = csr::ethmac::sram_writer_slot_read() as usize;
            let length = csr::ethmac::sram_writer_length_read() as usize;
            Ok(RxBuffer(slice::from_raw_parts(rx_buffer(slot), length)))
        }
    }

    fn transmit(&mut self, _timestamp: u64, length: usize) -> Result<Self::TxBuffer, Error> {
        unsafe {
            if csr::ethmac::sram_reader_ready_read() == 0 {
                return Err(Error::Exhausted)
            }

            let slot = csr::ethmac::sram_reader_slot_read() as usize;
            let slot = (slot + 1) % TX_SLOTS;
            csr::ethmac::sram_reader_slot_write(slot as u8);
            csr::ethmac::sram_reader_length_write(length as u16);
            Ok(TxBuffer(slice::from_raw_parts_mut(tx_buffer(slot), length)))
        }
    }
}

pub struct RxBuffer(&'static [u8]);

impl AsRef<[u8]> for RxBuffer {
    fn as_ref(&self) -> &[u8] { self.0 }
}

impl Drop for RxBuffer {
    fn drop(&mut self) {
        unsafe { csr::ethmac::sram_writer_ev_pending_write(1) }
    }
}

pub struct TxBuffer(&'static mut [u8]);

impl AsRef<[u8]> for TxBuffer {
    fn as_ref(&self) -> &[u8] { self.0 }
}

impl AsMut<[u8]> for TxBuffer {
    fn as_mut(&mut self) -> &mut [u8] { self.0 }
}

impl Drop for TxBuffer {
    fn drop(&mut self) {
        unsafe { csr::ethmac::sram_reader_start_write(1) }
    }
}
