extern crate fringe;

use std::prelude::v1::*;
use std::time::{Instant, Duration};
use self::fringe::OwnedStack;
use self::fringe::generator::{Generator, Yielder};

#[derive(Debug)]
pub struct WaitRequest {
    timeout: Option<Instant>,
    event:   Option<WaitEvent>
}

#[derive(Debug)]
pub enum WaitResult {
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

    pub unsafe fn spawn<F: FnOnce(Io) + Send>(&mut self, stack_size: usize, f: F) {
        let stack = OwnedStack::new(stack_size);
        let thread = Thread {
            generator:   Generator::unsafe_new(stack, move |yielder, _| {
                f(Io(yielder))
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
pub enum WaitEvent {}

impl WaitEvent {
    fn completed(&self) -> bool {
        match *self {}
    }
}

pub type IoResult<T> = Result<T, ()>;

#[derive(Debug)]
pub struct Io<'a>(&'a mut Yielder<WaitResult, WaitRequest, OwnedStack>);

impl<'a> Io<'a> {
    pub fn sleep(&mut self, duration: Duration) -> IoResult<()> {
        let request = WaitRequest {
            timeout: Some(Instant::now() + duration),
            event:   None
        };

        match self.0.suspend(request) {
            WaitResult::TimedOut => Ok(()),
            WaitResult::Interrupted => Err(()),
            _ => unreachable!()
        }
    }
}
