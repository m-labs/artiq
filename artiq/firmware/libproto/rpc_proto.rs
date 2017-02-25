use std::io::{self, Read, Write};
use std::str;
use cslice::{CSlice, CMutSlice};
use io::*;
use self::tag::{Tag, TagIterator, split_tag};

unsafe fn recv_value(reader: &mut Read, tag: Tag, data: &mut *mut (),
                     alloc: &Fn(usize) -> io::Result<*mut ()>) -> io::Result<()> {
    macro_rules! consume_value {
        ($ty:ty, |$ptr:ident| $map:expr) => ({
            let ptr = (*data) as *mut $ty;
            *data = ptr.offset(1) as *mut ();
            (|$ptr: *mut $ty| $map)(ptr)
        })
    }

    match tag {
        Tag::None => Ok(()),
        Tag::Bool =>
            consume_value!(u8, |ptr| {
                *ptr = read_u8(reader)?; Ok(())
            }),
        Tag::Int32 =>
            consume_value!(u32, |ptr| {
                *ptr = read_u32(reader)?; Ok(())
            }),
        Tag::Int64 | Tag::Float64 =>
            consume_value!(u64, |ptr| {
                *ptr = read_u64(reader)?; Ok(())
            }),
        Tag::String => {
            consume_value!(CMutSlice<u8>, |ptr| {
                let length = read_u32(reader)? as usize;
                *ptr = CMutSlice::new(alloc(length)? as *mut u8, length);
                reader.read_exact((*ptr).as_mut())?;
                Ok(())
            })
        }
        Tag::Tuple(it, arity) => {
            let mut it = it.clone();
            for _ in 0..arity {
                let tag = it.next().expect("truncated tag");
                recv_value(reader, tag, data, alloc)?
            }
            Ok(())
        }
        Tag::List(it) | Tag::Array(it) => {
            struct List { elements: *mut (), length: u32 };
            consume_value!(List, |ptr| {
                (*ptr).length = read_u32(reader)?;

                let tag = it.clone().next().expect("truncated tag");
                (*ptr).elements = alloc(tag.size() * (*ptr).length as usize)?;

                let mut data = (*ptr).elements;
                for _ in 0..(*ptr).length as usize {
                    recv_value(reader, tag, &mut data, alloc)?
                }
                Ok(())
            })
        }
        Tag::Range(it) => {
            let tag = it.clone().next().expect("truncated tag");
            recv_value(reader, tag, data, alloc)?;
            recv_value(reader, tag, data, alloc)?;
            recv_value(reader, tag, data, alloc)?;
            Ok(())
        }
        Tag::Keyword(_) => unreachable!(),
        Tag::Object => unreachable!()
    }
}

pub fn recv_return(reader: &mut Read, tag_bytes: &[u8], data: *mut (),
                   alloc: &Fn(usize) -> io::Result<*mut ()>) -> io::Result<()> {
    let mut it = TagIterator::new(tag_bytes);
    #[cfg(feature = "log")]
    trace!("recv ...->{}", it);

    let tag = it.next().expect("truncated tag");
    let mut data = data;
    unsafe { recv_value(reader, tag, &mut data, alloc)? };

    Ok(())
}

