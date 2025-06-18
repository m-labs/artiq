#[allow(dead_code)]
pub mod mem {
  pub const SRAM_BASE: usize = 0x10000000;
  pub const SRAM_SIZE: usize = 0x00002000;

  pub const CSR_BASE: usize = 0x60000000;
  pub const CSR_SIZE: usize = 0x00020000;

  pub const MAIN_RAM_BASE: usize = 0x40000000;
  pub const MAIN_RAM_SIZE: usize = 0x10000000;

  pub const ROM_BASE: usize = 0x00400000;
  pub const ROM_SIZE: usize = 0x00c00000;

  pub const ETHMAC_BASE: usize = 0xb0000000;
  pub const ETHMAC_SIZE: usize = 0x00004000;

  pub const MAILBOX_BASE: usize = 0xf0000000;
  pub const MAILBOX_SIZE: usize = 0x00000018;

  pub const FLASH_BOOT_ADDRESS: usize = 0x00450000;

}
