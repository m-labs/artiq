use core::{fmt, str};

use byteorder::{ByteOrder, NetworkEndian};
use cslice::CMutSlice;
use io::{Cursor, Write};
use proto_artiq::drtioaux_proto::CXP_PAYLOAD_MAX_SIZE;

use crate::{recv, send, Message};

const URL_BUF_SIZE: usize = 256;
const ROI_MAX_SIZE: usize = 4096;

type URLBuffer = [u8; URL_BUF_SIZE];
// Oversize the buffer to make sure the formatted message fits
type ErrMsgBuffer = [u8; URL_BUF_SIZE * 2];

#[repr(C)]
pub struct ROIViewerFrame {
    width: i32,
    height: i32,
    pixel_width: i32,
}

enum Error {
    BufferSizeTooSmall(usize, usize),
    ROISizeTooBig(usize, usize),
    InvalidLocalUrl(URLBuffer),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            &Error::BufferSizeTooSmall(required_size, buffer_size) => {
                write!(
                    f,
                    "BufferSizeTooSmall - The required size is {} bytes but the buffer size is {} bytes",
                    required_size, buffer_size
                )
            }
            &Error::ROISizeTooBig(width, height) => {
                write!(
                    f,
                    "ROISizeTooBig - The maximum ROIViewer height and total size are {} and {} pixels respectively \
                     but the ROI is set to {} ({}x{}) pixels",
                    ROI_MAX_SIZE / 4,
                    ROI_MAX_SIZE,
                    width * height,
                    width,
                    height
                )
            }
            &Error::InvalidLocalUrl(buf) => {
                write!(
                    f,
                    "InvalidLocalUrl - Cannot download xml file locally from {}",
                    str::from_utf8(&buf).unwrap()
                )
            }
        }
    }
}

impl From<Error> for ErrMsgBuffer {
    fn from(value: Error) -> ErrMsgBuffer {
        struct FmtWriter<'a> {
            cursor: Cursor<&'a mut [u8]>,
        }
        impl fmt::Write for FmtWriter<'_> {
            fn write_str(&mut self, s: &str) -> fmt::Result {
                match self.cursor.write_all(s.as_bytes()) {
                    Ok(()) => Ok(()),
                    Err(_) => Err(fmt::Error),
                }
            }
        }

        let mut buffer: ErrMsgBuffer = [0; URL_BUF_SIZE * 2];
        let cursor = Cursor::new(&mut buffer[..]);
        if let Err(e) = fmt::write(&mut FmtWriter { cursor }, format_args!("{}", value)) {
            panic!("Failed to write error buffer {:?}", e);
        };
        buffer
    }
}

fn read_xml_url<F>(read_bytes_f: F, buffer: &mut [u8]) -> Result<(), Error>
where
    F: Fn(u32, &mut [u8]),
{
    let mut bytes: [u8; 4] = [0; 4];
    read_bytes_f(0x0018, &mut bytes);
    let mut addr = NetworkEndian::read_u32(&bytes);
    let mut writer = Cursor::new(buffer);

    // Strings stored in the bootstrap and manufacturer-specific registers space shall be NULL-terminated, encoded ASCII - Section 12.3.1 (CXP-001-2021)
    // String length is not known during runtime, grabber must read 4 bytes at a time until NULL-terminated
    loop {
        let mut bytes: [u8; 4] = [0; 4];
        read_bytes_f(addr, &mut bytes);
        addr += 4;

        for b in bytes {
            if b == 0 {
                // ASCII NULL
                return Ok(());
            } else {
                let _ = writer.write(&[b]);
            }
        }
    }
}

fn read_xml_file<F>(
    buffer: &mut [i32],
    read_bytes_f: F,
    max_read_length: usize,
) -> Result<u32, Error>
where
    F: Fn(u32, &mut [u8]),
{
    let mut url_buffer: URLBuffer = [0; URL_BUF_SIZE];
    read_xml_url(&read_bytes_f, &mut url_buffer)?;

    // url example - Section 13.2.3 (CXP-001-2021)
    // Available on camera - "Local:MyFilename.zip;B8000;33A?SchemaVersion=1.0.0"
    // => ZIP file starting at address 0xB8000 in the Device with a length of 0x33A bytes
    //
    // Available online - "Web:http://www.example.com/xml/MyFilename.xml"
    // => xml is available at http://www.example.com/xml/MyFilename.xml

    // UTF-8 is compatible with ASCII encoding
    let url = str::from_utf8(&url_buffer).unwrap();
    let mut splitter = url.split(|c| c == ':' || c == ';' || c == '?' || c == '\0');
    let scheme = splitter.next().unwrap();
    if !scheme.eq_ignore_ascii_case("local") {
        return Err(Error::InvalidLocalUrl(url_buffer));
    }

    let (base_addr, size);
    match (splitter.next(), splitter.next(), splitter.next()) {
        (Some(name), Some(addr_str), Some(size_str)) => {
            size = u32::from_str_radix(size_str, 16)
                .map_err(|_| Error::InvalidLocalUrl(url_buffer))? as usize;

            if buffer.len() * 4 < size {
                return Err(Error::BufferSizeTooSmall(size as usize, buffer.len() * 4));
            };

            base_addr = u32::from_str_radix(addr_str, 16)
                .map_err(|_| Error::InvalidLocalUrl(url_buffer))?;

            println!("downloading xml file {} with {} bytes...", name, size);
        }
        _ => return Err(Error::InvalidLocalUrl(url_buffer)),
    }

    let mut addr = base_addr;
    let mut bytesleft = size;
    let mut bytes: [u8; CXP_PAYLOAD_MAX_SIZE] = [0; CXP_PAYLOAD_MAX_SIZE];
    let mut padding = 0;

    while bytesleft > 0 {
        let read_len = max_read_length.min(bytesleft);
        read_bytes_f(addr, &mut bytes[..read_len]);

        // pad to 32 bit boundary
        padding = (4 - (read_len % 4)) % 4;

        let offset = (size - bytesleft) / 4;
        NetworkEndian::read_i32_into(
            &bytes[..(read_len + padding)],
            &mut buffer[offset..offset + (read_len + padding) / 4],
        );

        addr += read_len as u32;
        bytesleft -= read_len;
    }
    println!("download successful");

    Ok(((size + padding) / 4) as u32)
}

