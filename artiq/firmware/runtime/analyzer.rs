use io::{Write, Error as IoError};
#[cfg(has_drtio)]
use alloc::vec::Vec;
use board_misoc::{csr, cache};
use sched::{Io, Mutex, TcpListener, TcpStream, Error as SchedError};
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
    
    pub struct RemoteBuffer {
        pub total_byte_count: u64,
        pub sent_bytes: u32,
        pub overflow_occurred: bool,
        pub data: Vec<u8>
    }

    pub fn get_data(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, routing_table: &drtio_routing::RoutingTable,
        up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>
    ) -> Result<RemoteBuffer, drtio::Error> {
            // gets data from satellites and returns consolidated data
            let mut remote_data: Vec<u8> = Vec::new();
            let mut remote_overflow = false;
            let mut remote_sent_bytes = 0;
            let mut remote_total_bytes = 0;

            let data_vec = drtio::analyzer_query(
                io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, up_destinations
            )?;
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
}   



fn worker(stream: &mut TcpStream, _io: &Io, _aux_mutex: &Mutex,
    _ddma_mutex: &Mutex, _subkernel_mutex: &Mutex,
    _routing_table: &drtio_routing::RoutingTable,
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
        _io, _aux_mutex, _ddma_mutex, _subkernel_mutex, _routing_table, _up_destinations);
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

pub fn thread(io: Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
    routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
    up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {
    let listener = TcpListener::new(&io, 65535);
    listener.listen(1382).expect("analyzer: cannot listen");

    loop {
        arm();

        let mut stream = listener.accept().expect("analyzer: cannot accept");
        info!("connection from {}", stream.remote_endpoint());

        disarm();

        let routing_table = routing_table.borrow();
        match worker(&mut stream, &io, aux_mutex, ddma_mutex, subkernel_mutex, &routing_table, up_destinations) {
            Ok(())   => (),
            Err(err) => error!("analyzer aborted: {}", err)
        }

        stream.close().expect("analyzer: close socket")
    }
}
