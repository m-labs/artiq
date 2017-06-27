// Copyright 2015 The Rust Project Developers. See the COPYRIGHT
// file at the top-level directory of this distribution and at
// http://rust-lang.org/COPYRIGHT.
//
// Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
// http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
// <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
// option. This file may not be copied, modified, or distributed
// except according to those terms.

//! Traits, helpers, and type definitions for core I/O functionality.
//!
//! The `std::io` module contains a number of common things you'll need
//! when doing input and output. The most core part of this module is
//! the [`Read`][read] and [`Write`][write] traits, which provide the
//! most general interface for reading and writing input and output.
//!
//! [read]: trait.Read.html
//! [write]: trait.Write.html
//!
//! # Read and Write
//!
//! Because they are traits, `Read` and `Write` are implemented by a number
//! of other types, and you can implement them for your types too. As such,
//! you'll see a few different types of I/O throughout the documentation in
//! this module: `File`s, `TcpStream`s, and sometimes even `Vec<T>`s. For
//! example, `Read` adds a `read()` method, which we can use on `File`s:
//!
//! ```
//! use std::io;
//! use std::io::prelude::*;
//! use std::fs::File;
//!
//! # fn foo() -> io::Result<()> {
//! let mut f = try!(File::open("foo.txt"));
//! let mut buffer = [0; 10];
//!
//! // read up to 10 bytes
//! try!(f.read(&mut buffer));
//!
//! println!("The bytes: {:?}", buffer);
//! # Ok(())
//! # }
//! ```
//!
//! `Read` and `Write` are so important, implementors of the two traits have a
//! nickname: readers and writers. So you'll sometimes see 'a reader' instead
//! of 'a type that implements the `Read` trait'. Much easier!
//!
//! ## Seek and BufRead
//!
//! Beyond that, there are two important traits that are provided: [`Seek`][seek]
//! and [`BufRead`][bufread]. Both of these build on top of a reader to control
//! how the reading happens. `Seek` lets you control where the next byte is
//! coming from:
//!
//! ```
//! use std::io;
//! use std::io::prelude::*;
//! use std::io::SeekFrom;
//! use std::fs::File;
//!
//! # fn foo() -> io::Result<()> {
//! let mut f = try!(File::open("foo.txt"));
//! let mut buffer = [0; 10];
//!
//! // skip to the last 10 bytes of the file
//! try!(f.seek(SeekFrom::End(-10)));
//!
//! // read up to 10 bytes
//! try!(f.read(&mut buffer));
//!
//! println!("The bytes: {:?}", buffer);
//! # Ok(())
//! # }
//! ```
//!
//! [seek]: trait.Seek.html
//! [bufread]: trait.BufRead.html
//!
//! `BufRead` uses an internal buffer to provide a number of other ways to read, but
//! to show it off, we'll need to talk about buffers in general. Keep reading!
//!
//! ## BufReader and BufWriter
//!
//! Byte-based interfaces are unwieldy and can be inefficient, as we'd need to be
//! making near-constant calls to the operating system. To help with this,
//! `std::io` comes with two structs, `BufReader` and `BufWriter`, which wrap
//! readers and writers. The wrapper uses a buffer, reducing the number of
//! calls and providing nicer methods for accessing exactly what you want.
//!
//! For example, `BufReader` works with the `BufRead` trait to add extra
//! methods to any reader:
//!
//! ```
//! use std::io;
//! use std::io::prelude::*;
//! use std::io::BufReader;
//! use std::fs::File;
//!
//! # fn foo() -> io::Result<()> {
//! let f = try!(File::open("foo.txt"));
//! let mut reader = BufReader::new(f);
//! let mut buffer = String::new();
//!
//! // read a line into buffer
//! try!(reader.read_line(&mut buffer));
//!
//! println!("{}", buffer);
//! # Ok(())
//! # }
//! ```
//!
//! `BufWriter` doesn't add any new ways of writing; it just buffers every call
//! to [`write()`][write()]:
//!
//! ```
//! use std::io;
//! use std::io::prelude::*;
//! use std::io::BufWriter;
//! use std::fs::File;
//!
//! # fn foo() -> io::Result<()> {
//! let f = try!(File::create("foo.txt"));
//! {
//!     let mut writer = BufWriter::new(f);
//!
//!     // write a byte to the buffer
//!     try!(writer.write(&[42]));
//!
//! } // the buffer is flushed once writer goes out of scope
//!
//! # Ok(())
//! # }
//! ```
//!
//! [write()]: trait.Write.html#tymethod.write
//!
//! ## Standard input and output
//!
//! A very common source of input is standard input:
//!
//! ```
//! use std::io;
//!
//! # fn foo() -> io::Result<()> {
//! let mut input = String::new();
//!
//! try!(io::stdin().read_line(&mut input));
//!
//! println!("You typed: {}", input.trim());
//! # Ok(())
//! # }
//! ```
//!
//! And a very common source of output is standard output:
//!
//! ```
//! use std::io;
//! use std::io::prelude::*;
//!
//! # fn foo() -> io::Result<()> {
//! try!(io::stdout().write(&[42]));
//! # Ok(())
//! # }
//! ```
//!
//! Of course, using `io::stdout()` directly is less common than something like
//! `println!`.
//!
//! ## Iterator types
//!
//! A large number of the structures provided by `std::io` are for various
//! ways of iterating over I/O. For example, `Lines` is used to split over
//! lines:
//!
//! ```
//! use std::io;
//! use std::io::prelude::*;
//! use std::io::BufReader;
//! use std::fs::File;
//!
//! # fn foo() -> io::Result<()> {
//! let f = try!(File::open("foo.txt"));
//! let reader = BufReader::new(f);
//!
//! for line in reader.lines() {
//!     println!("{}", try!(line));
//! }
//!
//! # Ok(())
//! # }
//! ```
//!
//! ## Functions
//!
//! There are a number of [functions][functions-list] that offer access to various
//! features. For example, we can use three of these functions to copy everything
//! from standard input to standard output:
//!
//! ```
//! use std::io;
//!
//! # fn foo() -> io::Result<()> {
//! try!(io::copy(&mut io::stdin(), &mut io::stdout()));
//! # Ok(())
//! # }
//! ```
//!
//! [functions-list]: #functions-1
//!
//! ## io::Result
//!
//! Last, but certainly not least, is [`io::Result`][result]. This type is used
//! as the return type of many `std::io` functions that can cause an error, and
//! can be returned from your own functions as well. Many of the examples in this
//! module use the [`try!`][try] macro:
//!
//! ```
//! use std::io;
//!
//! fn read_input() -> io::Result<()> {
//!     let mut input = String::new();
//!
//!     try!(io::stdin().read_line(&mut input));
//!
//!     println!("You typed: {}", input.trim());
//!
//!     Ok(())
//! }
//! ```
//!
//! The return type of `read_input()`, `io::Result<()>`, is a very common type
//! for functions which don't have a 'real' return value, but do want to return
//! errors if they happen. In this case, the only purpose of this function is
//! to read the line and print it, so we use `()`.
//!
//! [result]: type.Result.html
//! [try]: ../macro.try!.html
//!
//! ## Platform-specific behavior
//!
//! Many I/O functions throughout the standard library are documented to indicate
//! what various library or syscalls they are delegated to. This is done to help
//! applications both understand what's happening under the hood as well as investigate
//! any possibly unclear semantics. Note, however, that this is informative, not a binding
//! contract. The implementation of many of these functions are subject to change over
//! time and may call fewer or more syscalls/library functions.

