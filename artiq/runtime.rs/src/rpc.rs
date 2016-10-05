use std::io::{self, Read, Write};
use proto::{write_u8, write_bytes};
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

fn send_value(writer: &mut Write, tag: Tag, data: &mut *const ()) -> io::Result<()> {
    match tag {
        Tag::None => write_u8(writer, b'n'),
        _ => unreachable!()
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
            try!(send_value(writer, arg_tag, &mut data));
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

    #[derive(Debug)]
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
                    Tag::Tuple(self.skip(count), count)
                }
                b'l' => Tag::List(self.skip(1)),
                b'a' => Tag::Array(self.skip(1)),
                b'r' => Tag::Range(self.skip(1)),
                b'k' => Tag::Keyword(self.skip(1)),
                b'O' => Tag::Object,
                _    => unreachable!()
            })
        }

        fn skip(&mut self, count: u8) -> TagIterator<'a> {
            let origin = self.clone();
            for _ in 0..count {
                self.next().expect("truncated tag");
            }
            origin
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
                        for i in 0..cnt {
                            try!(it.fmt(f));
                            if i != cnt - 1 { try!(write!(f, ", ")) }
                        }
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