fn drtio_read_bytes(dest: u8, addr: u32, bytes: &mut [u8]) {
    let length = bytes.len() as u16;
    if length as usize > CXP_PAYLOAD_MAX_SIZE {
        panic!("CXPReadRequest length is too long")
    }

    send(&Message::CXPReadRequest {
        destination: dest,
        address: addr,
        length,
    });
    recv(|result| match result {
        Message::CXPReadReply { length, data } => {
            bytes.copy_from_slice(&data[..*length as usize]);
        }
        Message::CXPError(err_msg) => raise!("CXPError", err_msg),
        _ => unreachable!(),
    })
}

pub extern "C" fn download_xml_file(dest: i32, buffer: &mut CMutSlice<i32>) -> i32 {
    match dest {
        0 => {
            raise!("CXPError", "CXP Grabber is not available on destination 0");
        }
        _ => match read_xml_file(
            buffer.as_mut_slice(),
            |addr, bytes| drtio_read_bytes(dest as u8, addr, bytes),
            CXP_PAYLOAD_MAX_SIZE,
        ) {
            Ok(size_read) => size_read as i32,
            Err(e) => {
                // use `let` binding to create a longer lived value
                let msg_buf = ErrMsgBuffer::from(e);
                raise!("CXPError", msg_buf);
            }
        },
    }
}

pub extern "C" fn read32(dest: i32, addr: i32) -> i32 {
    match dest {
        0 => {
            raise!("CXPError", "CXP Grabber is not available on destination 0");
        }
        _ => {
            let mut bytes: [u8; 4] = [0; 4];
            drtio_read_bytes(dest as u8, addr as u32, &mut bytes);
            NetworkEndian::read_i32(&bytes)
        }
    }
}

pub extern "C" fn write32(dest: i32, addr: i32, val: i32) {
    match dest {
        0 => {
            raise!("CXPError", "CXP Grabber is not available on destination 0");
        }
        _ => {
            send(&Message::CXPWrite32Request {
                destination: dest as u8,
                address: addr as u32,
                value: val as u32,
            });
            recv(|result| match result {
                Message::CXPWrite32Reply => return,
                Message::CXPError(err_msg) => raise!("CXPError", err_msg),
                _ => unreachable!(),
            })
        }
    }
}

pub extern "C" fn start_roi_viewer(dest: i32, x0: i32, y0: i32, x1: i32, y1: i32) {
    let (width, height) = ((x1 - x0) as usize, (y1 - y0) as usize);
    if width * height > ROI_MAX_SIZE || height > ROI_MAX_SIZE / 4 {
        let msg_buf = ErrMsgBuffer::from(Error::ROISizeTooBig(width, height));
        raise!("CXPError", msg_buf);
    }

    match dest {
        0 => {
            raise!("CXPError", "CXP Grabber is not available on destination 0");
        }
        _ => {
            send(&Message::CXPROIViewerSetupRequest {
                destination: dest as u8,
                x0: x0 as u16,
                y0: y0 as u16,
                x1: x1 as u16,
                y1: y1 as u16,
            });
            recv(|result| match result {
                Message::CXPROIViewerSetupReply => return,
                _ => unreachable!(),
            })
        }
    }
}

pub extern "C" fn download_roi_viewer_frame(
    dest: i32,
    buffer: &mut CMutSlice<i64>,
) -> ROIViewerFrame {
    if buffer.len() * 4 < ROI_MAX_SIZE {
        // each pixel is 16 bits
        let msg_buf = ErrMsgBuffer::from(Error::BufferSizeTooSmall(
            ROI_MAX_SIZE * 2,
            buffer.len() * 8,
        ));
        raise!("CXPError", msg_buf);
    };

    let buf = buffer.as_mut_slice();
    let (width, height, pixel_code);
    match dest {
        0 => {
            raise!("CXPError", "CXP Grabber is not available on destination 0");
        }
        _ => {
            let mut i = 0;
            loop {
                send(&Message::CXPROIViewerDataRequest {
                    destination: dest as u8,
                });
                let frame_data = recv(|result| match result {
                    Message::CXPROIVIewerPixelDataReply { length, data } => {
                        for d in &data[..*length as usize] {
                            buf[i] = *d as i64;
                            i += 1;
                        }
                        None
                    }
                    Message::CXPROIVIewerFrameDataReply {
                        width: w,
                        height: h,
                        pixel_code: p,
                    } => Some((*w, *h, *p)),
                    _ => unreachable!(),
                });
                if let Some((w, h, p)) = frame_data {
                    width = w;
                    height = h;
                    pixel_code = p;
                    break;
                }
            }
        }
    };
    let pixel_width = match pixel_code {
        0x0101 => 8,
        0x0102 => 10,
        0x0103 => 12,
        0x0104 => 14,
        0x0105 => 16,
        _ => raise!("CXPError", "UnsupportedPixelFormat"),
    };
    ROIViewerFrame {
        width: width as i32,
        height: height as i32,
        pixel_width: pixel_width as i32,
    }
}