use core::cmp;
use core::fmt;
use core::iter::{Iterator};
use core::marker::Sized;
 use core::ops::{Drop, FnOnce};
use core::option::Option::{self, Some, None};
use core::result::Result::{Ok, Err};
use core::result;
 use collections::string::String;
 use collections::vec::Vec;
 use collections::str;
mod memchr;

 pub use self::buffered::{BufReader, BufWriter, LineWriter};
 pub use self::buffered::IntoInnerError;
 pub use self::cursor::Cursor;
pub use self::error::{Result, Error, ErrorKind};
pub use self::util::{copy, sink, Sink, empty, Empty, repeat, Repeat};

pub mod prelude;
 mod buffered;
 mod cursor;
mod error;
mod impls;
mod util;

const DEFAULT_BUF_SIZE: usize = 8 * 1024;

// A few methods below (read_to_string, read_line) will append data into a
// `String` buffer, but we need to be pretty careful when doing this. The
// implementation will just call `.as_mut_vec()` and then delegate to a
// byte-oriented reading method, but we must ensure that when returning we never
// leave `buf` in a state such that it contains invalid UTF-8 in its bounds.
//
// To this end, we use an RAII guard (to protect against panics) which updates
// the length of the string when it is dropped. This guard initially truncates
// the string to the prior length and only after we've validated that the
// new contents are valid UTF-8 do we allow it to set a longer length.
//
// The unsafety in this function is twofold:
//
// 1. We're looking at the raw bytes of `buf`, so we take on the burden of UTF-8
//    checks.
// 2. We're passing a raw buffer to the function `f`, and it is expected that
//    the function only *appends* bytes to the buffer. We'll get undefined
//    behavior if existing bytes are overwritten to have non-UTF-8 data.

fn append_to_string<F>(buf: &mut String, f: F) -> Result<usize>
    where F: FnOnce(&mut Vec<u8>) -> Result<usize>
{
    struct Guard<'a> { s: &'a mut Vec<u8>, len: usize }
        impl<'a> Drop for Guard<'a> {
        fn drop(&mut self) {
            unsafe { self.s.set_len(self.len); }
        }
    }

    unsafe {
        let mut g = Guard { len: buf.len(), s: buf.as_mut_vec() };
        let ret = f(g.s);
        if str::from_utf8(&g.s[g.len..]).is_err() {
            ret.and_then(|_| {
                Err(Error::new(ErrorKind::InvalidData,
                               "stream did not contain valid UTF-8"))
            })
        } else {
            g.len = g.s.len();
            ret
        }
    }
}

// This uses an adaptive system to extend the vector when it fills. We want to
// avoid paying to allocate and zero a huge chunk of memory if the reader only
// has 4 bytes while still making large reads if the reader does have a ton
// of data to return. Simply tacking on an extra DEFAULT_BUF_SIZE space every
// time is 4,500 times (!) slower than this if the reader has a very small
// amount of data to return.

fn read_to_end<R: Read + ?Sized>(r: &mut R, buf: &mut Vec<u8>) -> Result<usize> {
    let start_len = buf.len();
    let mut len = start_len;
    let mut new_write_size = 16;
    let ret;
    loop {
        if len == buf.len() {
            if new_write_size < DEFAULT_BUF_SIZE {
                new_write_size *= 2;
            }
            buf.resize(len + new_write_size, 0);
        }

        match r.read(&mut buf[len..]) {
            Ok(0) => {
                ret = Ok(len - start_len);
                break;
            }
            Ok(n) => len += n,
            Err(ref e) if e.kind() == ErrorKind::Interrupted => {}
            Err(e) => {
                ret = Err(e);
                break;
            }
        }
    }

    buf.truncate(len);
    ret
}

/// The `Read` trait allows for reading bytes from a source.
///
/// Implementors of the `Read` trait are sometimes called 'readers'.
///
/// Readers are defined by one required method, `read()`. Each call to `read`
/// will attempt to pull bytes from this source into a provided buffer. A
/// number of other methods are implemented in terms of `read()`, giving
/// implementors a number of ways to read bytes while only needing to implement
/// a single method.
///
/// Readers are intended to be composable with one another. Many implementors
/// throughout `std::io` take and provide types which implement the `Read`
/// trait.
///
/// Please note that each call to `read` may involve a system call, and
/// therefore, using something that implements [`BufRead`][bufread], such as
/// [`BufReader`][bufreader], will be more efficient.
///
/// [bufread]: trait.BufRead.html
/// [bufreader]: struct.BufReader.html
///
/// # Examples
///
/// [`File`][file]s implement `Read`:
///
/// [file]: ../fs/struct.File.html
///
/// ```
/// use std::io;
/// use std::io::prelude::*;
/// use std::fs::File;
///
/// # fn foo() -> io::Result<()> {
/// let mut f = try!(File::open("foo.txt"));
/// let mut buffer = [0; 10];
///
/// // read up to 10 bytes
/// try!(f.read(&mut buffer));
///
/// let mut buffer = vec![0; 10];
/// // read the whole file
/// try!(f.read_to_end(&mut buffer));
///
/// // read into a String, so that you don't need to do the conversion.
/// let mut buffer = String::new();
/// try!(f.read_to_string(&mut buffer));
///
/// // and more! See the other methods for more details.
/// # Ok(())
/// # }
/// ```
pub trait Read {
    /// Pull some bytes from this source into the specified buffer, returning
    /// how many bytes were read.
    ///
    /// This function does not provide any guarantees about whether it blocks
    /// waiting for data, but if an object needs to block for a read but cannot
    /// it will typically signal this via an `Err` return value.
    ///
    /// If the return value of this method is `Ok(n)`, then it must be
    /// guaranteed that `0 <= n <= buf.len()`. A nonzero `n` value indicates
    /// that the buffer `buf` has been filled in with `n` bytes of data from this
    /// source. If `n` is `0`, then it can indicate one of two scenarios:
    ///
    /// 1. This reader has reached its "end of file" and will likely no longer
    ///    be able to produce bytes. Note that this does not mean that the
    ///    reader will *always* no longer be able to produce bytes.
    /// 2. The buffer specified was 0 bytes in length.
    ///
    /// No guarantees are provided about the contents of `buf` when this
    /// function is called, implementations cannot rely on any property of the
    /// contents of `buf` being true. It is recommended that implementations
    /// only write data to `buf` instead of reading its contents.
    ///
    /// # Errors
    ///
    /// If this function encounters any form of I/O or other error, an error
    /// variant will be returned. If an error is returned then it must be
    /// guaranteed that no bytes were read.
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f = try!(File::open("foo.txt"));
    /// let mut buffer = [0; 10];
    ///
    /// // read 10 bytes
    /// try!(f.read(&mut buffer[..]));
    /// # Ok(())
    /// # }
    /// ```
    fn read(&mut self, buf: &mut [u8]) -> Result<usize>;

