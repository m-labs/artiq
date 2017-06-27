// Copyright 2015 The Rust Project Developers. See the COPYRIGHT
// file at the top-level directory of this distribution and at
// http://rust-lang.org/COPYRIGHT.
//
// Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
// http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
// <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
// option. This file may not be copied, modified, or distributed
// except according to those terms.

#[cfg(feature="io_error_alloc")] use alloc::boxed::Box;
#[cfg(not(feature="io_error_alloc"))] use ::FakeBox as Box;
use core::convert::Into;
use core::fmt;
use core::marker::{Send, Sync};
use core::option::Option::{self, Some, None};
use core::result;
use error;

/// A specialized [`Result`](../result/enum.Result.html) type for I/O
/// operations.
///
/// This type is broadly used across `std::io` for any operation which may
/// produce an error.
///
/// This typedef is generally used to avoid writing out `io::Error` directly and
/// is otherwise a direct mapping to `Result`.
///
/// While usual Rust style is to import types directly, aliases of `Result`
/// often are not, to make it easier to distinguish between them. `Result` is
/// generally assumed to be `std::result::Result`, and so users of this alias
/// will generally use `io::Result` instead of shadowing the prelude's import
/// of `std::result::Result`.
///
/// # Examples
///
/// A convenience function that bubbles an `io::Result` to its caller:
///
/// ```
/// use std::io;
///
/// fn get_string() -> io::Result<String> {
///     let mut buffer = String::new();
///
///     try!(io::stdin().read_line(&mut buffer));
///
///     Ok(buffer)
/// }
/// ```
pub type Result<T> = result::Result<T, Error>;

/// The error type for I/O operations of the `Read`, `Write`, `Seek`, and
/// associated traits.
///
/// Errors mostly originate from the underlying OS, but custom instances of
/// `Error` can be created with crafted error messages and a particular value of
/// `ErrorKind`.
#[derive(Debug)]
pub struct Error {
    repr: Repr,
}

enum Repr {
    Os(i32),

    #[cfg(feature="io_error_alloc")]
    Custom(Box<Custom>),
    #[cfg(not(feature="io_error_alloc"))]
    Custom(Custom),
}

#[derive(Debug)]
struct Custom {
    kind: ErrorKind,
    #[cfg(feature="io_error_alloc")]
    error: Box<error::Error+Send+Sync>,
    #[cfg(not(feature="io_error_alloc"))]
    error: &'static str
}

/// A list specifying general categories of I/O error.
///
/// This list is intended to grow over time and it is not recommended to
/// exhaustively match against it.
#[derive(Copy, PartialEq, Eq, Clone, Debug)]
#[allow(deprecated)]
pub enum ErrorKind {
    /// An entity was not found, often a file.
    NotFound,
    /// The operation lacked the necessary privileges to complete.
    PermissionDenied,
    /// The connection was refused by the remote server.
    ConnectionRefused,
    /// The connection was reset by the remote server.
    ConnectionReset,
    /// The connection was aborted (terminated) by the remote server.
    ConnectionAborted,
    /// The network operation failed because it was not connected yet.
    NotConnected,
    /// A socket address could not be bound because the address is already in
    /// use elsewhere.
    AddrInUse,
    /// A nonexistent interface was requested or the requested address was not
    /// local.
    AddrNotAvailable,
    /// The operation failed because a pipe was closed.
    BrokenPipe,
    /// An entity already exists, often a file.
    AlreadyExists,
    /// The operation needs to block to complete, but the blocking operation was
    /// requested to not occur.
    WouldBlock,
    /// A parameter was incorrect.
    InvalidInput,
    /// Data not valid for the operation were encountered.
    ///
    /// Unlike `InvalidInput`, this typically means that the operation
    /// parameters were valid, however the error was caused by malformed
    /// input data.
    ///
    /// For example, a function that reads a file into a string will error with
    /// `InvalidData` if the file's contents are not valid UTF-8.
    InvalidData,
    /// The I/O operation's timeout expired, causing it to be canceled.
    TimedOut,
    /// An error returned when an operation could not be completed because a
    /// call to `write` returned `Ok(0)`.
    ///
    /// This typically means that an operation could only succeed if it wrote a
    /// particular number of bytes but only a smaller number of bytes could be
    /// written.
    WriteZero,
    /// This operation was interrupted.
    ///
    /// Interrupted operations can typically be retried.
    Interrupted,
    /// Any I/O error not part of this list.
    Other,

