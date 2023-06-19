use core::{mem, cell::Cell};
use alloc::{string::String, format, vec::Vec, collections::btree_map::BTreeMap};

use board_artiq::mailbox;

use proto_artiq::kernel_proto as kern;
use board_misoc::{csr, clock};

mod kernel_cpu {
    use core::ptr;
    use board_misoc::csr;
    use board_artiq::{mailbox, rpc_queue};

    use proto_artiq::kernel_proto::{KERNELCPU_EXEC_ADDRESS, KERNELCPU_LAST_ADDRESS, KSUPPORT_HEADER_SIZE};

    pub unsafe fn start() {
        if csr::kernel_cpu::reset_read() == 0 {
            panic!("attempted to start kernel CPU when it is already running")
        }

        stop();

        extern {
            static _binary____ksupport_ksupport_elf_start: u8;
            static _binary____ksupport_ksupport_elf_end: u8;
        }
        let ksupport_start = &_binary____ksupport_ksupport_elf_start as *const _;
        let ksupport_end   = &_binary____ksupport_ksupport_elf_end as *const _;
        ptr::copy_nonoverlapping(ksupport_start,
                                (KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE) as *mut u8,
                                ksupport_end as usize - ksupport_start as usize);

        csr::cri_con::selected_write(2);
        csr::kernel_cpu::reset_write(0);

        rpc_queue::init();
    }

    pub unsafe fn stop() {
        csr::kernel_cpu::reset_write(1);
        csr::cri_con::selected_write(0);

        mailbox::acknowledge();
        rpc_queue::init();
    }

    pub fn validate(ptr: usize) -> bool {
        ptr >= KERNELCPU_EXEC_ADDRESS && ptr <= KERNELCPU_LAST_ADDRESS
    }

}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum KernelState {
    Absent,
    Loaded,
    Running,
    RpcWait
}

// Per-connection state
#[derive(Debug)]
pub struct Session {
    // no congress - no DMA, no cache, may implement latter later
    kernel_state: KernelState,
    log_buffer: String,
    finished_cleanly: Cell<bool>
}

impl Session {
    pub fn new() -> Session {
        Session {
            kernel_state: KernelState::Absent,
            log_buffer: String::new(),
            finished_cleanly: Cell::new(true)
        }
    }

    fn running(&self) -> bool {
        match self.kernel_state {
            KernelState::Absent  | KernelState::Loaded  => false,
            KernelState::Running | KernelState::RpcWait => true
        }
    }

    fn flush_log_buffer(&mut self) {
        if &self.log_buffer[self.log_buffer.len() - 1..] == "\n" {
            for line in self.log_buffer.lines() {
                info!(target: "kernel", "{}", line);
            }
            self.log_buffer.clear()
        }
    }
}

#[derive(Debug)]
pub enum Error {
    Load(String),
    KernelNotFound,
    InvalidPointer(usize),
    ClockFailure,
    Unexpected(String),
    NoMessage,
}

#[derive(Debug)]
pub enum ManagerError {
    IdNotFound,
    KernelRunning,
    EntryNotComplete
}

macro_rules! unexpected {
     ($($arg:tt)*) => (return Err(Error::Unexpected(format!($($arg)*))));
}


#[derive(Debug)]
struct KernelData {
    data: Vec<u8>,
    complete: bool
}

#[derive(Debug)]
pub struct Manager {
    kernels: BTreeMap<u32, KernelData>,
    current_id: u32,
    current_session: Session
}

impl Manager {
    pub fn new() -> Manager {
        // in case Manager is created during a DMA in progress
        // wait for it to end
        unsafe {
            while csr::rtio_dma::enable_read() != 0 {} 
        }
        Manager {
            kernels: BTreeMap::new(),
            current_id: 0,
            current_session: Session::new()
        }
    }

    pub fn add(&mut self, id: u32, last: bool, data: &[u8], data_len: usize) -> Result<(), Error> {
        let kernel = match self.kernels.get_mut(&id) {
            Some(kernel) => {
                if kernel.complete {
                    // replace entry
                    self.kernels.remove(&id);
                    self.kernels.insert(id, KernelData {
                        data: Vec::new(),
                        complete: false });
                    self.kernels.get_mut(&id).unwrap()
                } else {
                    kernel
                }
            },
            None => {
                self.kernels.insert(id, KernelData {
                    data: Vec::new(),
                    complete: false });
                self.kernels.get_mut(&id).unwrap()
            },
        };
        kernel.data.extend(&data[0..data_len]);

        kernel.complete = last;
        Ok(())
    }