    /// Read all bytes until EOF in this source, placing them into `buf`.
    ///
    /// All bytes read from this source will be appended to the specified buffer
    /// `buf`. This function will continuously call `read` to append more data to
    /// `buf` until `read` returns either `Ok(0)` or an error of
    /// non-`ErrorKind::Interrupted` kind.
    ///
    /// If successful, this function will return the total number of bytes read.
    ///
    /// # Errors
    ///
    /// If this function encounters an error of the kind
    /// `ErrorKind::Interrupted` then the error is ignored and the operation
    /// will continue.
    ///
    /// If any other read error is encountered then this function immediately
    /// returns. Any bytes which have already been read will be appended to
    /// `buf`.
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f = try!(File::open("foo.txt"));
    /// let mut buffer = Vec::new();
    ///
    /// // read the whole file
    /// try!(f.read_to_end(&mut buffer));
    /// # Ok(())
    /// # }
    /// ```

    fn read_to_end(&mut self, buf: &mut Vec<u8>) -> Result<usize> {
        read_to_end(self, buf)
    }

    /// Read all bytes until EOF in this source, placing them into `buf`.
    ///
    /// If successful, this function returns the number of bytes which were read
    /// and appended to `buf`.
    ///
    /// # Errors
    ///
    /// If the data in this stream is *not* valid UTF-8 then an error is
    /// returned and `buf` is unchanged.
    ///
    /// See [`read_to_end()`][readtoend] for other error semantics.
    ///
    /// [readtoend]: #method.read_to_end
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f = try!(File::open("foo.txt"));
    /// let mut buffer = String::new();
    ///
    /// try!(f.read_to_string(&mut buffer));
    /// # Ok(())
    /// # }
    /// ```

    fn read_to_string(&mut self, buf: &mut String) -> Result<usize> {
        // Note that we do *not* call `.read_to_end()` here. We are passing
        // `&mut Vec<u8>` (the raw contents of `buf`) into the `read_to_end`
        // method to fill it up. An arbitrary implementation could overwrite the
        // entire contents of the vector, not just append to it (which is what
        // we are expecting).
        //
        // To prevent extraneously checking the UTF-8-ness of the entire buffer
        // we pass it to our hardcoded `read_to_end` implementation which we
        // know is guaranteed to only read data into the end of the buffer.
        append_to_string(buf, |b| read_to_end(self, b))
    }

    /// Read the exact number of bytes required to fill `buf`.
    ///
    /// This function reads as many bytes as necessary to completely fill the
    /// specified buffer `buf`.
    ///
    /// No guarantees are provided about the contents of `buf` when this
    /// function is called, implementations cannot rely on any property of the
    /// contents of `buf` being true. It is recommended that implementations
    /// only write data to `buf` instead of reading its contents.
    ///
    /// # Errors
    ///
    /// If this function encounters an error of the kind
    /// `ErrorKind::Interrupted` then the error is ignored and the operation
    /// will continue.
    ///
    /// If this function encounters an "end of file" before completely filling
    /// the buffer, it returns an error of the kind `ErrorKind::UnexpectedEof`.
    /// The contents of `buf` are unspecified in this case.
    ///
    /// If any other read error is encountered then this function immediately
    /// returns. The contents of `buf` are unspecified in this case.
    ///
    /// If this function returns an error, it is unspecified how many bytes it
    /// has read, but it will never read more than would be necessary to
    /// completely fill the buffer.
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f = try!(File::open("foo.txt"));
    /// let mut buffer = [0; 10];
    ///
    /// // read exactly 10 bytes
    /// try!(f.read_exact(&mut buffer));
    /// # Ok(())
    /// # }
    /// ```
    fn read_exact(&mut self, mut buf: &mut [u8]) -> Result<()> {
        while !buf.is_empty() {
            match self.read(buf) {
                Ok(0) => break,
                Ok(n) => { let tmp = buf; buf = &mut tmp[n..]; }
                Err(ref e) if e.kind() == ErrorKind::Interrupted => {}
                Err(e) => return Err(e),
            }
        }
        if !buf.is_empty() {
            Err(Error::new(ErrorKind::UnexpectedEof,
                           "failed to fill whole buffer"))
        } else {
            Ok(())
        }
    }

    /// Creates a "by reference" adaptor for this instance of `Read`.
    ///
    /// The returned adaptor also implements `Read` and will simply borrow this
    /// current reader.
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// use std::io;
    /// use std::io::Read;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f = try!(File::open("foo.txt"));
    /// let mut buffer = Vec::new();
    /// let mut other_buffer = Vec::new();
    ///
    /// {
    ///     let reference = f.by_ref();
    ///
    ///     // read at most 5 bytes
    ///     try!(reference.take(5).read_to_end(&mut buffer));
    ///
    /// } // drop our &mut reference so we can use f again
    ///
    /// // original file still usable, read the rest
    /// try!(f.read_to_end(&mut other_buffer));
    /// # Ok(())
    /// # }
    /// ```
    fn by_ref(&mut self) -> &mut Self where Self: Sized { self }

    /// Transforms this `Read` instance to an `Iterator` over its bytes.
    ///
    /// The returned type implements `Iterator` where the `Item` is `Result<u8,
    /// R::Err>`.  The yielded item is `Ok` if a byte was successfully read and
    /// `Err` otherwise for I/O errors. EOF is mapped to returning `None` from
    /// this iterator.
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f = try!(File::open("foo.txt"));
    ///
    /// for byte in f.bytes() {
    ///     println!("{}", byte.unwrap());
    /// }
    /// # Ok(())
    /// # }
    /// ```
    fn bytes(self) -> Bytes<Self> where Self: Sized {
        Bytes { inner: self }
    }

    /// Transforms this `Read` instance to an `Iterator` over `char`s.
    ///
    /// This adaptor will attempt to interpret this reader as a UTF-8 encoded
    /// sequence of characters. The returned iterator will return `None` once
    /// EOF is reached for this reader. Otherwise each element yielded will be a
    /// `Result<char, E>` where `E` may contain information about what I/O error
    /// occurred or where decoding failed.
    ///
    /// Currently this adaptor will discard intermediate data read, and should
    /// be avoided if this is not desired.
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// #![feature(io)]
    /// use std::io;
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f = try!(File::open("foo.txt"));
    ///
    /// for c in f.chars() {
    ///     println!("{}", c.unwrap());
    /// }
    /// # Ok(())
    /// # }
    /// ```
    fn chars(self) -> Chars<Self> where Self: Sized {
        Chars { inner: self }
    }

