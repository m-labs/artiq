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
    use core::str;
    use board_artiq::drtio_routing::RoutingTable;
    use board_misoc::clock;
    use proto_artiq::{drtioaux_proto::MASTER_PAYLOAD_MAX_SIZE, rpc_proto as rpc};
    use io::Cursor;
    use rtio_mgt::drtio;
    use sched::{Io, Mutex};


    #[derive(Debug, PartialEq, Clone)]
    pub enum SubkernelState {
        NotLoaded,
        Uploaded,
        Loaded,
        Running,
        FinishedAbnormally { comm_lost: bool, with_exception: bool },
        Finished,
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

    pub fn add_subkernel(io: &Io, subkernel_mutex: &Mutex, id: u32, destination: u8, kernel: Vec<u8>) {
        let _lock = subkernel_mutex.lock(io).unwrap();
        unsafe { SUBKERNELS.insert(id, Subkernel::new(destination, kernel)); }
    }

    pub fn upload(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, 
             routing_table: &RoutingTable, id: u32) -> Result<(), &'static str> {
        let _lock = subkernel_mutex.lock(io).unwrap();
        let subkernel = unsafe { SUBKERNELS.get_mut(&id).unwrap() };
        match drtio::subkernel_upload(
            io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, id, 
            subkernel.destination, &subkernel.data) {
            Ok(_) => { subkernel.state = SubkernelState::Uploaded; Ok(()) },
            Err(e) => Err(e)
        }
    }

    pub fn load(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, routing_table: &RoutingTable,
            id: u32, run: bool) -> Result<(), &'static str> {
        let _lock = subkernel_mutex.lock(io).unwrap();
        let subkernel = unsafe { SUBKERNELS.get_mut(&id).unwrap() };
        if subkernel.state != SubkernelState::Uploaded && subkernel.state != SubkernelState::Loaded {
            return Err("Subkernel not in state ready for loading (not uploaded)")
        }
        drtio::subkernel_load(io, aux_mutex, ddma_mutex, subkernel_mutex,
            routing_table, id, subkernel.destination, run)?;
        subkernel.state = if run { SubkernelState::Running } else { SubkernelState::Loaded };
        Ok(())
    }

    pub fn clear_subkernels(io: &Io, subkernel_mutex: &Mutex) {
        let _lock = subkernel_mutex.lock(io).unwrap();
        unsafe {
            SUBKERNELS = BTreeMap::new();
            MESSAGE_QUEUE = Vec::new();
            CURRENT_MESSAGES = BTreeMap::new();
        }
    }

    pub fn subkernel_finished(io: &Io, subkernel_mutex: &Mutex, id: u32, with_exception: bool) {
        // called upon receiving DRTIO SubkernelRunDone
        let _lock = subkernel_mutex.lock(io).unwrap();
        let mut subkernel = unsafe { SUBKERNELS.get_mut(&id).unwrap() };
        subkernel.state = match with_exception {
            true => SubkernelState::FinishedAbnormally { comm_lost: false, with_exception: with_exception },
            false => SubkernelState::Finished
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
                        SubkernelState::Running => SubkernelState::FinishedAbnormally { comm_lost: true, with_exception: false },
                        _ => SubkernelState::NotLoaded,
                    }
                }
            }
        }
    }

    fn get_finished_abnormally<'a>(io: &Io, subkernel_mutex: &Mutex) -> Option<(u32, &'a mut Subkernel)> {
        // return kernels that have an exception which require handling
        let _lock = match subkernel_mutex.lock(io) {
            Ok(lock) => lock,
            // this may get interrupted and cause a panic - nothing to worry about though!
            Err(_) => return None
        };
        let subkernels_iter = unsafe { SUBKERNELS.iter_mut() };
        for (id, subkernel) in subkernels_iter {
            match subkernel.state {
                SubkernelState::FinishedAbnormally { .. } => {
                    return Some((*id, subkernel));
                }
                _ => ()
            }
        }
        None
    }

    pub fn get_finished_with_exception(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &RoutingTable) -> Result<Option<SubkernelFinished>, &'static str> {
        let finished = get_finished_abnormally(io, subkernel_mutex);
        // broken into get_finished function to prevent deadlocks if something comes during exception retrieval
        match finished {
            Some((id, mut subkernel)) => {
                if let SubkernelState::FinishedAbnormally { comm_lost, with_exception } = subkernel.state {
                    let exception = match with_exception {
                        true => Some(drtio::subkernel_retrieve_exception(io, aux_mutex, ddma_mutex, subkernel_mutex,
                            routing_table, subkernel.destination)?),
                        false => None
                    };
                    subkernel.state = SubkernelState::Finished;
                    Ok(Some(SubkernelFinished {
                        id: id,
                        comm_lost: comm_lost,
                        exception: exception
                    }))
                } else {
                    Err("Subkernel returned did not have finished state")
                }
            },
            None => Ok(None)
        }
    }

    pub fn await_finish(io: &Io, subkernel_mutex: &Mutex, id: Option<u32>, timeout: u64) -> Result<(), &'static str> {
        let max_time = clock::get_ms() + timeout as u64;
        io.until(|| {
            if clock::get_ms() > max_time {
                return true;
            }
            if subkernel_mutex.test_lock() {
                // cannot lock again within io.until - scheduler guarantees
                // that it will not be interrupted - so only test the lock
                return false;
            }
            if let Some(id) = id {
                // kernel can wait for all subkernels to finish (None)
                // or a particular one (Some(id))
                let subkernel = unsafe { SUBKERNELS.get(&id).unwrap() };
                match subkernel.state {
                    // a kernel that finished with an exception or comm lost
                    // still needs handling, so it doesn't count as truly finished
                    SubkernelState::Finished => true,
                    _ => false
                }
            } else {
                let subkernels_iter = unsafe { SUBKERNELS.iter_mut() };
                for (_, subkernel) in subkernels_iter {
                    match subkernel.state {
                        // count any non-running kernels as finished
                        SubkernelState::Running => return false,
                        _ => (),
                    }
                }
                true
            }
        }).unwrap();
        if clock::get_ms() > max_time {
            error!("Remote subkernel finish await timed out");
            return Err("Timed out waiting for subkernels.");
        }
        // finished state will be dealt with by session
        Ok(())
    }

    struct Message {
        from_id: u32,
        pub tag: u8,
        pub data: Vec<u8>
    }

    // FIFO queue of messages
    static mut MESSAGE_QUEUE: Vec<Message> = Vec::new();
    // currently under construction message(s) (can be from multiple sources)
    static mut CURRENT_MESSAGES: BTreeMap<u32, Message> = BTreeMap::new();

    pub fn message_handle_incoming(io: &Io, subkernel_mutex: &Mutex, 
        id: u32, last: bool, length: usize, data: &[u8; MASTER_PAYLOAD_MAX_SIZE]) {
        // called when receiving a message from satellite
        let _lock = subkernel_mutex.lock(io).unwrap();
        match unsafe { CURRENT_MESSAGES.get_mut(&id) } {
            Some(message) => message.data.extend(&data[..length]),
            None => unsafe { 
                CURRENT_MESSAGES.insert(id, Message {
                    from_id: id,
                    tag: data[0],
                    data: data[1..length].to_vec()
                });
            }
        };
        if last {
            unsafe { 
                // when done, remove from working queue
                MESSAGE_QUEUE.push(CURRENT_MESSAGES.remove(&id).unwrap());
            };
        }
    }

    pub fn message_await(io: &Io, subkernel_mutex: &Mutex, id: u32, timeout: u64) -> Result<(u8, Vec<u8>), &'static str> {
        let max_time = clock::get_ms() + timeout as u64;
        let message = io.until_ok(|| {
            if clock::get_ms() > max_time {
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
            Err(())
        }).unwrap();
        match message {
            Some(message) => Ok((message.tag, message.data)),
            None => Err("Timed out waiting for subkernel message.")
        }
    }

    pub fn message_clear_queue(io: &Io, subkernel_mutex: &Mutex) {
        let _lock = subkernel_mutex.lock(io).unwrap();
        unsafe {
            MESSAGE_QUEUE = Vec::new();
            CURRENT_MESSAGES = BTreeMap::new();
        }
    }

    pub fn message_send<'a>(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
        routing_table: &RoutingTable, id: u32, tag: &'a [u8], message: *const *const ()) -> Result<(), &'static str> {
        // todo: make a writer that will call back and send smaller slices
        let mut writer = Cursor::new(Vec::new());
        let destination = unsafe {
            let _lock = subkernel_mutex.lock(io).unwrap();
            SUBKERNELS.get(&id).unwrap().destination
        };
        
        // reuse rpc code for sending arbitrary data
        match rpc::send_args(&mut writer, 0, tag, message) {
            Ok(_) => drtio::subkernel_send_message(
                io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table,
                // skip service tag
                id, destination, &writer.into_inner()[4..]
            ),
            Err(_) => Err("Error writing message arguments")
        }
    }
}