    /// An error returned when an operation could not be completed because an
    /// "end of file" was reached prematurely.
    ///
    /// This typically means that an operation could only succeed if it read a
    /// particular number of bytes but only a smaller number of bytes could be
    /// read.
    UnexpectedEof,

    /// Any I/O error not part of this list.
    #[doc(hidden)]
    __Nonexhaustive,
}

impl Error {
    /// Creates a new I/O error from a known kind of error as well as an
    /// arbitrary error payload.
    ///
    /// This function is used to generically create I/O errors which do not
    /// originate from the OS itself. The `error` argument is an arbitrary
    /// payload which will be contained in this `Error`.
    ///
    /// # Examples
    ///
    /// ```
    /// use std::io::{Error, ErrorKind};
    ///
    /// // errors can be created from strings
    /// let custom_error = Error::new(ErrorKind::Other, "oh no!");
    ///
    /// // errors can also be created from other errors
    /// let custom_error2 = Error::new(ErrorKind::Interrupted, custom_error);
    /// ```
    #[cfg(feature="io_error_alloc")]
    pub fn new<E>(kind: ErrorKind, error: E) -> Error
        where E: Into<Box<error::Error+Send+Sync>>
    {
        Self::_new(kind, error.into())
    }

    #[cfg(not(feature="io_error_alloc"))]
    pub fn new<E>(kind: ErrorKind, error: E) -> Error
        where E: Into<&'static str>
    {
        Self::_new(kind, error.into())
    }

    #[cfg(feature="io_error_alloc")]
    fn _new(kind: ErrorKind, error: Box<error::Error+Send+Sync>) -> Error {
        Error {
            repr: Repr::Custom(Box::new(Custom {
                kind: kind,
                error: error,
            }))
        }
    }

    #[cfg(not(feature="io_error_alloc"))]
    fn _new(kind: ErrorKind, error: &'static str) -> Error {
        Error {
            repr: Repr::Custom(Box::new(Custom {
                kind: kind,
                error: error,
            }))
        }
    }

    /// Creates a new instance of an `Error` from a particular OS error code.
    pub fn from_raw_os_error(code: i32) -> Error {
        Error { repr: Repr::Os(code) }
    }

    /// Returns the OS error that this error represents (if any).
    ///
    /// If this `Error` was constructed via `last_os_error` or
    /// `from_raw_os_error`, then this function will return `Some`, otherwise
    /// it will return `None`.
    pub fn raw_os_error(&self) -> Option<i32> {
        match self.repr {
            Repr::Os(i) => Some(i),
            Repr::Custom(..) => None,
        }
    }

    /// Returns a reference to the inner error wrapped by this error (if any).
    ///
    /// If this `Error` was constructed via `new` then this function will
    /// return `Some`, otherwise it will return `None`.
    #[cfg(feature="io_error_alloc")]
    pub fn get_ref(&self) -> Option<&(error::Error+Send+Sync+'static)> {
        match self.repr {
            Repr::Os(..) => None,
            Repr::Custom(ref c) => Some(&*c.error),
        }
    }

    /// Returns a mutable reference to the inner error wrapped by this error
    /// (if any).
    ///
    /// If this `Error` was constructed via `new` then this function will
    /// return `Some`, otherwise it will return `None`.
    #[cfg(feature="io_error_alloc")]
    pub fn get_mut(&mut self) -> Option<&mut (error::Error+Send+Sync+'static)> {
        match self.repr {
            Repr::Os(..) => None,
            Repr::Custom(ref mut c) => Some(&mut *c.error),
        }
    }

    /// Consumes the `Error`, returning its inner error (if any).
    ///
    /// If this `Error` was constructed via `new` then this function will
    /// return `Some`, otherwise it will return `None`.
    #[cfg(feature="io_error_alloc")]
    pub fn into_inner(self) -> Option<Box<error::Error+Send+Sync>> {
        match self.repr {
            Repr::Os(..) => None,
            Repr::Custom(c) => Some(c.error)
        }
    }