    /// Creates an adaptor which will chain this stream with another.
    ///
    /// The returned `Read` instance will first read all bytes from this object
    /// until EOF is encountered. Afterwards the output is equivalent to the
    /// output of `next`.
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f1 = try!(File::open("foo.txt"));
    /// let mut f2 = try!(File::open("bar.txt"));
    ///
    /// let mut handle = f1.chain(f2);
    /// let mut buffer = String::new();
    ///
    /// // read the value into a String. We could use any Read method here,
    /// // this is just one example.
    /// try!(handle.read_to_string(&mut buffer));
    /// # Ok(())
    /// # }
    /// ```
    fn chain<R: Read>(self, next: R) -> Chain<Self, R> where Self: Sized {
        Chain { first: self, second: next, done_first: false }
    }

    /// Creates an adaptor which will read at most `limit` bytes from it.
    ///
    /// This function returns a new instance of `Read` which will read at most
    /// `limit` bytes, after which it will always return EOF (`Ok(0)`). Any
    /// read errors will not count towards the number of bytes read and future
    /// calls to `read` may succeed.
    ///
    /// # Examples
    ///
    /// [`File`][file]s implement `Read`:
    ///
    /// [file]: ../fs/struct.File.html
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> io::Result<()> {
    /// let mut f = try!(File::open("foo.txt"));
    /// let mut buffer = [0; 5];
    ///
    /// // read at most five bytes
    /// let mut handle = f.take(5);
    ///
    /// try!(handle.read(&mut buffer));
    /// # Ok(())
    /// # }
    /// ```
    fn take(self, limit: u64) -> Take<Self> where Self: Sized {
        Take { inner: self, limit: limit }
    }
}

/// A trait for objects which are byte-oriented sinks.
///
/// Implementors of the `Write` trait are sometimes called 'writers'.
///
/// Writers are defined by two required methods, `write()` and `flush()`:
///
/// * The `write()` method will attempt to write some data into the object,
///   returning how many bytes were successfully written.
///
/// * The `flush()` method is useful for adaptors and explicit buffers
///   themselves for ensuring that all buffered data has been pushed out to the
///   'true sink'.
///
/// Writers are intended to be composable with one another. Many implementors
/// throughout `std::io` take and provide types which implement the `Write`
/// trait.
///
/// # Examples
///
/// ```
/// use std::io::prelude::*;
/// use std::fs::File;
///
/// # fn foo() -> std::io::Result<()> {
/// let mut buffer = try!(File::create("foo.txt"));
///
/// try!(buffer.write(b"some bytes"));
/// # Ok(())
/// # }
/// ```
pub trait Write {
    /// Write a buffer into this object, returning how many bytes were written.
    ///
    /// This function will attempt to write the entire contents of `buf`, but
    /// the entire write may not succeed, or the write may also generate an
    /// error. A call to `write` represents *at most one* attempt to write to
    /// any wrapped object.
    ///
    /// Calls to `write` are not guaranteed to block waiting for data to be
    /// written, and a write which would otherwise block can be indicated through
    /// an `Err` variant.
    ///
    /// If the return value is `Ok(n)` then it must be guaranteed that
    /// `0 <= n <= buf.len()`. A return value of `0` typically means that the
    /// underlying object is no longer able to accept bytes and will likely not
    /// be able to in the future as well, or that the buffer provided is empty.
    ///
    /// # Errors
    ///
    /// Each call to `write` may generate an I/O error indicating that the
    /// operation could not be completed. If an error is returned then no bytes
    /// in the buffer were written to this writer.
    ///
    /// It is **not** considered an error if the entire buffer could not be
    /// written to this writer.
    ///
    /// # Examples
    ///
    /// ```
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> std::io::Result<()> {
    /// let mut buffer = try!(File::create("foo.txt"));
    ///
    /// try!(buffer.write(b"some bytes"));
    /// # Ok(())
    /// # }
    /// ```
    fn write(&mut self, buf: &[u8]) -> Result<usize>;

    /// Flush this output stream, ensuring that all intermediately buffered
    /// contents reach their destination.
    ///
    /// # Errors
    ///
    /// It is considered an error if not all bytes could be written due to
    /// I/O errors or EOF being reached.
    ///
    /// # Examples
    ///
    /// ```
    /// use std::io::prelude::*;
    /// use std::io::BufWriter;
    /// use std::fs::File;
    ///
    /// # fn foo() -> std::io::Result<()> {
    /// let mut buffer = BufWriter::new(try!(File::create("foo.txt")));
    ///
    /// try!(buffer.write(b"some bytes"));
    /// try!(buffer.flush());
    /// # Ok(())
    /// # }
    /// ```
    fn flush(&mut self) -> Result<()>;

    /// Attempts to write an entire buffer into this write.
    ///
    /// This method will continuously call `write` while there is more data to
    /// write. This method will not return until the entire buffer has been
    /// successfully written or an error occurs. The first error generated from
    /// this method will be returned.
    ///
    /// # Errors
    ///
    /// This function will return the first error that `write` returns.
    ///
    /// # Examples
    ///
    /// ```
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> std::io::Result<()> {
    /// let mut buffer = try!(File::create("foo.txt"));
    ///
    /// try!(buffer.write_all(b"some bytes"));
    /// # Ok(())
    /// # }
    /// ```
    fn write_all(&mut self, mut buf: &[u8]) -> Result<()> {
        while !buf.is_empty() {
            match self.write(buf) {
                Ok(0) => return Err(Error::new(ErrorKind::WriteZero,
                                               "failed to write whole buffer")),
                Ok(n) => buf = &buf[n..],
                Err(ref e) if e.kind() == ErrorKind::Interrupted => {}
                Err(e) => return Err(e),
            }
        }
        Ok(())
    }

    /// Writes a formatted string into this writer, returning any error
    /// encountered.
    ///
    /// This method is primarily used to interface with the
    /// [`format_args!`][formatargs] macro, but it is rare that this should
    /// explicitly be called. The [`write!`][write] macro should be favored to
    /// invoke this method instead.
    ///
    /// [formatargs]: ../macro.format_args!.html
    /// [write]: ../macro.write!.html
    ///
    /// This function internally uses the [`write_all`][writeall] method on
    /// this trait and hence will continuously write data so long as no errors
    /// are received. This also means that partial writes are not indicated in
    /// this signature.
    ///
    /// [writeall]: #method.write_all
    ///
    /// # Errors
    ///
    /// This function will return any I/O error reported while formatting.
    ///
    /// # Examples
    ///
    /// ```
    /// use std::io::prelude::*;
    /// use std::fs::File;
    ///
    /// # fn foo() -> std::io::Result<()> {
    /// let mut buffer = try!(File::create("foo.txt"));
    ///
    /// // this call
    /// try!(write!(buffer, "{:.*}", 2, 1.234567));
    /// // turns into this:
    /// try!(buffer.write_fmt(format_args!("{:.*}", 2, 1.234567)));
    /// # Ok(())
    /// # }
    /// ```
    fn write_fmt(&mut self, fmt: fmt::Arguments) -> Result<()> {
        // Create a shim which translates a Write to a fmt::Write and saves
        // off I/O errors. instead of discarding them
        struct Adaptor<'a, T: ?Sized + 'a> {
            inner: &'a mut T,
            error: Result<()>,
        }

        impl<'a, T: Write + ?Sized> fmt::Write for Adaptor<'a, T> {
            fn write_str(&mut self, s: &str) -> fmt::Result {
                match self.inner.write_all(s.as_bytes()) {
                    Ok(()) => Ok(()),
                    Err(e) => {
                        self.error = Err(e);
                        Err(fmt::Error)
                    }
                }
            }
        }

        let mut output = Adaptor { inner: self, error: Ok(()) };
        match fmt::write(&mut output, fmt) {
            Ok(()) => Ok(()),
            Err(..) => {
                // check if the error came from the underlying `Write` or not
                if output.error.is_err() {
                    output.error
                } else {
                    Err(Error::new(ErrorKind::Other, "formatter error"))
                }
            }
        }
    }

    /// Creates a "by reference" adaptor for this instance of `Write`.
    ///
    /// The returned adaptor also implements `Write` and will simply borrow this
    /// current writer.
    ///
    /// # Examples
    ///
    /// ```
    /// use std::io::Write;
    /// use std::fs::File;
    ///
    /// # fn foo() -> std::io::Result<()> {
    /// let mut buffer = try!(File::create("foo.txt"));
    ///
    /// let reference = buffer.by_ref();
    ///
    /// // we can use reference just like our original buffer
    /// try!(reference.write_all(b"some bytes"));
    /// # Ok(())
    /// # }
    /// ```
    fn by_ref(&mut self) -> &mut Self where Self: Sized { self }
}

/// The `Seek` trait provides a cursor which can be moved within a stream of
/// bytes.
///
/// The stream typically has a fixed size, allowing seeking relative to either
/// end or the current offset.
///
/// # Examples
///
/// [`File`][file]s implement `Seek`:
///
/// [file]: ../fs/struct.File.html
///
/// ```
/// use std::io;
/// use std::io::prelude::*;
/// use std::fs::File;
/// use std::io::SeekFrom;
///
/// # fn foo() -> io::Result<()> {
/// let mut f = try!(File::open("foo.txt"));
///
/// // move the cursor 42 bytes from the start of the file
/// try!(f.seek(SeekFrom::Start(42)));
/// # Ok(())
/// # }
/// ```
pub trait Seek {
    /// Seek to an offset, in bytes, in a stream.
    ///
    /// A seek beyond the end of a stream is allowed, but implementation
    /// defined.
    ///
    /// If the seek operation completed successfully,
    /// this method returns the new position from the start of the stream.
    /// That position can be used later with `SeekFrom::Start`.
    ///
    /// # Errors
    ///
    /// Seeking to a negative offset is considered an error.
    fn seek(&mut self, pos: SeekFrom) -> Result<u64>;
}

/// Enumeration of possible methods to seek within an I/O object.
#[derive(Copy, PartialEq, Eq, Clone, Debug)]
pub enum SeekFrom {
    /// Set the offset to the provided number of bytes.
    Start(u64),

    /// Set the offset to the size of this object plus the specified number of
    /// bytes.
    ///
    /// It is possible to seek beyond the end of an object, but it's an error to
    /// seek before byte 0.
    End(i64),

    /// Set the offset to the current position plus the specified number of
    /// bytes.
    ///
    /// It is possible to seek beyond the end of an object, but it's an error to
    /// seek before byte 0.
    Current(i64),
}


fn read_until<R: BufRead + ?Sized>(r: &mut R, delim: u8, buf: &mut Vec<u8>)
                                   -> Result<usize> {
    let mut read = 0;
    loop {
        let (done, used) = {
            let available = match r.fill_buf() {
                Ok(n) => n,
                Err(ref e) if e.kind() == ErrorKind::Interrupted => continue,
                Err(e) => return Err(e)
            };
            match memchr::memchr(delim, available) {
                Some(i) => {
                    buf.extend_from_slice(&available[..i + 1]);
                    (true, i + 1)
                }
                None => {
                    buf.extend_from_slice(available);
                    (false, available.len())
                }
            }
        };
        r.consume(used);
        read += used;
        if done || used == 0 {
            return Ok(read);
        }
    }
}

/// A `BufRead` is a type of `Read`er which has an internal buffer, allowing it
/// to perform extra ways of reading.
///
/// For example, reading line-by-line is inefficient without using a buffer, so
/// if you want to read by line, you'll need `BufRead`, which includes a
/// [`read_line()`][readline] method as well as a [`lines()`][lines] iterator.
///
/// [readline]: #method.read_line
/// [lines]: #method.lines
///
/// # Examples
///
/// A locked standard input implements `BufRead`:
///
/// ```
/// use std::io;
/// use std::io::prelude::*;
///
/// let stdin = io::stdin();
/// for line in stdin.lock().lines() {
///     println!("{}", line.unwrap());
/// }
/// ```
///
/// If you have something that implements `Read`, you can use the [`BufReader`
/// type][bufreader] to turn it into a `BufRead`.
///
/// For example, [`File`][file] implements `Read`, but not `BufRead`.
/// `BufReader` to the rescue!
///
/// [bufreader]: struct.BufReader.html
/// [file]: ../fs/struct.File.html
///
/// ```
/// use std::io::{self, BufReader};
/// use std::io::prelude::*;
/// use std::fs::File;
///
/// # fn foo() -> io::Result<()> {
/// let f = try!(File::open("foo.txt"));
/// let f = BufReader::new(f);
///
/// for line in f.lines() {
///     println!("{}", line.unwrap());
/// }
///
/// # Ok(())
/// # }
/// ```
///

pub trait BufRead: Read {
    /// Fills the internal buffer of this object, returning the buffer contents.
    ///
    /// This function is a lower-level call. It needs to be paired with the
    /// [`consume`][consume] method to function properly. When calling this
    /// method, none of the contents will be "read" in the sense that later
    /// calling `read` may return the same contents. As such, `consume` must be
    /// called with the number of bytes that are consumed from this buffer to
    /// ensure that the bytes are never returned twice.
    ///
    /// [consume]: #tymethod.consume
    ///
    /// An empty buffer returned indicates that the stream has reached EOF.
    ///
    /// # Errors
    ///
    /// This function will return an I/O error if the underlying reader was
    /// read, but returned an error.
    ///
    /// # Examples
    ///
    /// A locked standard input implements `BufRead`:
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    ///
    /// let stdin = io::stdin();
    /// let mut stdin = stdin.lock();
    ///
    /// // we can't have two `&mut` references to `stdin`, so use a block
    /// // to end the borrow early.
    /// let length = {
    ///     let buffer = stdin.fill_buf().unwrap();
    ///
    ///     // work with buffer
    ///     println!("{:?}", buffer);
    ///
    ///     buffer.len()
    /// };
    ///
    /// // ensure the bytes we worked with aren't returned again later
    /// stdin.consume(length);
    /// ```
    fn fill_buf(&mut self) -> Result<&[u8]>;

    /// Tells this buffer that `amt` bytes have been consumed from the buffer,
    /// so they should no longer be returned in calls to `read`.
    ///
    /// This function is a lower-level call. It needs to be paired with the
    /// [`fill_buf`][fillbuf] method to function properly. This function does
    /// not perform any I/O, it simply informs this object that some amount of
    /// its buffer, returned from `fill_buf`, has been consumed and should no
    /// longer be returned. As such, this function may do odd things if
    /// `fill_buf` isn't called before calling it.
    ///
    /// [fillbuf]: #tymethod.fill_buf
    ///
    /// The `amt` must be `<=` the number of bytes in the buffer returned by
    /// `fill_buf`.
    ///
    /// # Examples
    ///
    /// Since `consume()` is meant to be used with [`fill_buf()`][fillbuf],
    /// that method's example includes an example of `consume()`.
    fn consume(&mut self, amt: usize);

    /// Read all bytes into `buf` until the delimiter `byte` is reached.
    ///
    /// This function will read bytes from the underlying stream until the
    /// delimiter or EOF is found. Once found, all bytes up to, and including,
    /// the delimiter (if found) will be appended to `buf`.
    ///
    /// If this reader is currently at EOF then this function will not modify
    /// `buf` and will return `Ok(n)` where `n` is the number of bytes which
    /// were read.
    ///
    /// # Errors
    ///
    /// This function will ignore all instances of `ErrorKind::Interrupted` and
    /// will otherwise return any errors returned by `fill_buf`.
    ///
    /// If an I/O error is encountered then all bytes read so far will be
    /// present in `buf` and its length will have been adjusted appropriately.
    ///
    /// # Examples
    ///
    /// A locked standard input implements `BufRead`. In this example, we'll
    /// read from standard input until we see an `a` byte.
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    ///
    /// fn foo() -> io::Result<()> {
    /// let stdin = io::stdin();
    /// let mut stdin = stdin.lock();
    /// let mut buffer = Vec::new();
    ///
    /// try!(stdin.read_until(b'a', &mut buffer));
    ///
    /// println!("{:?}", buffer);
    /// # Ok(())
    /// # }
    /// ```
    fn read_until(&mut self, byte: u8, buf: &mut Vec<u8>) -> Result<usize> {
        read_until(self, byte, buf)
    }

    /// Read all bytes until a newline (the 0xA byte) is reached, and append
    /// them to the provided buffer.
    ///
    /// This function will read bytes from the underlying stream until the
    /// newline delimiter (the 0xA byte) or EOF is found. Once found, all bytes
    /// up to, and including, the delimiter (if found) will be appended to
    /// `buf`.
    ///
    /// If this reader is currently at EOF then this function will not modify
    /// `buf` and will return `Ok(n)` where `n` is the number of bytes which
    /// were read.
    ///
    /// # Errors
    ///
    /// This function has the same error semantics as `read_until` and will also
    /// return an error if the read bytes are not valid UTF-8. If an I/O error
    /// is encountered then `buf` may contain some bytes already read in the
    /// event that all data read so far was valid UTF-8.
    ///
    /// # Examples
    ///
    /// A locked standard input implements `BufRead`. In this example, we'll
    /// read all of the lines from standard input. If we were to do this in
    /// an actual project, the [`lines()`][lines] method would be easier, of
    /// course.
    ///
    /// [lines]: #method.lines
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    ///
    /// let stdin = io::stdin();
    /// let mut stdin = stdin.lock();
    /// let mut buffer = String::new();
    ///
    /// while stdin.read_line(&mut buffer).unwrap() > 0 {
    ///     // work with buffer
    ///     println!("{:?}", buffer);
    ///
    ///     buffer.clear();
    /// }
    /// ```
    fn read_line(&mut self, buf: &mut String) -> Result<usize> {
        // Note that we are not calling the `.read_until` method here, but
        // rather our hardcoded implementation. For more details as to why, see
        // the comments in `read_to_end`.
        append_to_string(buf, |b| read_until(self, b'\n', b))
    }

    /// Returns an iterator over the contents of this reader split on the byte
    /// `byte`.
    ///
    /// The iterator returned from this function will return instances of
    /// `io::Result<Vec<u8>>`. Each vector returned will *not* have the
    /// delimiter byte at the end.
    ///
    /// This function will yield errors whenever `read_until` would have also
    /// yielded an error.
    ///
    /// # Examples
    ///
    /// A locked standard input implements `BufRead`. In this example, we'll
    /// read some input from standard input, splitting on commas.
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    ///
    /// let stdin = io::stdin();
    ///
    /// for content in stdin.lock().split(b',') {
    ///     println!("{:?}", content.unwrap());
    /// }
    /// ```
    fn split(self, byte: u8) -> Split<Self> where Self: Sized {
        Split { buf: self, delim: byte }
    }

    /// Returns an iterator over the lines of this reader.
    ///
    /// The iterator returned from this function will yield instances of
    /// `io::Result<String>`. Each string returned will *not* have a newline
    /// byte (the 0xA byte) or CRLF (0xD, 0xA bytes) at the end.
    ///
    /// # Examples
    ///
    /// A locked standard input implements `BufRead`:
    ///
    /// ```
    /// use std::io;
    /// use std::io::prelude::*;
    ///
    /// let stdin = io::stdin();
    ///
    /// for line in stdin.lock().lines() {
    ///     println!("{}", line.unwrap());
    /// }
    /// ```
    fn lines(self) -> Lines<Self> where Self: Sized {
        Lines { buf: self }
    }
}

/// Adaptor to chain together two readers.
///
/// This struct is generally created by calling [`chain()`][chain] on a reader.
/// Please see the documentation of `chain()` for more details.
///
/// [chain]: trait.Read.html#method.chain
pub struct Chain<T, U> {
    first: T,
    second: U,
    done_first: bool,
}

impl<T: Read, U: Read> Read for Chain<T, U> {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        if !self.done_first {
            match self.first.read(buf)? {
                0 => { self.done_first = true; }
                n => return Ok(n),
            }
        }
        self.second.read(buf)
    }
}


impl<T: BufRead, U: BufRead> BufRead for Chain<T, U> {
    fn fill_buf(&mut self) -> Result<&[u8]> {
        if !self.done_first {
            match self.first.fill_buf()? {
                buf if buf.len() == 0 => { self.done_first = true; }
                buf => return Ok(buf),
            }
        }
        self.second.fill_buf()
    }