unsafe fn send_value(writer: &mut Write, tag: Tag, data: &mut *const ()) -> io::Result<()> {
    macro_rules! consume_value {
        ($ty:ty, |$ptr:ident| $map:expr) => ({
            let ptr = (*data) as *const $ty;
            *data = ptr.offset(1) as *const ();
            (|$ptr: *const $ty| $map)(ptr)
        })
    }

    write_u8(writer, tag.as_u8())?;
    match tag {
        Tag::None => Ok(()),
        Tag::Bool =>
            consume_value!(u8, |ptr|
                write_u8(writer, *ptr)),
        Tag::Int32 =>
            consume_value!(u32, |ptr|
                write_u32(writer, *ptr)),
        Tag::Int64 | Tag::Float64 =>
            consume_value!(u64, |ptr|
                write_u64(writer, *ptr)),
        Tag::String =>
            consume_value!(CSlice<u8>, |ptr|
                write_string(writer, str::from_utf8((*ptr).as_ref()).unwrap())),
        Tag::Tuple(it, arity) => {
            let mut it = it.clone();
            write_u8(writer, arity)?;
            for _ in 0..arity {
                let tag = it.next().expect("truncated tag");
                send_value(writer, tag, data)?
            }
            Ok(())
        }
        Tag::List(it) | Tag::Array(it) => {
            struct List { elements: *const (), length: u32 };
            consume_value!(List, |ptr| {
                write_u32(writer, (*ptr).length)?;
                let tag = it.clone().next().expect("truncated tag");
                let mut data = (*ptr).elements;
                for _ in 0..(*ptr).length as usize {
                    send_value(writer, tag, &mut data)?;
                }
                Ok(())
            })
        }
        Tag::Range(it) => {
            let tag = it.clone().next().expect("truncated tag");
            send_value(writer, tag, data)?;
            send_value(writer, tag, data)?;
            send_value(writer, tag, data)?;
            Ok(())
        }
        Tag::Keyword(it) => {
            struct Keyword<'a> { name: CSlice<'a, u8>, contents: () };
            consume_value!(Keyword, |ptr| {
                write_string(writer, str::from_utf8((*ptr).name.as_ref()).unwrap())?;
                let tag = it.clone().next().expect("truncated tag");
                let mut data = &(*ptr).contents as *const ();
                send_value(writer, tag, &mut data)
            })
            // Tag::Keyword never appears in composite types, so we don't have
            // to accurately advance data.
        }
        Tag::Object => {
            struct Object { id: u32 };
            consume_value!(*const Object, |ptr|
                write_u32(writer, (**ptr).id))
        }
    }
}

pub fn send_args(writer: &mut Write, service: u32, tag_bytes: &[u8],
                 data: *const *const ()) -> io::Result<()> {
    let (arg_tags_bytes, return_tag_bytes) = split_tag(tag_bytes);

    let mut args_it = TagIterator::new(arg_tags_bytes);
    #[cfg(feature = "log")]
    {
        let return_it = TagIterator::new(return_tag_bytes);
        trace!("send<{}>({})->{}", service, args_it, return_it);
    }

    write_u32(writer, service)?;
    for index in 0.. {
        if let Some(arg_tag) = args_it.next() {
            let mut data = unsafe { *data.offset(index) };
            unsafe { send_value(writer, arg_tag, &mut data)? };
        } else {
            break
        }
    }
    write_u8(writer, 0)?;
    write_bytes(writer, return_tag_bytes)?;

    Ok(())
}

mod tag {
    use core::fmt;

    pub fn split_tag(tag_bytes: &[u8]) -> (&[u8], &[u8]) {
        let tag_separator =
            tag_bytes.iter()
                     .position(|&b| b == b':')
                     .expect("tag without a return separator");
        let (arg_tags_bytes, rest) = tag_bytes.split_at(tag_separator);
        let return_tag_bytes = &rest[1..];
        (arg_tags_bytes, return_tag_bytes)
    }