    pub fn erase(&mut self, id: u32) -> Result<(), ManagerError> {
        match self.kernels.remove(&id) {
            Some(_) => Ok(()),
            None => Err(ManagerError::IdNotFound)
        }
    }

    pub fn is_running(&self) -> bool {
        self.current_session.running()
    }

    pub fn stop_forcefully(&mut self) {
        self.current_session.kernel_state = KernelState::Loaded;
        unsafe { kernel_cpu::stop(); }
    }

    pub fn kern_run(&mut self, id: u32) -> Result<(), Error> {
        if self.current_session.kernel_state != KernelState::Loaded
            || self.current_id != id {
            self.kern_load(id)?;
        }
    
        self.current_session.kernel_state = KernelState::Running;
    
        kern_acknowledge()
    }

    pub fn kern_load(&mut self, id: u32) -> Result<(), Error> {
        if self.current_session.running() {
            unexpected!("attempted to load a new kernel while a kernel was running")
        }
        self.current_id = id;
        self.current_session = Session::new();
        
        unsafe { 
            kernel_cpu::start();

            kern_send(&kern::LoadRequest(&self.kernels.get(&id).unwrap().data)).unwrap();
            kern_recv(|reply| {
                match reply {
                    kern::LoadReply(Ok(())) => {
                        self.current_session.kernel_state = KernelState::Loaded;
                        Ok(())
                    }
                    kern::LoadReply(Err(error)) => {
                        kernel_cpu::stop();
                        Err(Error::Load(format!("{}", error)))
                    }
                    other => {
                        unexpected!("unexpected kernel CPU reply to load request: {:?}", other)
                    }
                }
            })
        }
    }

    pub fn process_kern_requests(&mut self) {
        if !self.is_running() {
            return;
        }
        // may need to return some value or data through DRTIO to master
        process_kern_message(&mut self.current_session).unwrap();
    }
}

impl Drop for Manager {
    fn drop(&mut self) {
        unsafe { kernel_cpu::stop() };
    }
}

fn kern_recv_notrace<R, F>(f: F) -> Result<R, Error>
        where F: FnOnce(&kern::Message) -> Result<R, Error> {
    if mailbox::receive() == 0 {
        return Err(Error::NoMessage);
    };
    if !kernel_cpu::validate(mailbox::receive()) {
        return Err(Error::InvalidPointer(mailbox::receive()))
    }
    f(unsafe { &*(mailbox::receive() as *const kern::Message) })
}

fn kern_recv_dotrace(reply: &kern::Message) {
    match reply {
        &kern::Log(_) => debug!("comm<-kern Log(...)"),
        &kern::LogSlice(_) => debug!("comm<-kern LogSlice(...)"),
        &kern::DmaRecordAppend(_) => debug!("comm<-kern DmaRecordAppend(...) - ignored"),
        _ => debug!("comm<-kern {:?}", reply),
    }
}

#[inline(always)]
fn kern_recv<R, F>(f: F) -> Result<R, Error>
        where F: FnOnce(&kern::Message) -> Result<R, Error> {
    kern_recv_notrace(|reply| {
        kern_recv_dotrace(reply);
        f(reply)
    })
}

fn kern_acknowledge() -> Result<(), Error> {
    mailbox::acknowledge();
    Ok(())
}

fn kern_send(request: &kern::Message) -> Result<(), Error> {
    match request {
        &kern::LoadRequest(_) => debug!("comm->kern LoadRequest(...)"),
        &kern::DmaRetrieveReply { .. } => {
            debug!("this should not have been sent");
        }
        _ => debug!("comm->kern {:?}", request)
    }
    unsafe { mailbox::send(request as *const _ as usize) }
    while !mailbox::acknowledged() {}
    Ok(())
}

