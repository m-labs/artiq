use board_misoc::{csr, cache};
use board_artiq::drtioaux;
use proto_artiq::drtioaux_proto::ANALYZER_MAX_SIZE;

const BUFFER_SIZE: usize = 512 * 1024;

#[repr(align(64))]
struct Buffer {
    data: [u8; BUFFER_SIZE],
}

static mut BUFFER: Buffer = Buffer {
    data: [0; BUFFER_SIZE]
};

pub fn arm() {
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

pub fn disarm() {
    unsafe {
        csr::rtio_analyzer::enable_write(0);
        while csr::rtio_analyzer::busy_read() != 0 {}
        cache::flush_cpu_dcache();
        cache::flush_l2_cache();
    }
}

pub fn send() -> Result<(), drtioaux::Error<!>> {
    let data = unsafe { &BUFFER.data[..] };
    let overflow_occurred = unsafe { csr::rtio_analyzer::message_encoder_overflow_read() != 0 };
    let total_byte_count = unsafe { csr::rtio_analyzer::dma_byte_count_read() };
    let pointer = (total_byte_count % BUFFER_SIZE as u64) as usize;
    let wraparound = total_byte_count >= BUFFER_SIZE as u64;
    let sent_bytes = if wraparound { BUFFER_SIZE } else { total_byte_count as usize };

    drtioaux::send(0, &drtioaux::Packet::AnalyzerHeader {
        total_byte_count: total_byte_count,
        sent_bytes: sent_bytes as u32,
        overflow_occurred: overflow_occurred,
    })?;

    let mut i = if wraparound { pointer } else { 0 };
    while i < sent_bytes {
        let mut data_slice: [u8; ANALYZER_MAX_SIZE] = [0; ANALYZER_MAX_SIZE];
        let len: usize = if i + ANALYZER_MAX_SIZE < sent_bytes { ANALYZER_MAX_SIZE } else { sent_bytes - i } as usize;
        let last = i + len == sent_bytes;
        if i + len >= BUFFER_SIZE {
            data_slice[..len].clone_from_slice(&data[i..BUFFER_SIZE]);
            data_slice[..len].clone_from_slice(&data[..(i+len) % BUFFER_SIZE]);
        } else {
            data_slice[..len].clone_from_slice(&data[i..i+len]);
        }
        i += len;
        drtioaux::send(0, &drtioaux::Packet::AnalyzerData {
            last: last,
            length: len as u16,
            data: data_slice,
        })?;
    }

    Ok(())
}