    fn consume(&mut self, amt: usize) {
        if !self.done_first {
            self.first.consume(amt)
        } else {
            self.second.consume(amt)
        }
    }
}

/// Reader adaptor which limits the bytes read from an underlying reader.
///
/// This struct is generally created by calling [`take()`][take] on a reader.
/// Please see the documentation of `take()` for more details.
///
/// [take]: trait.Read.html#method.take
pub struct Take<T> {
    inner: T,
    limit: u64,
}

impl<T> Take<T> {
    /// Returns the number of bytes that can be read before this instance will
    /// return EOF.
    ///
    /// # Note
    ///
    /// This instance may reach EOF after reading fewer bytes than indicated by
    /// this method if the underlying `Read` instance reaches EOF.
    pub fn limit(&self) -> u64 { self.limit }
}

impl<T: Read> Read for Take<T> {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        // Don't call into inner reader at all at EOF because it may still block
        if self.limit == 0 {
            return Ok(0);
        }

        let max = cmp::min(buf.len() as u64, self.limit) as usize;
        let n = self.inner.read(&mut buf[..max])?;
        self.limit -= n as u64;
        Ok(n)
    }
}


impl<T: BufRead> BufRead for Take<T> {
    fn fill_buf(&mut self) -> Result<&[u8]> {
        // Don't call into inner reader at all at EOF because it may still block
        if self.limit == 0 {
            return Ok(&[]);
        }

        let buf = self.inner.fill_buf()?;
        let cap = cmp::min(buf.len() as u64, self.limit) as usize;
        Ok(&buf[..cap])
    }

