use std::io::{self, Write};
use board::{self, csr};
use sched::{Io, TcpSocket};
use analyzer_proto::*;

const BUFFER_SIZE: usize = 512 * 1024;

// hack until https://github.com/rust-lang/rust/issues/33626 is fixed
#[repr(simd)]
struct Align64(u64, u64, u64, u64, u64, u64, u64, u64);

struct Buffer {
    data: [u8; BUFFER_SIZE],
    __alignment: [Align64; 0]
}

static mut BUFFER: Buffer = Buffer {
    data: [0; BUFFER_SIZE],
    __alignment: []
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
        board::flush_cpu_dcache();
        board::flush_l2_cache();
    }
}

fn worker(socket: &mut TcpSocket) -> io::Result<()> {
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
    trace!("{:?}", header);

    try!(header.write_to(socket));
    if wraparound {
        try!(socket.write_all(&data[pointer..]));
        try!(socket.write_all(&data[..pointer]));
    } else {
        try!(socket.write_all(&data[..pointer]));
    }

    Ok(())
}

pub fn thread(io: Io) {
    // verify that the hack above works
    assert!(::core::mem::align_of::<Buffer>() == 64);

    let mut socket = TcpSocket::with_buffer_size(&io, 65535);
    loop {
        arm();

        socket.listen(1382).expect("analyzer: cannot listen");
        socket.accept().expect("analyzer: cannot accept");
        info!("connection from {}", socket.remote_endpoint());

        disarm();

        match worker(&mut socket) {
            Ok(())   => (),
            Err(err) => error!("analyzer aborted: {}", err)
        }
        socket.close().expect("analyzer: cannot close");
    }
}