fn process_kern_message(session: &mut Session) -> Result<bool, Error> {
    kern_recv_notrace(|request| {
        match (request, session.kernel_state) {
            (&kern::LoadReply(_), KernelState::Loaded) => {
                // We're standing by; ignore the message.
                return Ok(false)
            }
            (_, KernelState::Running) => (),
            _ => {
                unexpected!("unexpected request {:?} from kernel CPU in {:?} state",
                            request, session.kernel_state)
            },
        }

        kern_recv_dotrace(request);

        if process_kern_hwreq(request)? {
            return Ok(false)
        }

        match request {
            &kern::Log(args) => {
                use core::fmt::Write;
                session.log_buffer
                       .write_fmt(args)
                       .unwrap_or_else(|_| warn!("cannot append to session log buffer"));
                session.flush_log_buffer();
                kern_acknowledge()
            }

            &kern::LogSlice(arg) => {
                session.log_buffer += arg;
                session.flush_log_buffer();
                kern_acknowledge()
            }

            &kern::DmaRecordStart(_name) => {
                unexpected!("unsupported in subkernels request {:?} (use DDMA instead)", request)
            }
            &kern::DmaRecordAppend(_data) => {
                unexpected!("unsupported in subkernels request {:?} (use DDMA instead)", request)
            }
            &kern::DmaRecordStop { duration: _dur, enable_ddma: _ } => {
                unexpected!("unsupported in subkernels request {:?} (use DDMA instead)", request)
            }
            &kern::DmaEraseRequest { name: _name } => {
                unexpected!("unsupported in subkernels request {:?} (use DDMA instead)", request)
            }
            &kern::DmaRetrieveRequest { name: _name } => {
                unexpected!("unsupported in subkernels request {:?} (use DDMA instead)", request)
            }
            &kern::DmaStartRemoteRequest { id: _id, timestamp: _timestamp } => {
                unexpected!("unsupported in subkernels request {:?} (use DDMA instead)", request)
            }
            &kern::DmaAwaitRemoteRequest { id: _id } => {
                unexpected!("unsupported in subkernels request {:?} (use DDMA instead)", request)
            }

            &kern::RpcSend { async: _async, service: _service, tag: _tag, data: _data } => {
                kern_acknowledge()
            },
            &kern::RpcFlush => {
                // See ksupport/lib.rs for the reason this request exists.
                // We do not need to do anything here because of how the main loop is
                // structured.
                kern_acknowledge()
            },

            &kern::CacheGetRequest { key: _key } => {
                kern_send(&kern::CacheGetReply {
                    value: unsafe { mem::transmute([0]) }
                })
            }

            &kern::CachePutRequest { key: _key, value: _value } => {
                kern_send(&kern::CachePutReply { succeeded: false })
            }

            &kern::RunFinished => {
                unsafe { kernel_cpu::stop() }
                session.kernel_state = KernelState::Absent;

                info!("kernel finished");
                Ok(())
            }
            &kern::RunException {
                exceptions,
                stack_pointers,
                backtrace
            } => {
                unsafe { kernel_cpu::stop() }
                session.kernel_state = KernelState::Absent;

                error!("exception in flash kernel");
                for exception in exceptions {
                    error!("{:?}", exception.unwrap());
                }
                return Ok(true)
            }

            request => unexpected!("unexpected request {:?} from kernel CPU", request)
        }.and(Ok(false))
    })
}

pub fn process_kern_hwreq(request: &kern::Message) -> Result<bool, Error> {
    match request {
        &kern::RtioInitRequest => {
            info!("resetting RTIO");
            unsafe {
                csr::drtiosat::reset_write(1);
                clock::spin_us(100);
                csr::drtiosat::reset_write(0);
            }
            kern_acknowledge()
        }

        &kern::RtioDestinationStatusRequest { destination: _destination } => {
            kern_send(&kern::RtioDestinationStatusReply { up: true })
        }

        &kern::I2cStartRequest { busno } => {
            kern_send(&kern::I2cBasicReply { succeeded: false })
        }
        &kern::I2cRestartRequest { busno } => {
            kern_send(&kern::I2cBasicReply { succeeded: false})
        }
        &kern::I2cStopRequest { busno } => {
            kern_send(&kern::I2cBasicReply { succeeded: false })
        }
        &kern::I2cWriteRequest { busno, data } => {
            kern_send(&kern::I2cWriteReply { succeeded: false, ack: false })
        }
        &kern::I2cReadRequest { busno, ack } => {
            kern_send(&kern::I2cReadReply { succeeded: false, data: 0xff })
        }
        &kern::I2cSwitchSelectRequest { busno, address, mask } => {
            kern_send(&kern::I2cBasicReply { succeeded: false })
        }

        &kern::SpiSetConfigRequest { busno, flags, length, div, cs } => {
            kern_send(&kern::SpiBasicReply { succeeded: false })
        },
        &kern::SpiWriteRequest { busno, data } => {
            kern_send(&kern::SpiBasicReply { succeeded: false })
        }
        &kern::SpiReadRequest { busno } => {
            kern_send(&kern::SpiReadReply { succeeded: false, data: 0 })
        }

        _ => return Ok(false)
    }.and(Ok(true))
}