    fn consume(&mut self, amt: usize) {
        // Don't let callers reset the limit by passing an overlarge value
        let amt = cmp::min(amt as u64, self.limit) as usize;
        self.limit -= amt as u64;
        self.inner.consume(amt);
    }
}

/// An iterator over `u8` values of a reader.
///
/// This struct is generally created by calling [`bytes()`][bytes] on a reader.
/// Please see the documentation of `bytes()` for more details.
///
/// [bytes]: trait.Read.html#method.bytes
pub struct Bytes<R> {
    inner: R,
}

impl<R: Read> Iterator for Bytes<R> {
    type Item = Result<u8>;

    fn next(&mut self) -> Option<Result<u8>> {
        let mut buf = [0];
        match self.inner.read(&mut buf) {
            Ok(0) => None,
            Ok(..) => Some(Ok(buf[0])),
            Err(e) => Some(Err(e)),
        }
    }
}

/// An iterator over the `char`s of a reader.
///
/// This struct is generally created by calling [`chars()`][chars] on a reader.
/// Please see the documentation of `chars()` for more details.
///
/// [chars]: trait.Read.html#method.chars
pub struct Chars<R> {
    inner: R,
}

/// An enumeration of possible errors that can be generated from the `Chars`
/// adapter.
#[derive(Debug)]
pub enum CharsError {
    /// Variant representing that the underlying stream was read successfully
    /// but it did not contain valid utf8 data.
    NotUtf8,

