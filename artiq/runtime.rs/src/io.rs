extern crate fringe;
extern crate lwip;

use std::vec::Vec;
use std::time::{Instant, Duration};
use self::fringe::OwnedStack;
use self::fringe::generator::{Generator, Yielder};

#[derive(Debug)]
struct WaitRequest {
    timeout: Option<Instant>,
    event:   Option<WaitEvent>
}

#[derive(Debug)]
enum WaitResult {
    Completed,
    TimedOut,
    Interrupted
}

#[derive(Debug)]
struct Thread {
    generator:   Generator<WaitResult, WaitRequest, OwnedStack>,
    waiting_for: WaitRequest,
    interrupted: bool
}

#[derive(Debug)]
pub struct Scheduler {
    threads: Vec<Thread>,
    index:   usize
}

impl Scheduler {
    pub fn new() -> Scheduler {
        Scheduler { threads: Vec::new(), index: 0 }
    }

    pub unsafe fn spawn<F: FnOnce(Waiter) + Send>(&mut self, stack_size: usize, f: F) {
        let stack = OwnedStack::new(stack_size);
        let thread = Thread {
            generator:   Generator::unsafe_new(stack, move |yielder, _| {
                f(Waiter(yielder))
            }),
            waiting_for: WaitRequest {
                timeout: None,
                event:   None
            },
            interrupted: false
        };
        self.threads.push(thread)
    }

    pub fn run(&mut self) {
        if self.threads.len() == 0 { return }

        let now = Instant::now();

        let start_index = self.index;
        loop {
            self.index = (self.index + 1) % self.threads.len();

            let result = {
                let thread = &mut self.threads[self.index];
                match thread.waiting_for {
                    _ if thread.interrupted => {
                        thread.interrupted = false;
                        thread.generator.resume(WaitResult::Interrupted)
                    }
                    WaitRequest { timeout: Some(instant), .. } if now >= instant =>
                        thread.generator.resume(WaitResult::TimedOut),
                    WaitRequest { event: Some(ref event), .. } if event.completed() =>
                        thread.generator.resume(WaitResult::Completed),
                    WaitRequest { timeout: None, event: None } =>
                        thread.generator.resume(WaitResult::Completed),
                    _ => {
                        if self.index == start_index {
                            // We've checked every thread and none of them are runnable.
                            break
                        } else {
                            continue
                        }
                    }
                }
            };

            match result {
                None => {
                    // The thread has terminated.
                    self.threads.remove(self.index);
                    self.index = 0
                },
                Some(wait_request) => {
                    // The thread has suspended itself.
                    self.threads[self.index].waiting_for = wait_request
                }
            }

            break
        }
    }
}

#[derive(Debug)]
enum WaitEvent {
    UdpReadable(*const lwip::UdpSocketState),
    TcpAcceptable(*const lwip::TcpListenerState),
    TcpWriteable(*const lwip::TcpStreamState),
    TcpReadable(*const lwip::TcpStreamState),
}

impl WaitEvent {
    fn completed(&self) -> bool {
        match *self {
            WaitEvent::UdpReadable(state) =>
                unsafe { (*state).readable() },
            WaitEvent::TcpAcceptable(state) =>
                unsafe { (*state).acceptable() },
            WaitEvent::TcpWriteable(state) =>
                unsafe { (*state).writeable() },
            WaitEvent::TcpReadable(state) =>
                unsafe { (*state).readable() },
        }
    }
}

unsafe impl Send for WaitEvent {}

#[derive(Debug, Clone, Copy, Eq, PartialEq)]
pub enum Error {
    Lwip(lwip::Error),
    TimedOut,
    Interrupted
}

pub type Result<T> = ::std::result::Result<T, Error>;

#[derive(Debug)]
pub struct Waiter<'a>(&'a mut Yielder<WaitResult, WaitRequest, OwnedStack>);

impl<'a> Waiter<'a> {
    pub fn sleep(&mut self, duration: Duration) -> Result<()> {
        let request = WaitRequest {
            timeout: Some(Instant::now() + duration),
            event:   None
        };

        match self.0.suspend(request) {
            WaitResult::TimedOut => Ok(()),
            WaitResult::Interrupted => Err(Error::Interrupted),
            _ => unreachable!()
        }
    }

    fn suspend(&mut self, request: WaitRequest) -> Result<()> {
        match self.0.suspend(request) {
            WaitResult::Completed => Ok(()),
            WaitResult::TimedOut => Err(Error::TimedOut),
            WaitResult::Interrupted => Err(Error::Interrupted)
        }
    }

    pub fn udp_readable(&mut self, socket: &lwip::UdpSocket) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::UdpReadable(socket.state()))
        })
    }

    pub fn tcp_acceptable(&mut self, socket: &lwip::TcpListener) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::TcpAcceptable(socket.state()))
        })
    }

    pub fn tcp_writeable(&mut self, socket: &lwip::TcpStream) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::TcpWriteable(socket.state()))
        })
    }

    pub fn tcp_readable(&mut self, socket: &lwip::TcpStream) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::TcpReadable(socket.state()))
        })
    }
}
