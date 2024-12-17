use alloc::vec::Vec;
use byteorder::{ByteOrder, NativeEndian};
use crc::crc32;

use routing::{Sliceable, SliceMeta};
use board_artiq::drtioaux;
use board_misoc::{mem, config, spiflash};
use log::LevelFilter;
use logger_artiq::BufferLogger;
use io::{Cursor, ProtoRead, ProtoWrite};
use proto_artiq::drtioaux_proto::SAT_PAYLOAD_MAX_SIZE;


pub fn clear_log() -> Result<(), ()> {
    BufferLogger::with(|logger| {
        let mut buffer = logger.buffer()?;
        Ok(buffer.clear())
    }).map_err(|()| error!("error on clearing log buffer"))
}

pub fn byte_to_level_filter(level_byte: u8) -> Result<LevelFilter, ()> {
    Ok(match level_byte {
        0 => LevelFilter::Off,
        1 => LevelFilter::Error,
        2 => LevelFilter::Warn,
        3 => LevelFilter::Info,
        4 => LevelFilter::Debug,
        5 => LevelFilter::Trace,
        lv => {
            error!("unknown log level: {}", lv);
            return Err(());
        }
    })
}

pub struct Manager {
    config_payload: Cursor<Vec<u8>>,
    image_payload: Cursor<Vec<u8>>,
    last_value: Sliceable,
    last_log: Sliceable,
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            config_payload: Cursor::new(Vec::new()),
            image_payload: Cursor::new(Vec::new()),
            last_value: Sliceable::new(0, Vec::new()),
            last_log: Sliceable::new(0, Vec::new()),
        }
    }

    pub fn fetch_config_value(&mut self, key: &str) -> Result<(), ()> {
        config::read(key, |result| result.map(
            |value| self.last_value = Sliceable::new(0, value.to_vec())
        )).map_err(|_err| warn!("read error: no such key"))
    }

    pub fn log_get_slice(&mut self, data_slice: &mut [u8; SAT_PAYLOAD_MAX_SIZE], consume: bool) -> Result<SliceMeta, ()> {
        // Populate buffer if depleted
        if self.last_log.at_end() {
            BufferLogger::with(|logger| {
                let mut buffer = logger.buffer()?;
                self.last_log = Sliceable::new(0, buffer.extract().as_bytes().to_vec());
                if consume {
                    buffer.clear();
                }
                Ok(())
            }).map_err(|()| error!("error on getting log buffer"))?;
        }

        Ok(self.last_log.get_slice_satellite(data_slice))
    }

    pub fn get_config_value_slice(&mut self, data_slice: &mut [u8; SAT_PAYLOAD_MAX_SIZE]) -> SliceMeta {
        self.last_value.get_slice_satellite(data_slice)
    }

    pub fn add_config_data(&mut self, data: &[u8], data_len: usize) {
        self.config_payload.write_all(&data[..data_len]).unwrap();
    }

    pub fn clear_config_data(&mut self) {
        self.config_payload.get_mut().clear();
        self.config_payload.set_position(0);
    }

    pub fn write_config(&mut self) -> Result<(), drtioaux::Error<!>> {
        let key = match self.config_payload.read_string() {
            Ok(key) => key,
            Err(err) => {
                self.clear_config_data();
                error!("error on reading key: {:?}", err);
                return drtioaux::send(0, &drtioaux::Packet::CoreMgmtReply { succeeded: false });
            }
        };

        let value = self.config_payload.read_bytes().unwrap();

        let succeeded = config::write(&key, &value).map_err(|err| {
            error!("error on writing config: {:?}", err);
        }).is_ok();

        self.clear_config_data();

        drtioaux::send(0, &drtioaux::Packet::CoreMgmtReply { succeeded })
    }

    pub fn allocate_image_buffer(&mut self, image_size: usize) {
        self.image_payload = Cursor::new(Vec::with_capacity(image_size));
    }

    pub fn add_image_data(&mut self, data: &[u8], data_len: usize) {
        self.image_payload.write_all(&data[..data_len]).unwrap();
    }

    pub fn flash_image(&self) {
        let image = &self.image_payload.get_ref()[..];

        let (expected_crc, mut image) = {
            let (image, crc_slice) = image.split_at(image.len() - 4);
            (NativeEndian::read_u32(crc_slice), image)
        };

        let actual_crc = crc32::checksum_ieee(image);

        if actual_crc == expected_crc {
            let bin_origins = [
                ("gateware"  , 0                      ),
                ("bootloader", mem::ROM_BASE          ),
                ("firmware"  , mem::FLASH_BOOT_ADDRESS),
            ];

            for (name, origin) in bin_origins {
                info!("flashing {} binary...", name);
                let size = NativeEndian::read_u32(&image[..4]) as usize;
                image = &image[4..];

                let (bin, remaining) = image.split_at(size);
                image = remaining;

                unsafe { spiflash::flash_binary(origin, bin) };
            }

        } else {
            panic!("CRC failed, images have not been written to flash.\n(actual {:08x}, expected {:08x})", actual_crc, expected_crc);
        }
    }
}
