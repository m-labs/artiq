use alloc::vec::Vec;

use routing::{Sliceable, SliceMeta};
use board_artiq::drtioaux;
use board_misoc::{clock, config, csr, spiflash};
use io::{Cursor, ProtoRead, ProtoWrite};
use proto_artiq::drtioaux_proto::SAT_PAYLOAD_MAX_SIZE;


pub struct Manager {
    current_payload: Cursor<Vec<u8>>,
    last_value: Sliceable,
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            current_payload: Cursor::new(Vec::new()),
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

    pub fn add_data(&mut self, data: &[u8], data_len: usize) {
        self.current_payload.write_all(&data[..data_len]).unwrap();
    }

    pub fn clear_data(&mut self) {
        self.current_payload.get_mut().clear();
        self.current_payload.set_position(0);
    }

    pub fn write_config(&mut self) -> Result<(), drtioaux::Error<!>> {
        let key = match self.current_payload.read_string() {
            Ok(key) => key,
            Err(err) => {
                self.clear_data();
                error!("error on reading key: {:?}", err);
                return drtioaux::send(0, &drtioaux::Packet::CoreMgmtNack);
            }
        };

        let value = self.current_payload.read_bytes().unwrap();

        match key.as_str() {
            "gateware" | "bootloader" | "firmware" => {
                drtioaux::send(0, &drtioaux::Packet::CoreMgmtRebootImminent)?;
                #[cfg(not(soc_platform = "efc"))]
                unsafe {
                    clock::spin_us(10000);
                    csr::gt_drtio::txenable_write(0);
                }
                config::write(&key, &value).expect("failed to write to flash storage");
                warn!("restarting");
                unsafe { spiflash::reload(); }
            }

            _ => {
                let succeeded = config::write(&key, &value).map_err(|err| {
                    error!("error on writing config: {:?}", err);
                }).is_ok();

                self.clear_data();

                if succeeded {
                    drtioaux::send(0, &drtioaux::Packet::CoreMgmtAck)
                } else {
                    drtioaux::send(0, &drtioaux::Packet::CoreMgmtNack)
                }
            }
        }
    }
}
