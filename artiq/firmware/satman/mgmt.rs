use alloc::vec::Vec;
use byteorder::{ByteOrder, NativeEndian};
use crc::crc32;

use routing::{Sliceable, SliceMeta};
use board_artiq::drtioaux;
use board_misoc::{mem, clock, config, csr, spiflash};
use io::{Cursor, ProtoRead, ProtoWrite};
use proto_artiq::drtioaux_proto::SAT_PAYLOAD_MAX_SIZE;


pub struct Manager {
    config_payload: Cursor<Vec<u8>>,
    image_payload: Cursor<Vec<u8>>,
    last_value: Sliceable,
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            config_payload: Cursor::new(Vec::new()),
            image_payload: Cursor::new(Vec::new()),
            last_value: Sliceable::new(0, Vec::new()),
        }
    }

    pub fn fetch_config_value(&mut self, key: &str) -> Result<(), ()> {
        config::read(key, |result| result.map(
            |value| self.last_value = Sliceable::new(0, value.to_vec())
        )).map_err(|_err| warn!("read error: no such key"))
    }

    pub fn get_config_value_slice(&mut self, data_slice: &mut [u8; SAT_PAYLOAD_MAX_SIZE]) -> SliceMeta {
        self.last_value.get_slice_sat(data_slice)
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

    pub fn add_image_data(&mut self, data: &[u8], data_len: usize) {
        self.image_payload.write_all(&data[..data_len]).unwrap();
    }

    pub fn clear_image_data(&mut self) {
        self.image_payload.get_mut().clear();
        self.image_payload.set_position(0);
    }

    pub fn flash_image(&mut self) -> Result<(), drtioaux::Error<!>> {
        let image = &self.image_payload.get_ref()[..];

        let (expected_crc, mut image) = {
            let (image, crc_slice) = image.split_at(image.len() - 4);
            (NativeEndian::read_u32(crc_slice), image)
        };

        let actual_crc = crc32::checksum_ieee(image);

        if actual_crc == expected_crc {
            drtioaux::send(0, &drtioaux::Packet::CoreMgmtReply { succeeded: true })?;
            #[cfg(not(soc_platform = "efc"))]
            unsafe {
                clock::spin_us(10000);
                csr::gt_drtio::txenable_write(0);
            }

            let bin_origins = [
                ("gateware"  , 0                      ),
                ("bootloader", mem::ROM_BASE          ),
                ("firmware"  , mem::FLASH_BOOT_ADDRESS),
            ];

            for (name, origin) in bin_origins {
                info!("Flashing {} binary...", name);
                let size = NativeEndian::read_u32(&image[..4]) as usize;
                image = &image[4..];

                let (bin, remaining) = image.split_at(size);
                image = remaining;

                unsafe { spiflash::flash_binary(origin, bin) };
            }

            warn!("restarting");
            unsafe { spiflash::reload(); }

        } else {
            error!("CRC failed in SDRAM (actual {:08x}, expected {:08x})", actual_crc, expected_crc);
            self.clear_image_data();
            drtioaux::send(0, &drtioaux::Packet::CoreMgmtReply { succeeded: false })
        }
    }
}
