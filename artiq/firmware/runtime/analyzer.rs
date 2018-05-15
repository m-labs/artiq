use io::{Write, Error as IoError};
use board_misoc::{csr, cache};
use sched::{Io, TcpListener, TcpStream, Error as SchedError};
use analyzer_proto::*;

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

fn worker(stream: &mut TcpStream) -> Result<(), IoError<SchedError>> {
    let data = unsafe { &BUFFER.data[..] };
    let overflow_occurred = unsafe { csr::rtio_analyzer::message_encoder_overflow_read() != 0 };
    let total_byte_count = unsafe { csr::rtio_analyzer::dma_byte_count_read() };
    let pointer = (total_byte_count % BUFFER_SIZE as u64) as usize;
    let wraparound = total_byte_count >= BUFFER_SIZE as u64;

    let header = Header {
        total_byte_count: total_byte_count,
        sent_bytes: if wraparound { BUFFER_SIZE as u32 } else { total_byte_count as u32 },
        overflow_occurred: overflow_occurred,
        log_channel: csr::CONFIG_RTIO_LOG_CHANNEL as u8,
        dds_onehot_sel: true  // kept for backward compatibility of analyzer dumps
    };
    debug!("{:?}", header);

    header.write_to(stream)?;
    if wraparound {
        stream.write_all(&data[pointer..])?;
        stream.write_all(&data[..pointer])?;
    } else {
        stream.write_all(&data[..pointer])?;
    }

    Ok(())
}

pub fn thread(io: Io) {
    let listener = TcpListener::new(&io, 65535);
    listener.listen(1382).expect("analyzer: cannot listen");

    loop {
        arm();

        let mut stream = listener.accept().expect("analyzer: cannot accept");
        info!("connection from {}", stream.remote_endpoint());

        disarm();

        match worker(&mut stream) {
            Ok(())   => (),
            Err(err) => error!("analyzer aborted: {}", err)
        }
    }
}