    /// Variant representing that an I/O error occurred.
    Other(Error),
}

impl<R: Read> Iterator for Chars<R> {
    type Item = result::Result<char, CharsError>;

    fn next(&mut self) -> Option<result::Result<char, CharsError>> {
        let mut buf = [0];
        let first_byte = match self.inner.read(&mut buf) {
            Ok(0) => return None,
            Ok(..) => buf[0],
            Err(e) => return Some(Err(CharsError::Other(e))),
        };
        let width = ::core::str::utf8_char_width(first_byte);
        if width == 1 { return Some(Ok(first_byte as char)) }
        if width == 0 { return Some(Err(CharsError::NotUtf8)) }
        let mut buf = [first_byte, 0, 0, 0];
        {
            let mut start = 1;
            while start < width {
                match self.inner.read(&mut buf[start..width]) {
                    Ok(0) => return Some(Err(CharsError::NotUtf8)),
                    Ok(n) => start += n,
                    Err(e) => return Some(Err(CharsError::Other(e))),
                }
            }
        }
        Some(match str::from_utf8(&buf[..width]).ok() {
            Some(s) => Ok(s.chars().next().unwrap()),
            None => Err(CharsError::NotUtf8),
        })
    }
}

impl fmt::Display for CharsError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            CharsError::NotUtf8 => {
                "byte stream did not contain valid utf8".fmt(f)
            }
            CharsError::Other(ref e) => e.fmt(f),
        }
    }
}

/// An iterator over the contents of an instance of `BufRead` split on a
/// particular byte.
///
/// This struct is generally created by calling [`split()`][split] on a
/// `BufRead`. Please see the documentation of `split()` for more details.
///
/// [split]: trait.BufRead.html#method.split

pub struct Split<B> {
    buf: B,
    delim: u8,
}


impl<B: BufRead> Iterator for Split<B> {
    type Item = Result<Vec<u8>>;

    fn next(&mut self) -> Option<Result<Vec<u8>>> {
        let mut buf = Vec::new();
        match self.buf.read_until(self.delim, &mut buf) {
            Ok(0) => None,
            Ok(_n) => {
                if buf[buf.len() - 1] == self.delim {
                    buf.pop();
                }
                Some(Ok(buf))
            }
            Err(e) => Some(Err(e))
        }
    }
}

/// An iterator over the lines of an instance of `BufRead`.
///
/// This struct is generally created by calling [`lines()`][lines] on a
/// `BufRead`. Please see the documentation of `lines()` for more details.
///
/// [lines]: trait.BufRead.html#method.lines

pub struct Lines<B> {
    buf: B,
}


impl<B: BufRead> Iterator for Lines<B> {
    type Item = Result<String>;

    fn next(&mut self) -> Option<Result<String>> {
        let mut buf = String::new();
        match self.buf.read_line(&mut buf) {
            Ok(0) => None,
            Ok(_n) => {
                if buf.ends_with("\n") {
                    buf.pop();
                    if buf.ends_with("\r") {
                        buf.pop();
                    }
                }
                Some(Ok(buf))
            }
            Err(e) => Some(Err(e))
        }
    }
}

#[cfg(test)]
mod tests {
    use prelude::v1::*;
    use io::prelude::*;
    use io;
    use super::Cursor;
    use test;
    use super::repeat;

    #[test]
    fn read_until() {
        let mut buf = Cursor::new(&b"12"[..]);
        let mut v = Vec::new();
        assert_eq!(buf.read_until(b'3', &mut v).unwrap(), 2);
        assert_eq!(v, b"12");

        let mut buf = Cursor::new(&b"1233"[..]);
        let mut v = Vec::new();
        assert_eq!(buf.read_until(b'3', &mut v).unwrap(), 3);
        assert_eq!(v, b"123");
        v.truncate(0);
        assert_eq!(buf.read_until(b'3', &mut v).unwrap(), 1);
        assert_eq!(v, b"3");
        v.truncate(0);
        assert_eq!(buf.read_until(b'3', &mut v).unwrap(), 0);
        assert_eq!(v, []);
    }

