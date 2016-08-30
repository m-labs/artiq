use core::ops::{Add, Sub};
use time::duration::Duration;

/// A measurement of a monotonically increasing clock.
///
/// Instants are always guaranteed to be greater than any previously measured
/// instant when created, and are often useful for tasks such as measuring
/// benchmarks or timing how long an operation takes.
///
/// Note, however, that instants are not guaranteed to be **steady**.  In other
/// words, each tick of the underlying clock may not be the same length (e.g.
/// some seconds may be longer than others). An instant may jump forwards or
/// experience time dilation (slow down or speed up), but it will never go
/// backwards.
///
/// Instants are opaque types that can only be compared to one another. There is
/// no method to get "the number of seconds" from an instant. Instead, it only
/// allows measuring the duration between two instants (or comparing two
/// instants).
#[derive(Debug, Copy, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Instant {
    millis: u64
}

impl Instant {
    /// Returns an instant corresponding to "now".
    pub fn now() -> Instant {
        extern {
            fn clock_get_ms() -> i64;
        }

        Instant { millis: unsafe { clock_get_ms() as u64 } }
    }

    /// Returns the amount of time elapsed from another instant to this one.
    ///
    /// # Panics
    ///
    /// This function will panic if `earlier` is later than `self`, which should
    /// only be possible if `earlier` was created after `self`. Because
    /// `Instant` is monotonic, the only time that this should happen should be
    /// a bug.
    pub fn duration_from_earlier(&self, earlier: Instant) -> Duration {
        let millis = self.millis.checked_sub(earlier.millis)
                                .expect("`earlier` is later than `self`");
        Duration::from_millis(millis)
    }

    /// Returns the amount of time elapsed since this instant was created.
    ///
    /// # Panics
    ///
    /// This function may panic if the current time is earlier than this
    /// instant, which is something that can happen if an `Instant` is
    /// produced synthetically.
    pub fn elapsed(&self) -> Duration {
        Instant::now().duration_from_earlier(*self)
    }
}

impl Add<Duration> for Instant {
    type Output = Instant;

    fn add(self, other: Duration) -> Instant {
        Instant {
            millis: self.millis.checked_add(other.as_millis())
                               .expect("overflow when adding duration to instant")
        }
    }
}

impl Sub<Duration> for Instant {
    type Output = Instant;

    fn sub(self, other: Duration) -> Instant {
        Instant {
            millis: self.millis.checked_sub(other.as_millis())
                               .expect("overflow when subtracting duration from instant")
        }
    }
}
