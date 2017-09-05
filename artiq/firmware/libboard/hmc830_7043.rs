include!(concat!(env!("OUT_DIR"), "/hmc7043_writes.rs"));

pub fn init() -> Result<(), &'static str> {
    error!("HMC830/7043 support is not implemented");
    Ok(())
}
