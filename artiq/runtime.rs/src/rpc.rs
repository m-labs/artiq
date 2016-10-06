use std::io::{self, Read, Write};
use proto::*;
use self::tag::{Tag, TagIterator, split_tag};

fn recv_value(reader: &mut Read, tag: Tag, data: &mut *const ()) -> io::Result<()> {
    match tag {
        Tag::None => Ok(()),
        _ => unreachable!()
    }
}

pub fn recv_return(reader: &mut Read, tag_bytes: &[u8], data: *const ()) -> io::Result<()> {
    let mut it = TagIterator::new(tag_bytes);
    trace!("recv ...->{}", it);

    let mut data = data;
    try!(recv_value(reader, it.next().expect("RPC without a return value"), &mut data));

    Ok(())
}

pub unsafe fn from_c_str<'a>(ptr: *const u8) -> &'a str {
    use core::{str, slice};
    extern { fn strlen(ptr: *const u8) -> usize; }
    str::from_utf8_unchecked(slice::from_raw_parts(ptr as *const u8, strlen(ptr)))
}

unsafe fn send_value(writer: &mut Write, tag: Tag, data: &mut *const ()) -> io::Result<()> {
    macro_rules! consume_value {
        ($ty:ty, |$ptr:ident| $map:expr) => ({
            let ptr = (*data) as *const $ty;
            *data = ptr.offset(1) as *const ();
            (|$ptr: *const $ty| $map)(ptr)
        })
    }

    try!(write_u8(writer, tag.as_u8()));
    match tag {
        Tag::None => Ok(()),
        Tag::Bool => {
            consume_value!(u8, |ptr|
                write_u8(writer, *ptr))
        }
        Tag::Int32 => {
            consume_value!(u32, |ptr|
                write_u32(writer, *ptr))
        }
        Tag::Int64 => {
            consume_value!(u64, |ptr|
                write_u64(writer, *ptr))
        }
        Tag::Float64 => {
            consume_value!(u64, |ptr|
                write_u64(writer, *ptr))
        }
        Tag::String => {
            consume_value!(*const u8, |ptr|
                write_string(writer, from_c_str(*ptr)))
        }
        Tag::Tuple(it, arity) => {
            let mut it = it.clone();
            try!(write_u8(writer, arity));
            for _ in 0..arity {
                let tag = it.next().expect("truncated tag");
                try!(send_value(writer, tag, data))
            }
            Ok(())
        }
        Tag::List(it) | Tag::Array(it) => {
            struct List { length: u32, elements: *const () };
            consume_value!(List, |ptr| {
                try!(write_u32(writer, (*ptr).length));
                let tag = it.clone().next().expect("truncated tag");
                let mut data = (*ptr).elements;
                for _ in 0..(*ptr).length as usize {
                    try!(send_value(writer, tag, &mut data));
                }
                Ok(())
            })
        }
        Tag::Range(it) => {
            let tag = it.clone().next().expect("truncated tag");
            try!(send_value(writer, tag, data));
            try!(send_value(writer, tag, data));
            try!(send_value(writer, tag, data));
            Ok(())
        }
        Tag::Keyword(it) => {
            struct Keyword { name: *const u8, contents: () };
            consume_value!(Keyword, |ptr| {
                try!(write_string(writer, from_c_str((*ptr).name)));
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

pub fn send_args(writer: &mut Write, tag_bytes: &[u8],
                 data: *const *const ()) -> io::Result<()> {
    let (arg_tags_bytes, return_tag_bytes) = split_tag(tag_bytes);

    let mut args_it = TagIterator::new(arg_tags_bytes);
    let return_it = TagIterator::new(return_tag_bytes);
    trace!("send ({})->{}", args_it, return_it);

    for index in 0.. {
        if let Some(arg_tag) = args_it.next() {
            let mut data = unsafe { *data.offset(index) };
            try!(unsafe { send_value(writer, arg_tag, &mut data) });
        } else {
            break
        }
    }
    try!(write_u8(writer, 0));
    try!(write_bytes(writer, return_tag_bytes));

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
                    try!(write!(f, ", "))
                }

                match tag {
                    Tag::None =>
                        try!(write!(f, "None")),
                    Tag::Bool =>
                        try!(write!(f, "Bool")),
                    Tag::Int32 =>
                        try!(write!(f, "Int32")),
                    Tag::Int64 =>
                        try!(write!(f, "Int64")),
                    Tag::Float64 =>
                        try!(write!(f, "Float64")),
                    Tag::String =>
                        try!(write!(f, "String")),
                    Tag::Tuple(it, cnt) => {
                        try!(write!(f, "Tuple("));
                        try!(it.fmt(f));
                        try!(write!(f, ")"))
                    }
                    Tag::List(it) => {
                        try!(write!(f, "List("));
                        try!(it.fmt(f));
                        try!(write!(f, ")"))
                    }
                    Tag::Array(it) => {
                        try!(write!(f, "Array("));
                        try!(it.fmt(f));
                        try!(write!(f, ")"))
                    }
                    Tag::Range(it) => {
                        try!(write!(f, "Range("));
                        try!(it.fmt(f));
                        try!(write!(f, ")"))
                    }
                    Tag::Keyword(it) => {
                        try!(write!(f, "Keyword("));
                        try!(it.fmt(f));
                        try!(write!(f, ")"))
                    }
                    Tag::Object =>
                        try!(write!(f, "Object"))
                }
            }

            Ok(())
        }
    }
}