    #[test]
    fn split() {
        let buf = Cursor::new(&b"12"[..]);
        let mut s = buf.split(b'3');
        assert_eq!(s.next().unwrap().unwrap(), vec![b'1', b'2']);
        assert!(s.next().is_none());

        let buf = Cursor::new(&b"1233"[..]);
        let mut s = buf.split(b'3');
        assert_eq!(s.next().unwrap().unwrap(), vec![b'1', b'2']);
        assert_eq!(s.next().unwrap().unwrap(), vec![]);
        assert!(s.next().is_none());
    }

    #[test]
    fn read_line() {
        let mut buf = Cursor::new(&b"12"[..]);
        let mut v = String::new();
        assert_eq!(buf.read_line(&mut v).unwrap(), 2);
        assert_eq!(v, "12");

        let mut buf = Cursor::new(&b"12\n\n"[..]);
        let mut v = String::new();
        assert_eq!(buf.read_line(&mut v).unwrap(), 3);
        assert_eq!(v, "12\n");
        v.truncate(0);
        assert_eq!(buf.read_line(&mut v).unwrap(), 1);
        assert_eq!(v, "\n");
        v.truncate(0);
        assert_eq!(buf.read_line(&mut v).unwrap(), 0);
        assert_eq!(v, "");
    }

    #[test]
    fn lines() {
        let buf = Cursor::new(&b"12\r"[..]);
        let mut s = buf.lines();
        assert_eq!(s.next().unwrap().unwrap(), "12\r".to_string());
        assert!(s.next().is_none());

        let buf = Cursor::new(&b"12\r\n\n"[..]);
        let mut s = buf.lines();
        assert_eq!(s.next().unwrap().unwrap(), "12".to_string());
        assert_eq!(s.next().unwrap().unwrap(), "".to_string());
        assert!(s.next().is_none());
    }

    #[test]
    fn read_to_end() {
        let mut c = Cursor::new(&b""[..]);
        let mut v = Vec::new();
        assert_eq!(c.read_to_end(&mut v).unwrap(), 0);
        assert_eq!(v, []);

        let mut c = Cursor::new(&b"1"[..]);
        let mut v = Vec::new();
        assert_eq!(c.read_to_end(&mut v).unwrap(), 1);
        assert_eq!(v, b"1");

        let cap = 1024 * 1024;
        let data = (0..cap).map(|i| (i / 3) as u8).collect::<Vec<_>>();
        let mut v = Vec::new();
        let (a, b) = data.split_at(data.len() / 2);
        assert_eq!(Cursor::new(a).read_to_end(&mut v).unwrap(), a.len());
        assert_eq!(Cursor::new(b).read_to_end(&mut v).unwrap(), b.len());
        assert_eq!(v, data);
    }

    #[test]
    fn read_to_string() {
        let mut c = Cursor::new(&b""[..]);
        let mut v = String::new();
        assert_eq!(c.read_to_string(&mut v).unwrap(), 0);
        assert_eq!(v, "");

        let mut c = Cursor::new(&b"1"[..]);
        let mut v = String::new();
        assert_eq!(c.read_to_string(&mut v).unwrap(), 1);
        assert_eq!(v, "1");

        let mut c = Cursor::new(&b"\xff"[..]);
        let mut v = String::new();
        assert!(c.read_to_string(&mut v).is_err());
    }

    #[test]
    fn read_exact() {
        let mut buf = [0; 4];

        let mut c = Cursor::new(&b""[..]);
        assert_eq!(c.read_exact(&mut buf).unwrap_err().kind(),
                   io::ErrorKind::UnexpectedEof);

        let mut c = Cursor::new(&b"123"[..]).chain(Cursor::new(&b"456789"[..]));
        c.read_exact(&mut buf).unwrap();
        assert_eq!(&buf, b"1234");
        c.read_exact(&mut buf).unwrap();
        assert_eq!(&buf, b"5678");
        assert_eq!(c.read_exact(&mut buf).unwrap_err().kind(),
                   io::ErrorKind::UnexpectedEof);
    }

    #[test]
    fn read_exact_slice() {
        let mut buf = [0; 4];

        let mut c = &b""[..];
        assert_eq!(c.read_exact(&mut buf).unwrap_err().kind(),
                   io::ErrorKind::UnexpectedEof);

        let mut c = &b"123"[..];
        assert_eq!(c.read_exact(&mut buf).unwrap_err().kind(),
                   io::ErrorKind::UnexpectedEof);
        // make sure the optimized (early returning) method is being used
        assert_eq!(&buf, &[0; 4]);

        let mut c = &b"1234"[..];
        c.read_exact(&mut buf).unwrap();
        assert_eq!(&buf, b"1234");

        let mut c = &b"56789"[..];
        c.read_exact(&mut buf).unwrap();
        assert_eq!(&buf, b"5678");
        assert_eq!(c, b"9");
    }

    #[test]
    fn take_eof() {
        struct R;

        impl Read for R {
            fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
                Err(io::Error::new(io::ErrorKind::Other, ""))
            }
        }
        impl BufRead for R {
            fn fill_buf(&mut self) -> io::Result<&[u8]> {
                Err(io::Error::new(io::ErrorKind::Other, ""))
            }
            fn consume(&mut self, _amt: usize) { }
        }

        let mut buf = [0; 1];
        assert_eq!(0, R.take(0).read(&mut buf).unwrap());
        assert_eq!(b"", R.take(0).fill_buf().unwrap());
    }

    fn cmp_bufread<Br1: BufRead, Br2: BufRead>(mut br1: Br1, mut br2: Br2, exp: &[u8]) {
        let mut cat = Vec::new();
        loop {
            let consume = {
                let buf1 = br1.fill_buf().unwrap();
                let buf2 = br2.fill_buf().unwrap();
                let minlen = if buf1.len() < buf2.len() { buf1.len() } else { buf2.len() };
                assert_eq!(buf1[..minlen], buf2[..minlen]);
                cat.extend_from_slice(&buf1[..minlen]);
                minlen
            };
            if consume == 0 {
                break;
            }
            br1.consume(consume);
            br2.consume(consume);
        }
        assert_eq!(br1.fill_buf().unwrap().len(), 0);
        assert_eq!(br2.fill_buf().unwrap().len(), 0);
        assert_eq!(&cat[..], &exp[..])
    }

    #[test]
    fn chain_bufread() {
        let testdata = b"ABCDEFGHIJKL";
        let chain1 = (&testdata[..3]).chain(&testdata[3..6])
                                     .chain(&testdata[6..9])
                                     .chain(&testdata[9..]);
        let chain2 = (&testdata[..4]).chain(&testdata[4..8])
                                     .chain(&testdata[8..]);
        cmp_bufread(chain1, chain2, &testdata[..]);
    }

    #[bench]
    fn bench_read_to_end(b: &mut test::Bencher) {
        b.iter(|| {
            let mut lr = repeat(1).take(10000000);
            let mut vec = Vec::with_capacity(1024);
            super::read_to_end(&mut lr, &mut vec)
        });
    }
}
