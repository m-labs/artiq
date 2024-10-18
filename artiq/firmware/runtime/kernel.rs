use board_misoc::csr;
use core::{ptr, slice};
use mailbox;
use rpc_queue;

use kernel_proto::{KERNELCPU_EXEC_ADDRESS, KERNELCPU_LAST_ADDRESS, KSUPPORT_HEADER_SIZE};

#[cfg(has_kernel_cpu)]
pub unsafe fn start() {
    if csr::kernel_cpu::reset_read() == 0 {
        panic!("attempted to start kernel CPU when it is already running")
    }

    stop();

    extern "C" {
        static _binary____ksupport_ksupport_elf_start: u8;
        static _binary____ksupport_ksupport_elf_end: u8;
    }
    let ksupport_elf_start = &_binary____ksupport_ksupport_elf_start as *const u8;
    let ksupport_elf_end = &_binary____ksupport_ksupport_elf_end as *const u8;
    let ksupport_elf = slice::from_raw_parts(
        ksupport_elf_start,
        ksupport_elf_end as usize - ksupport_elf_start as usize,
    );

    if let Err(msg) = load_image(&ksupport_elf) {
        panic!("failed to load kernel CPU image (ksupport.elf): {}", msg);
    }

    csr::kernel_cpu::reset_write(0);

    rpc_queue::init();
}

#[cfg(not(has_kernel_cpu))]
pub unsafe fn start() {
    unimplemented!("not(has_kernel_cpu)")
}

pub unsafe fn stop() {
    #[cfg(has_kernel_cpu)]
    csr::kernel_cpu::reset_write(1);

    mailbox::acknowledge();
    rpc_queue::init();
}

/// Loads the given image for execution on the kernel CPU.
///
/// The entire image including the headers is copied into memory for later use by libunwind, but
/// placed such that the text section ends up at the right location in memory. Currently, we just
/// hard-code the address range, but at least verify that this matches the ELF program header given
/// in the image (avoids loading the – non-relocatable – code at the wrong address on toolchain/…
/// changes).
unsafe fn load_image(image: &[u8]) -> Result<(), &'static str> {
    use dyld::elf::*;
    use dyld::{is_elf_for_current_arch, read_unaligned};

    let ehdr = read_unaligned::<Elf32_Ehdr>(image, 0).map_err(|()| "could not read ELF header")?;

    // The check assumes the two CPUs share the same architecture. This is just to avoid inscrutable
    // errors; we do not functionally rely on this.
    if !is_elf_for_current_arch(&ehdr, ET_EXEC) {
        return Err("not an executable for kernel CPU architecture");
    }

    // First program header should be the main text/… LOAD (see ksupport.ld).
    let phdr = read_unaligned::<Elf32_Phdr>(image, ehdr.e_phoff as usize)
        .map_err(|()| "could not read program header")?;
    if phdr.p_type != PT_LOAD {
        return Err("unexpected program header type");
    }
    if phdr.p_vaddr + phdr.p_memsz > KERNELCPU_LAST_ADDRESS as u32 {
        // This is a weak sanity check only; we also need to fit in the stack, etc.
        return Err("too large for kernel CPU address range");
    }
    const TARGET_ADDRESS: u32 = (KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE) as _;
    if phdr.p_vaddr - phdr.p_offset != TARGET_ADDRESS {
        return Err("unexpected load address/offset");
    }

    ptr::copy_nonoverlapping(image.as_ptr(), TARGET_ADDRESS as *mut u8, image.len());
    Ok(())
}

pub fn validate(ptr: usize) -> bool {
    ptr >= KERNELCPU_EXEC_ADDRESS && ptr <= KERNELCPU_LAST_ADDRESS
}


#[cfg(has_drtio)]
pub mod subkernel {
    use alloc::{vec::Vec, collections::btree_map::BTreeMap};
    use board_artiq::drtio_routing::RoutingTable;
    use board_misoc::clock;
    use proto_artiq::{drtioaux_proto::{PayloadStatus, MASTER_PAYLOAD_MAX_SIZE}, rpc_proto as rpc};
    use io::{Cursor, ProtoRead};
    use eh::eh_artiq::Exception;
    use cslice::CSlice;
    use rtio_mgt::drtio;
    use sched::{Io, Mutex, Error as SchedError};

    #[derive(Debug, PartialEq, Clone, Copy)]
    pub enum FinishStatus {
        Ok,
        CommLost,
        Exception(u8) // exception source
    }