    #[derive(Debug, Clone, Copy)]
    pub enum Tag<'a> {
        None,
        Bool,
        Int32,
        Int64,
        Float64,
        String,
        Tuple(TagIterator<'a>, u8),
        List(TagIterator<'a>),
        Array(TagIterator<'a>),
        Range(TagIterator<'a>),
        Keyword(TagIterator<'a>),
        Object
    }

    impl<'a> Tag<'a> {
        pub fn as_u8(self) -> u8 {
            match self {
                Tag::None => b'n',
                Tag::Bool => b'b',
                Tag::Int32 => b'i',
                Tag::Int64 => b'I',
                Tag::Float64 => b'f',
                Tag::String => b's',
                Tag::Tuple(_, _) => b't',
                Tag::List(_) => b'l',
                Tag::Array(_) => b'a',
                Tag::Range(_) => b'r',
                Tag::Keyword(_) => b'k',
                Tag::Object => b'O',
            }
        }

        pub fn size(self) -> usize {
            match self {
                Tag::None => 0,
                Tag::Bool => 1,
                Tag::Int32 => 4,
                Tag::Int64 => 8,
                Tag::Float64 => 8,
                Tag::String => 4,
                Tag::Tuple(it, arity) => {
                    let mut size = 0;
                    for _ in 0..arity {
                        let tag = it.clone().next().expect("truncated tag");
                        size += tag.size();
                    }
                    size
                }
                Tag::List(_) => 8,
                Tag::Array(_) => 8,
                Tag::Range(it) => {
                    let tag = it.clone().next().expect("truncated tag");
                    tag.size() * 3
                }
                Tag::Keyword(_) => unreachable!(),
                Tag::Object => unreachable!(),
            }
        }
    }

    #[derive(Debug, Clone, Copy)]
    pub struct TagIterator<'a> {
        data: &'a [u8]
    }

    impl<'a> TagIterator<'a> {
        pub fn new(data: &'a [u8]) -> TagIterator<'a> {
            TagIterator { data: data }
        }

        pub fn next(&mut self) -> Option<Tag<'a>> {
            if self.data.len() == 0 {
                return None
            }

            let tag_byte = self.data[0];
            self.data = &self.data[1..];
            Some(match tag_byte {
                b'n' => Tag::None,
                b'b' => Tag::Bool,
                b'i' => Tag::Int32,
                b'I' => Tag::Int64,
                b'f' => Tag::Float64,
                b's' => Tag::String,
                b't' => {
                    let count = self.data[0];
                    self.data = &self.data[1..];
                    Tag::Tuple(self.sub(count), count)
                }
                b'l' => Tag::List(self.sub(1)),
                b'a' => Tag::Array(self.sub(1)),
                b'r' => Tag::Range(self.sub(1)),
                b'k' => Tag::Keyword(self.sub(1)),
                b'O' => Tag::Object,
                _    => unreachable!()
            })
        }

        fn sub(&mut self, count: u8) -> TagIterator<'a> {
            let data = self.data;
            for _ in 0..count {
                self.next().expect("truncated tag");
            }
            TagIterator { data: &data[..(data.len() - self.data.len())] }
        }
    }

    impl<'a> fmt::Display for TagIterator<'a> {
        fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
            let mut it = self.clone();
            let mut first = true;
            while let Some(tag) = it.next() {
                if first {
                    first = false
                } else {
                    write!(f, ", ")?
                }

                match tag {
                    Tag::None =>
                        write!(f, "None")?,
                    Tag::Bool =>
                        write!(f, "Bool")?,
                    Tag::Int32 =>
                        write!(f, "Int32")?,
                    Tag::Int64 =>
                        write!(f, "Int64")?,
                    Tag::Float64 =>
                        write!(f, "Float64")?,
                    Tag::String =>
                        write!(f, "String")?,
                    Tag::Tuple(it, _) => {
                        write!(f, "Tuple(")?;
                        it.fmt(f)?;
                        write!(f, ")")?;
                    }
                    Tag::List(it) => {
                        write!(f, "List(")?;
                        it.fmt(f)?;
                        write!(f, ")")?;
                    }
                    Tag::Array(it) => {
                        write!(f, "Array(")?;
                        it.fmt(f)?;
                        write!(f, ")")?;
                    }
                    Tag::Range(it) => {
                        write!(f, "Range(")?;
                        it.fmt(f)?;
                        write!(f, ")")?;
                    }
                    Tag::Keyword(it) => {
                        write!(f, "Keyword(")?;
                        it.fmt(f)?;
                        write!(f, ")")?;
                    }
                    Tag::Object =>
                        write!(f, "Object")?,
                }
            }

            Ok(())
        }
    }
}
