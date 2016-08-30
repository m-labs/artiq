use core::ops::{Add, Sub, Mul, Div};

const MILLIS_PER_SEC: u64 = 1_000;
const NANOS_PER_MILLI: u32 = 1_000_000;

/// A duration type to represent a span of time, typically used for system
/// timeouts.
///
/// Each duration is composed of a number of seconds and nanosecond precision.
/// APIs binding a system timeout will typically round up the nanosecond
/// precision if the underlying system does not support that level of precision.
///
/// Durations implement many common traits, including `Add`, `Sub`, and other
/// ops traits. Currently a duration may only be inspected for its number of
/// seconds and its nanosecond precision.
///
/// # Examples
///
/// ```
/// use std::time::Duration;
///
/// let five_seconds = Duration::new(5, 0);
/// let five_seconds_and_five_nanos = five_seconds + Duration::new(0, 5);
///
/// assert_eq!(five_seconds_and_five_nanos.as_secs(), 5);
/// assert_eq!(five_seconds_and_five_nanos.subsec_nanos(), 5);
///
/// let ten_millis = Duration::from_millis(10);
/// ```
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub struct Duration {
    millis: u64
}

impl Duration {
    /// Creates a new `Duration` from the specified number of seconds and
    /// additional nanosecond precision.
    ///
    /// If the nanoseconds is greater than 1 billion (the number of nanoseconds
    /// in a second), then it will carry over into the seconds provided.
    pub fn new(secs: u64, nanos: u32) -> Duration {
        Duration { millis: secs * MILLIS_PER_SEC + (nanos / NANOS_PER_MILLI) as u64 }
    }

    /// Creates a new `Duration` from the specified number of seconds.
    pub fn from_secs(secs: u64) -> Duration {
        Duration { millis: secs * MILLIS_PER_SEC }
    }

    /// Creates a new `Duration` from the specified number of milliseconds.
    pub fn from_millis(millis: u64) -> Duration {
        Duration { millis: millis }
    }

    /// Returns the number of whole milliseconds represented by this duration.
    pub fn as_millis(&self) -> u64 { self.millis }

    /// Returns the number of whole seconds represented by this duration.
    ///
    /// The extra precision represented by this duration is ignored (e.g. extra
    /// nanoseconds are not represented in the returned value).
    pub fn as_secs(&self) -> u64 {
        self.millis / MILLIS_PER_SEC
    }

    /// Returns the nanosecond precision represented by this duration.
    ///
    /// This method does **not** return the length of the duration when
    /// represented by nanoseconds. The returned number always represents a
    /// fractional portion of a second (e.g. it is less than one billion).
    pub fn subsec_nanos(&self) -> u32 {
        (self.millis % MILLIS_PER_SEC) as u32 * NANOS_PER_MILLI
    }
}

impl Add for Duration {
    type Output = Duration;

    fn add(self, rhs: Duration) -> Duration {
        Duration {
            millis: self.millis.checked_add(rhs.millis)
                               .expect("overflow when adding durations")
        }
    }
}

impl Sub for Duration {
    type Output = Duration;

    fn sub(self, rhs: Duration) -> Duration {
        Duration {
            millis: self.millis.checked_sub(rhs.millis)
                               .expect("overflow when subtracting durations")
        }
    }
}

impl Mul<u32> for Duration {
    type Output = Duration;

    fn mul(self, rhs: u32) -> Duration {
        Duration {
            millis: self.millis.checked_mul(rhs as u64)
                               .expect("overflow when multiplying duration")
        }
    }
}

impl Div<u32> for Duration {
    type Output = Duration;

    fn div(self, rhs: u32) -> Duration {
        Duration {
            millis: self.millis / (rhs as u64)
        }
    }
}
