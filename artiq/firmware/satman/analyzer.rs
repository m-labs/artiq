use core::cmp::min;
use board_misoc::{csr, cache};
use proto_artiq::drtioaux_proto::SAT_PAYLOAD_MAX_SIZE;

const BUFFER_SIZE: usize = 512 * 1024;

#[repr(align(64))]
struct Buffer {
    data: [u8; BUFFER_SIZE],
}

static mut BUFFER: Buffer = Buffer {
    data: [0; BUFFER_SIZE]
};

fn arm() {
    unsafe {
        let base_addr = &mut BUFFER.data[0] as *mut _ as usize;
        let last_addr = &mut BUFFER.data[BUFFER_SIZE - 1] as *mut _ as usize;
        csr::rtio_analyzer::message_encoder_overflow_reset_write(1);
        csr::rtio_analyzer::dma_base_address_write(base_addr as u64);
        csr::rtio_analyzer::dma_last_address_write(last_addr as u64);
        csr::rtio_analyzer::dma_reset_write(1);
        csr::rtio_analyzer::enable_write(1);
    }
}

fn disarm() {
    unsafe {
        csr::rtio_analyzer::enable_write(0);
        while csr::rtio_analyzer::busy_read() != 0 {}
        cache::flush_cpu_dcache();
        cache::flush_l2_cache();
    }
}

pub struct Analyzer {
    // necessary for keeping track of sent data
    data_len: usize,
    sent_bytes: usize,
    data_pointer: usize
}

pub struct Header {
    pub total_byte_count: u64,
    pub sent_bytes: u32,
    pub overflow: bool
}

pub struct AnalyzerSliceMeta {
    pub len: u16,
    pub last: bool
}

impl Drop for Analyzer {
    fn drop(&mut self) {
        disarm();
    }
}

impl Analyzer {
    pub fn new() -> Analyzer {
        // create and arm new Analyzer
        arm();
        Analyzer {
            data_len: 0,
            sent_bytes: 0,
            data_pointer: 0
        }
    }

    pub fn get_header(&mut self) -> Header {
        disarm();

        let overflow = unsafe { csr::rtio_analyzer::message_encoder_overflow_read() != 0 };
        let total_byte_count = unsafe { csr::rtio_analyzer::dma_byte_count_read() };
        let wraparound = total_byte_count >= BUFFER_SIZE as u64;
        self.data_len = if wraparound { BUFFER_SIZE } else { total_byte_count as usize };
        self.data_pointer = if wraparound { (total_byte_count % BUFFER_SIZE as u64) as usize } else { 0 };
        self.sent_bytes = 0;

        Header {
            total_byte_count: total_byte_count,
            sent_bytes: self.data_len as u32,
            overflow: overflow
        }
    }

    pub fn get_data(&mut self, data_slice: &mut [u8; SAT_PAYLOAD_MAX_SIZE]) -> AnalyzerSliceMeta {
        let data = unsafe { &BUFFER.data[..] };
        let i = (self.data_pointer + self.sent_bytes) % BUFFER_SIZE;
        let len = min(SAT_PAYLOAD_MAX_SIZE, self.data_len - self.sent_bytes);
        let last = self.sent_bytes + len == self.data_len;

        if i + len >= BUFFER_SIZE {
            data_slice[..(BUFFER_SIZE-i)].clone_from_slice(&data[i..BUFFER_SIZE]);
            data_slice[(BUFFER_SIZE-i)..len].clone_from_slice(&data[..(i + len) % BUFFER_SIZE]);
        } else {
            data_slice[..len].clone_from_slice(&data[i..i+len]);
        }
        self.sent_bytes += len;

        if last {
            arm();
        }
        
        AnalyzerSliceMeta {
            len: len as u16,
            last: last
        }
    }
}
