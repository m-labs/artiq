use std::io::{self, Write};
use proto::*;

#[derive(Debug)]
pub struct Header {
    pub sent_bytes: u32,
    pub total_byte_count: u64,
    pub overflow_occurred: bool,
    pub log_channel: u8,
    pub dds_onehot_sel: bool
}

impl Header {
    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        try!(write_u32(writer, self.sent_bytes));
        try!(write_u64(writer, self.total_byte_count));
        try!(write_u8(writer, self.overflow_occurred as u8));
        try!(write_u8(writer, self.log_channel));
        try!(write_u8(writer, self.dds_onehot_sel as u8));
        Ok(())
    }
}