    /// Returns the corresponding `ErrorKind` for this error.
    pub fn kind(&self) -> ErrorKind {
        match self.repr {
            Repr::Os(_code) => ErrorKind::Other,
            Repr::Custom(ref c) => c.kind,
        }
    }
}

impl fmt::Debug for Repr {
    fn fmt(&self, fmt: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            Repr::Os(ref code) =>
                fmt.debug_struct("Os").field("code", code).finish(),
            Repr::Custom(ref c) => fmt.debug_tuple("Custom").field(c).finish(),
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, fmt: &mut fmt::Formatter) -> fmt::Result {
        match self.repr {
            Repr::Os(code) => {
                write!(fmt, "os error {}", code)
            }
            Repr::Custom(ref c) => c.error.fmt(fmt),
        }
    }
}

impl error::Error for Error {
    fn description(&self) -> &str {
        match self.repr {
            Repr::Os(..) => match self.kind() {
                ErrorKind::NotFound => "entity not found",
                ErrorKind::PermissionDenied => "permission denied",
                ErrorKind::ConnectionRefused => "connection refused",
                ErrorKind::ConnectionReset => "connection reset",
                ErrorKind::ConnectionAborted => "connection aborted",
                ErrorKind::NotConnected => "not connected",
                ErrorKind::AddrInUse => "address in use",
                ErrorKind::AddrNotAvailable => "address not available",
                ErrorKind::BrokenPipe => "broken pipe",
                ErrorKind::AlreadyExists => "entity already exists",
                ErrorKind::WouldBlock => "operation would block",
                ErrorKind::InvalidInput => "invalid input parameter",
                ErrorKind::InvalidData => "invalid data",
                ErrorKind::TimedOut => "timed out",
                ErrorKind::WriteZero => "write zero",
                ErrorKind::Interrupted => "operation interrupted",
                ErrorKind::Other => "other os error",
                ErrorKind::UnexpectedEof => "unexpected end of file",
                ErrorKind::__Nonexhaustive => unreachable!()
            },
            Repr::Custom(ref c) => {
                #[cfg(feature="io_error_alloc")]
                { c.error.description() }
                #[cfg(not(feature="io_error_alloc"))]
                { c.error }
            },
        }
    }

    fn cause(&self) -> Option<&error::Error> {
        match self.repr {
            Repr::Os(..) => None,
            Repr::Custom(ref _c) => {
                #[cfg(feature="io_error_alloc")]
                { _c.error.cause() }
                #[cfg(not(feature="io_error_alloc"))]
                { None }
            }
        }
    }
}

fn _assert_error_is_sync_send() {
    fn _is_sync_send<T: Sync+Send>() {}
    _is_sync_send::<Error>();
}

#[cfg(test)]
mod test {
    use prelude::v1::*;
    use super::{Error, ErrorKind};
    use error;
    use fmt;
    use sys::os::error_string;

    #[test]
    fn test_debug_error() {
        let code = 6;
        let msg = error_string(code);
        let err = Error { repr: super::Repr::Os(code) };
        let expected = format!("Error {{ repr: Os {{ code: {:?}, message: {:?} }} }}", code, msg);
        assert_eq!(format!("{:?}", err), expected);
    }

    #[test]
    fn test_downcasting() {
        #[derive(Debug)]
        struct TestError;

        impl fmt::Display for TestError {
            fn fmt(&self, _: &mut fmt::Formatter) -> fmt::Result {
                Ok(())
            }
        }

        impl error::Error for TestError {
            fn description(&self) -> &str {
                "asdf"
            }
        }

        // we have to call all of these UFCS style right now since method
        // resolution won't implicitly drop the Send+Sync bounds
        let mut err = Error::new(ErrorKind::Other, TestError);
        assert!(err.get_ref().unwrap().is::<TestError>());
        assert_eq!("asdf", err.get_ref().unwrap().description());
        assert!(err.get_mut().unwrap().is::<TestError>());
        let extracted = err.into_inner().unwrap();
        extracted.downcast::<TestError>().unwrap();
    }
}
