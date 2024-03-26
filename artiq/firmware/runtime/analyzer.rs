use io::{Write, Error as IoError};
#[cfg(has_drtio)]
use alloc::vec::Vec;
use board_misoc::{csr, cache};
use sched::{Io, TcpListener, TcpStream, Error as SchedError};
use analyzer_proto::*;
use urc::Urc;
use board_artiq::drtio_routing;
use core::cell::RefCell;

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

#[cfg(has_drtio)]
pub mod remote_analyzer {
    use super::*;
    use rtio_mgt::drtio;
    use board_artiq::drtioaux;
    
    pub struct RemoteBuffer {
        pub total_byte_count: u64,
        pub sent_bytes: u32,
        pub overflow_occurred: bool,
        pub data: Vec<u8>
    }

    pub fn get_data(io: &Io, up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>
    ) -> Result<RemoteBuffer, drtio::Error> {
            // gets data from satellites and returns consolidated data
            let mut remote_data: Vec<u8> = Vec::new();
            let mut remote_overflow = false;
            let mut remote_sent_bytes = 0;
            let mut remote_total_bytes = 0;

            let data_vec = remote_query(io, up_destinations)?;
            for data in data_vec {
                remote_total_bytes += data.total_byte_count;
                remote_sent_bytes += data.sent_bytes;
                remote_overflow |= data.overflow_occurred;
                remote_data.extend(data.data);
            }

            Ok(RemoteBuffer {
                total_byte_count: remote_total_bytes,
                sent_bytes: remote_sent_bytes,
                overflow_occurred: remote_overflow,
                data: remote_data
            })
        }

    fn download_data(io: &Io, destination: u8) -> Result<RemoteBuffer, drtio::Error> {
        let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true,
            drtioaux::Payload::AnalyzerHeaderRequest)?;
        let (sent, total, overflow) = match reply {
            drtioaux::Payload::AnalyzerHeader { sent_bytes, total_byte_count, overflow_occurred } => 
                (sent_bytes, total_byte_count, overflow_occurred),
            packet => return Err(drtio::Error::UnexpectedPacket(packet)),
        };

        let mut remote_data: Vec<u8> = Vec::new();
        if sent > 0 {
            let mut last_packet = false;
            while !last_packet {
                let reply = drtio::aux_transact(io, destination, drtio::DEFAULT_TIMEOUT, true, 
                    drtioaux::Payload::AnalyzerDataRequest)?;
                match reply {
                    drtioaux::Payload::AnalyzerData { last, length, data } => { 
                        last_packet = last;
                        remote_data.extend(&data[0..length as usize]);
                    },
                    packet => return Err(drtio::Error::UnexpectedPacket(packet)),
                }
            }
        }

        Ok(RemoteBuffer {
            sent_bytes: sent,
            total_byte_count: total,
            overflow_occurred: overflow,
            data: remote_data
        })
    }

    fn remote_query(io: &Io, up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>
    ) -> Result<Vec<RemoteBuffer>, drtio::Error> {
        let mut remote_buffers: Vec<RemoteBuffer> = Vec::new();
        for i in 1..drtio_routing::DEST_COUNT {
            if drtio::destination_up(up_destinations, i as u8) {
                remote_buffers.push(download_data(io, i as u8)?);
            }
        }
        Ok(remote_buffers)
    }
    
}   


fn worker(stream: &mut TcpStream, _io: &Io,
    _up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>
) -> Result<(), IoError<SchedError>> {
    let local_data = unsafe { &BUFFER.data[..] };
    let local_overflow_occurred = unsafe { csr::rtio_analyzer::message_encoder_overflow_read() != 0 };
    let local_total_byte_count = unsafe { csr::rtio_analyzer::dma_byte_count_read() };

    let wraparound = local_total_byte_count >= BUFFER_SIZE as u64;
    let local_sent_bytes = if wraparound { BUFFER_SIZE as u32 } else { local_total_byte_count as u32 };
    let pointer = (local_total_byte_count % BUFFER_SIZE as u64) as usize;

    #[cfg(has_drtio)]
    let remote = remote_analyzer::get_data(
        _io, _up_destinations);
    #[cfg(has_drtio)]
    let (header, remote_data) = match remote {
        Ok(remote) => (Header {
            total_byte_count: local_total_byte_count + remote.total_byte_count,
            sent_bytes: local_sent_bytes + remote.sent_bytes,
            overflow_occurred: local_overflow_occurred | remote.overflow_occurred,
            log_channel: csr::CONFIG_RTIO_LOG_CHANNEL as u8,
            dds_onehot_sel: true 
        }, remote.data),
        Err(e) => {
            error!("Error getting remote analyzer data: {}", e);
            (Header {
                total_byte_count: local_total_byte_count,
                sent_bytes: local_sent_bytes,
                overflow_occurred: true,
                log_channel: csr::CONFIG_RTIO_LOG_CHANNEL as u8,
                dds_onehot_sel: true 
            },
            Vec::new())
        }
    };

    #[cfg(not(has_drtio))]
    let header = Header {
        total_byte_count: local_total_byte_count,
        sent_bytes: local_sent_bytes,
        overflow_occurred: local_overflow_occurred,
        log_channel: csr::CONFIG_RTIO_LOG_CHANNEL as u8,
        dds_onehot_sel: true  // kept for backward compatibility of analyzer dumps
    };
    debug!("{:?}", header);

    stream.write_all("e".as_bytes())?;
    header.write_to(stream)?;
    if wraparound {
        stream.write_all(&local_data[pointer..])?;
        stream.write_all(&local_data[..pointer])?;
    } else {
        stream.write_all(&local_data[..pointer])?;
    }
    #[cfg(has_drtio)]
    stream.write_all(&remote_data)?;

    Ok(())
}

pub fn thread(io: Io,
    up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {
    let listener = TcpListener::new(&io, 65535);
    listener.listen(1382).expect("analyzer: cannot listen");

    loop {
        arm();

        let mut stream = listener.accept().expect("analyzer: cannot accept");
        info!("connection from {}", stream.remote_endpoint());

        disarm();

        match worker(&mut stream, &io, up_destinations) {
            Ok(())   => (),
            Err(err) => error!("analyzer aborted: {}", err)
        }

        stream.close().expect("analyzer: close socket")
    }
}
