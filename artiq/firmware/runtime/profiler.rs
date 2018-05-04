#![cfg_attr(not(has_timer1), allow(dead_code))]

use core::mem;
use core::fmt;
use core::nonzero::NonZero;
use alloc::Vec;
use managed::ManagedMap;

#[derive(Debug, Copy, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Address(NonZero<usize>);

impl Address {
    pub fn new(raw: usize) -> Option<Address> {
        NonZero::new(raw).map(Address)
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

    pub fn hits<'a>(&'a mut self) -> ManagedMap<'a, Address, u32> {
        ManagedMap::Borrowed(&mut self.hits[..])
    }

    pub fn edges<'a>(&'a mut self) -> ManagedMap<'a, (Address, Address), u32> {
        ManagedMap::Borrowed(&mut self.edges[..])
    }

    pub fn record_hit(&mut self, addr: Address) -> Result<(), ()> {
        let mut hits = self.hits();
        match hits.get_mut(&addr) {
            Some(count) => *count = count.saturating_add(1),
            None => {
                if let Err(_) = hits.insert(addr, 1) {
                    return Err(())
                }
            }
        }
        Ok(())
    }

    #[allow(dead_code)]
    pub fn record_edge(&mut self, caller: Address, callee: Address) -> Result<(), ()> {
        let mut edges = self.edges();
        match edges.get_mut(&(caller, callee)) {
            Some(count) => *count = count.saturating_add(1),
            None => {
                if let Err(_) = edges.insert((caller, callee), 1) {
                    return Err(())
                }
            }
        }
        Ok(())
    }
}

#[cfg(has_timer1)]
mod imp {
    use board::{csr, irq};
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

    #[inline(always)] // make the top of backtrace predictable
    fn record(profile: &mut Profile, pc: usize) -> Result<(), ()> {
        let callee = Address::new(pc).expect("null code address");
        profile.record_hit(callee)?;

        // TODO: record edges

        Ok(())
    }

    #[inline(never)] // see above
    pub fn sample(pc: usize) {
        unsafe {
            csr::timer1::ev_pending_write(1);
        }

        let result = {
            let mut profile = Lock::take().expect("cannot lock");
            record(profile.as_mut().expect("profiler not running"), pc)
        };

        if result.is_err() {
            warn!("out of space");
            stop();
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
