use alloc::vec::Vec;

use routing::{Sliceable, SliceMeta};
use board_misoc::config;
use io::{Cursor, ProtoRead, ProtoWrite};
use proto_artiq::drtioaux_proto::SAT_PAYLOAD_MAX_SIZE;


type Result<T> = core::result::Result<T, ()>;

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

    pub fn fetch_config_value(&mut self, key: &str) -> Result<()> {
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

    pub fn write_config(&mut self) -> Result<()> {
        let key = self.current_payload.read_string().map_err(
            |err| error!("error on reading key: {:?}", err))?;
        let value = self.current_payload.read_bytes().unwrap();

        config::write(&key, &value).map_err(|err| {
            error!("error on writing config: {:?}", err);
        })
    }
}