    #[derive(Debug, PartialEq, Clone, Copy)]
    pub enum SubkernelState {
        NotLoaded,
        Uploaded,
        Running,
        Finished { status: FinishStatus },
    }

    #[derive(Fail, Debug)]
    pub enum Error {
        #[fail(display = "Timed out waiting for subkernel")]
        Timeout,
        #[fail(display = "Subkernel is in incorrect state for the given operation")]
        IncorrectState,
        #[fail(display = "DRTIO error: {}", _0)]
        DrtioError(#[cause] drtio::Error),
        #[fail(display = "scheduler error: {}", _0)]
        SchedError(#[cause] SchedError),
        #[fail(display = "rpc io error")]
        RpcIoError,
        #[fail(display = "subkernel finished prematurely")]
        SubkernelFinished,
    }

    impl From<drtio::Error> for Error {
        fn from(value: drtio::Error) -> Error {
            match value {
                drtio::Error::SchedError(x) => Error::SchedError(x),
                x => Error::DrtioError(x),
            }
        }
    }

    impl From<SchedError> for Error {
        fn from(value: SchedError) -> Error {
                Error::SchedError(value)
        }
    }

    impl From<io::Error<!>> for Error {
        fn from(_value: io::Error<!>) -> Error  {
            Error::RpcIoError
        }
    }

    pub struct SubkernelFinished {
        pub id: u32,
        pub comm_lost: bool,
        pub exception: Option<Vec<u8>>
    }

    struct Subkernel {
        pub destination: u8,
        pub data: Vec<u8>,
        pub state: SubkernelState
    }

    impl Subkernel {
        pub fn new(destination: u8, data: Vec<u8>) -> Self {
            Subkernel {
                destination: destination,
                data: data,
                state: SubkernelState::NotLoaded
            }
        }
    }

    static mut SUBKERNELS: BTreeMap<u32, Subkernel> = BTreeMap::new();

    pub fn add_subkernel(io: &Io, subkernel_mutex: &Mutex, id: u32, destination: u8, kernel: Vec<u8>) -> Result<(), Error> {
        let _lock = subkernel_mutex.lock(io)?;
        unsafe { SUBKERNELS.insert(id, Subkernel::new(destination, kernel)); }
        Ok(())
    }

    pub fn upload(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, 
             routing_table: &RoutingTable, id: u32) -> Result<(), Error> {
        let _lock = subkernel_mutex.lock(io)?;
        let subkernel = unsafe { SUBKERNELS.get_mut(&id).unwrap() };
        drtio::subkernel_upload(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, id, 
            subkernel.destination, &subkernel.data)?;
        subkernel.state = SubkernelState::Uploaded; 
        Ok(()) 
    }

    pub fn load(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, routing_table: &RoutingTable,
            id: u32, run: bool, timestamp: u64) -> Result<(), Error> {
        let _lock = subkernel_mutex.lock(io)?;
        let subkernel = unsafe { SUBKERNELS.get_mut(&id).unwrap() };
        if subkernel.state != SubkernelState::Uploaded {
            error!("for id: {} expected Uploaded, got: {:?}", id, subkernel.state);
            return Err(Error::IncorrectState);
        }
        drtio::subkernel_load(io, aux_mutex, ddma_mutex, subkernel_mutex, 
            routing_table, id, subkernel.destination, run, timestamp)?;
        if run {
            subkernel.state = SubkernelState::Running;
        }
        Ok(())
    }

    pub fn clear_subkernels(io: &Io, subkernel_mutex: &Mutex) -> Result<(), Error> {
        let _lock = subkernel_mutex.lock(io)?;
        unsafe {
            SUBKERNELS = BTreeMap::new();
            MESSAGE_QUEUE = Vec::new();
            CURRENT_MESSAGES = BTreeMap::new();
        }
        Ok(())
    }

    pub fn subkernel_finished(io: &Io, subkernel_mutex: &Mutex, id: u32, with_exception: bool, exception_src: u8) {
        // called upon receiving DRTIO SubkernelRunDone
        let _lock = subkernel_mutex.lock(io).unwrap();
        let subkernel = unsafe { SUBKERNELS.get_mut(&id) };
        // may be None if session ends and is cleared
        if let Some(subkernel) = subkernel {
            // ignore other messages, could be a late finish reported
            if subkernel.state == SubkernelState::Running {
                subkernel.state = SubkernelState::Finished {
                    status: match with_exception {
                        true => FinishStatus::Exception(exception_src),
                        false => FinishStatus::Ok,
                    }
                }
            }
        }
    }

    pub fn destination_changed(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
             routing_table: &RoutingTable, destination: u8, up: bool) {
        let _lock = subkernel_mutex.lock(io).unwrap();
        let subkernels_iter = unsafe { SUBKERNELS.iter_mut() };
        for (id, subkernel) in subkernels_iter {
            if subkernel.destination == destination {
                if up {
                    match drtio::subkernel_upload(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, *id, destination, &subkernel.data)
                    {
                        Ok(_) => subkernel.state = SubkernelState::Uploaded,
                        Err(e) => error!("Error adding subkernel on destination {}: {}", destination, e)
                    }
                } else {
                    subkernel.state = match subkernel.state {
                        SubkernelState::Running => SubkernelState::Finished { status: FinishStatus::CommLost },
                        _ => SubkernelState::NotLoaded,
                    }
                }
            }
        }
    }

    fn read_exception_string<'a>(reader: &mut Cursor<&[u8]>) -> Result<CSlice<'a, u8>, Error> {
        let len = reader.read_u32()? as usize;
        if len == usize::MAX {
            let data = reader.read_u32()?;
            Ok(unsafe { CSlice::new(data as *const u8, len) })
        } else {
            let pos = reader.position();
            let slice = unsafe {
                let ptr = reader.get_ref().as_ptr().offset(pos as isize);
                CSlice::new(ptr, len)
            };
            reader.set_position(pos + len);
            Ok(slice)
        }
    }

    pub fn read_exception(buffer: &[u8]) -> Result<Exception, Error>
    {
        let mut reader = Cursor::new(buffer);

        let mut byte = reader.read_u8()?;
        // to sync
        while byte != 0x5a {
            byte = reader.read_u8()?;
        }
        // skip sync bytes, 0x09 indicates exception
        while byte != 0x09 {
            byte = reader.read_u8()?;
        }
        let _len = reader.read_u32()?;
        // ignore the remaining exceptions, stack traces etc. - unwinding from another device would be unwise anyway
        Ok(Exception {
            id:       reader.read_u32()?,
            message:  read_exception_string(&mut reader)?,
            param:    [reader.read_u64()? as i64, reader.read_u64()? as i64, reader.read_u64()? as i64],
            file:     read_exception_string(&mut reader)?,
            line:     reader.read_u32()?,
            column:   reader.read_u32()?,
            function: read_exception_string(&mut reader)?
        })
    }


    pub fn retrieve_finish_status(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &RoutingTable, id: u32) -> Result<SubkernelFinished, Error> {
        let _lock = subkernel_mutex.lock(io)?;
        let mut subkernel = unsafe { SUBKERNELS.get_mut(&id).unwrap() };
        match subkernel.state {
            SubkernelState::Finished { status } => {
                subkernel.state = SubkernelState::Uploaded;
                Ok(SubkernelFinished {
                    id: id,
                    comm_lost: status == FinishStatus::CommLost,
                    exception: if let FinishStatus::Exception(dest) = status { 
                        Some(drtio::subkernel_retrieve_exception(io, aux_mutex, ddma_mutex, subkernel_mutex,
                            routing_table, dest)?) 
                    } else { None }
                })
            },
            _ => {
                Err(Error::IncorrectState)
            }
        }
    }

    pub fn await_finish(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &RoutingTable, id: u32, timeout: i64) -> Result<SubkernelFinished, Error> {
        {
            let _lock = subkernel_mutex.lock(io)?;
            match unsafe { SUBKERNELS.get(&id).unwrap().state } {
                SubkernelState::Running | SubkernelState::Finished { .. } => (),
                _ => {
                    return Err(Error::IncorrectState);
                }
            }
        }
        let max_time = clock::get_ms() + timeout as u64;
        let _res = io.until(|| {
            if timeout > 0 && clock::get_ms() > max_time {
                return true;
            }
            if subkernel_mutex.test_lock() {
                // cannot lock again within io.until - scheduler guarantees
                // that it will not be interrupted - so only test the lock
                return false;
            }
            let subkernel = unsafe { SUBKERNELS.get(&id).unwrap() };
            match subkernel.state {
                SubkernelState::Finished { .. } => true,
                _ => false
            }
        })?;
        if timeout > 0 && clock::get_ms() > max_time {
            error!("Remote subkernel finish await timed out");
            return Err(Error::Timeout);
        }
        retrieve_finish_status(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, id)
    }

    pub struct Message {
        from_id: u32,
        pub count: u8,
        pub data: Vec<u8>
    }

    // FIFO queue of messages
    static mut MESSAGE_QUEUE: Vec<Message> = Vec::new();
    // currently under construction message(s) (can be from multiple sources)
    static mut CURRENT_MESSAGES: BTreeMap<u32, Message> = BTreeMap::new();

    pub fn message_handle_incoming(io: &Io, subkernel_mutex: &Mutex, 
        id: u32, status: PayloadStatus, length: usize, data: &[u8; MASTER_PAYLOAD_MAX_SIZE]) {
        // called when receiving a message from satellite
        let _lock = match subkernel_mutex.lock(io) {
            Ok(lock) => lock,
            // may get interrupted, when session is cancelled or main kernel finishes without await
            Err(_) => return,
        };
        let subkernel = unsafe { SUBKERNELS.get(&id) };
        if subkernel.is_some() && subkernel.unwrap().state != SubkernelState::Running {
            warn!("received a message for a non-running subkernel #{}", id);
            // do not add messages for non-running or deleted subkernels
            return
        }
        if status.is_first() {
            unsafe {
                CURRENT_MESSAGES.remove(&id);
            }
        }
        match unsafe { CURRENT_MESSAGES.get_mut(&id) } {
            Some(message) => message.data.extend(&data[..length]),
            None => unsafe {
                CURRENT_MESSAGES.insert(id, Message {
                    from_id: id,
                    count: data[0],
                    data: data[1..length].to_vec()
                });
            }
        };
        if status.is_last() {
            unsafe { 
                // when done, remove from working queue
                MESSAGE_QUEUE.push(CURRENT_MESSAGES.remove(&id).unwrap());
            };
        }
    }

    pub fn message_await(io: &Io, subkernel_mutex: &Mutex, id: u32, timeout: i64
    ) -> Result<Message, Error> {
        let is_subkernel = {
            let _lock = subkernel_mutex.lock(io)?;
            let is_subkernel = unsafe { SUBKERNELS.get(&id).is_some() };
            if is_subkernel {
            match unsafe { SUBKERNELS.get(&id).unwrap().state } {
                SubkernelState::Finished { status: FinishStatus::Ok } |
                SubkernelState::Running => (),
                SubkernelState::Finished {
                    status: FinishStatus::CommLost,
                    } => return Err(Error::SubkernelFinished),
                _ => return Err(Error::IncorrectState)
            }
        }
            is_subkernel
        };
        let max_time = clock::get_ms() + timeout as u64;
        let message = io.until_ok(|| {
            if timeout > 0 && clock::get_ms() > max_time {
                return Ok(None);
            }
            if subkernel_mutex.test_lock() {
                return Err(());
            }
            let msg_len = unsafe { MESSAGE_QUEUE.len() };
            for i in 0..msg_len {
                let msg = unsafe { &MESSAGE_QUEUE[i] };
                if msg.from_id == id {
                    return Ok(Some(unsafe { MESSAGE_QUEUE.remove(i) }));
                }
            }
            if is_subkernel {
            match unsafe { SUBKERNELS.get(&id).unwrap().state } {
                SubkernelState::Finished { status: FinishStatus::CommLost } | 
                    SubkernelState::Finished { status: FinishStatus::Exception(_) }  => return Ok(None),
                _ => ()
                }
            }
            Err(())
        });
        match message {
            Ok(Some(message)) => Ok(message),
            Ok(None) => {
                if clock::get_ms() > max_time {
                    Err(Error::Timeout)
                } else {
                    let _lock = subkernel_mutex.lock(io)?;
                    match unsafe { SUBKERNELS.get(&id).unwrap().state } {
                        SubkernelState::Finished { .. } => Err(Error::SubkernelFinished),
                        _ => Err(Error::IncorrectState)
                    }
                }
            }
            Err(e) => Err(Error::SchedError(e)),
        }
    }

    pub fn message_send<'a>(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &RoutingTable, id: u32, destination: Option<u8>, count: u8, tag: &'a [u8], message: *const *const ()
    ) -> Result<(), Error> {
        let mut writer = Cursor::new(Vec::new());
        // reuse rpc code for sending arbitrary data
        rpc::send_args(&mut writer, 0, tag, message, false)?;
        // skip service tag, but overwrite first byte with tag count
        let destination = destination.unwrap_or_else(|| {
                let _lock = subkernel_mutex.lock(io).unwrap();
                unsafe { SUBKERNELS.get(&id).unwrap().destination }
            }
        );
        let data = &mut writer.into_inner()[3..];
        data[0] = count;
        Ok(drtio::subkernel_send_message(
            io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, id, destination, data
        )?)
    }
}