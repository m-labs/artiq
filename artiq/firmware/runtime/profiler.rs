#![cfg_attr(not(has_timer1), allow(dead_code))]

use core::mem;
use core::fmt;
use core::num::NonZeroUsize;
use alloc::Vec;
use managed::ManagedMap;

#[derive(Debug, Copy, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Address(NonZeroUsize);

impl Address {
    pub fn new(raw: usize) -> Address {
        Address(NonZeroUsize::new(raw).expect("null address"))
    }

    pub fn as_raw(&self) -> usize {
        self.0.get()
    }
}

pub struct Profile {
    hits:  Vec<Option<(Address, u32)>>,
    edges: Vec<Option<((Address, Address), u32)>>,
}

impl fmt::Debug for Profile {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "Profile {{ hits: vec![...; {}], edges: vec![...; {}] }}",
               self.hits.len(), self.edges.len())
    }
}

impl Profile {
    pub fn new(hits_size: usize, edges_size: usize) -> Profile {
        let mut hits  = vec![None; hits_size];
        hits.shrink_to_fit();
        let mut edges = vec![None; edges_size];
        edges.shrink_to_fit();
        Profile {
            hits:  hits.into(),
            edges: edges.into(),
        }
    }

    pub fn overhead(&self) -> usize {
        let hit_size  = mem::size_of::<Option<(Address, u32)>>();
        let edge_size = mem::size_of::<Option<(Address, u32)>>();
        self.hits.capacity() * hit_size +
            self.edges.capacity() * edge_size
    }

    pub fn has_edges(&self) -> bool {
        self.edges.is_empty()
    }

    pub fn hits<'a>(&'a mut self) -> ManagedMap<'a, Address, u32> {
        ManagedMap::Borrowed(&mut self.hits[..])
    }

    pub fn edges<'a>(&'a mut self) -> ManagedMap<'a, (Address, Address), u32> {
        ManagedMap::Borrowed(&mut self.edges[..])
    }

    pub fn record_hit(&mut self, addr: Address) -> Result<(), ()> {
        let mut hits = self.hits();
        if let Some(count) = hits.get_mut(&addr) {
            return Ok(*count = count.saturating_add(1))
        }
        if let Err(_) = hits.insert(addr, 1) {
            return Err(())
        }
        return Ok(())
    }

    #[allow(dead_code)]
    pub fn record_edge(&mut self, caller: Address, callee: Address) -> Result<(), ()> {
        let mut edges = self.edges();
        if let Some(count) = edges.get_mut(&(caller, callee)) {
            return Ok(*count = count.saturating_add(1))
        }
        if let Err(_) = edges.insert((caller, callee), 1) {
            return Err(())
        }
        Ok(())
    }
}

#[cfg(has_timer1)]
mod imp {
    use unwind_backtrace::backtrace;
    use board_misoc::{csr, irq};
    use super::{Address, Profile};

    static mut PROFILE: Option<Profile> = None;

    mod lock {
        use core::ops::{Deref, DerefMut};
        use core::sync::atomic::{AtomicUsize, Ordering, ATOMIC_USIZE_INIT};

        static LOCKED: AtomicUsize = ATOMIC_USIZE_INIT;

        pub struct Lock;

        impl Lock {
            pub fn take() -> Result<Lock, ()> {
                if LOCKED.swap(1, Ordering::SeqCst) != 0 {
                    Err(())
                } else {
                    Ok(Lock)
                }
            }
        }

        impl Deref for Lock {
            type Target = Option<super::Profile>;

            fn deref(&self) -> &Option<super::Profile> {
                unsafe { &super::PROFILE }
            }
        }

        impl DerefMut for Lock {
            fn deref_mut(&mut self) -> &mut Option<super::Profile> {
                unsafe { &mut super::PROFILE }
            }
        }

        impl Drop for Lock {
            fn drop(&mut self) {
                LOCKED.store(0, Ordering::SeqCst)
            }
        }
    }

    use self::lock::Lock;

    pub fn start(interval_us: u64, hits_size: usize, edges_size: usize) -> Result<(), ()> {
        stop();

        let profile = Profile::new(hits_size, edges_size);
        info!("starting at {}us interval using {} heap bytes",
              interval_us, profile.overhead());

        *Lock::take().expect("cannot lock") = Some(profile);

        unsafe {
            let reload = csr::CONFIG_CLOCK_FREQUENCY as u64 * interval_us / 1_000_000;
            csr::timer1::load_write(reload);
            csr::timer1::reload_write(reload);
            csr::timer1::ev_pending_write(1);
            csr::timer1::ev_enable_write(1);
            irq::enable(csr::TIMER1_INTERRUPT);
            csr::timer1::en_write(1);
        }

        Ok(())
    }

    pub fn stop() {
        unsafe {
            if csr::timer1::en_read() == 0 || csr::timer1::ev_enable_read() == 0 {
                return
            }

            irq::disable(csr::TIMER1_INTERRUPT);
            csr::timer1::en_write(0);

            *Lock::take().expect("cannot lock") = None;

            info!("stopped");
        }
    }

    pub fn pause<F: FnOnce(Option<&mut Profile>) -> R, R>(f: F) -> R {
        unsafe {
            if csr::timer1::en_read() == 0 {
                return f(None)
            }

            irq::disable(csr::TIMER1_INTERRUPT);
            csr::timer1::en_write(0);

            let result = {
                let mut profile = Lock::take().expect("cannot lock");
                f(profile.as_mut())
            };

            irq::enable(csr::TIMER1_INTERRUPT);
            csr::timer1::en_write(1);

            result
        }
    }

    // Skip frames: ::profiler::sample, ::exception, exception vector.
    const SKIP_FRAMES: i32 = 3;

    #[inline(always)] // make the top of backtrace predictable
    fn record(profile: &mut Profile, exn_pc: usize) -> Result<(), ()> {
        let mut result = Ok(());
        let mut frame = -SKIP_FRAMES;

        // If we have storage for edges, use the DWARF unwinder.
        // Otherwise, don't bother and use a much faster path that just looks at EPCR.
        // Also, acquiring a meaningful backtrace requires libunwind
        // with the https://reviews.llvm.org/D46971 patch applied.
        if profile.has_edges() {
            let mut prev_pc = 0;
            let _ = backtrace(|pc| {
                // Backtrace gives us the return address, i.e. the address after the delay slot,
                // but we're interested in the call instruction, *except* when going through
                // the frame directly below the exception frame, which has the address that's
                // being executed.
                let pc = if pc != exn_pc { pc - 2 * 4 } else { pc };

                if frame == 0 {
                    result = result.and_then(|()|
                        profile.record_hit(Address::new(pc)));
                    prev_pc = pc;
                } else if frame > 0 {
                    result = result.and_then(|()|
                        profile.record_edge(Address::new(pc),
                                            Address::new(prev_pc)));
                }

                prev_pc = pc;
                frame += 1;
            });
        }

        // If we couldn't get anything useful out of a backtrace, at least
        // record a hit at the exception PC.
        if frame <= 0 {
            result = profile.record_hit(Address::new(exn_pc));
        }

        result
    }

    #[inline(never)] // see above
    pub fn sample(pc: usize) {
        let result = {
            let mut profile = Lock::take().expect("cannot lock");
            record(profile.as_mut().expect("profiler not running"), pc)
        };

        if result.is_err() {
            warn!("out of space");
            stop();
        } else {
            unsafe {
                csr::timer1::ev_pending_write(1);
            }
        }
    }
}

#[cfg(not(has_timer1))]
mod imp {
    #![allow(dead_code)]

    pub fn start(_interval_us: u64, _hits_size: usize, _edges_size: usize) -> Result<(), ()> {
        error!("timer not available");

        Err(())
    }

    pub fn stop() {}

    pub fn pause<F: FnOnce(Option<&mut super::Profile>) -> R, R>(f: F) -> R {
        f(None)
    }

    pub fn sample(_pc: usize) {}
}

pub use self::imp::*;
