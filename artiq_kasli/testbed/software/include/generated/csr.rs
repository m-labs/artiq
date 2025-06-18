#[allow(dead_code)]
pub mod csr {
  pub const RTIO_BASE: *mut u32 = 0xa0000000 as *mut u32;

  pub mod rtio {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const TARGET_ADDR: *mut u32 = 0xa0000000 as *mut u32;
    pub const TARGET_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn target_read() -> u32 {
      read_volatile(TARGET_ADDR) as u32
    }

    #[inline(always)]
    pub unsafe fn target_write(w: u32) {
      write_volatile(TARGET_ADDR.offset(0), (w) as u32);
    }

    pub const NOW_HI_ADDR: *mut u32 = 0xa0000008 as *mut u32;
    pub const NOW_HI_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn now_hi_read() -> u32 {
      read_volatile(NOW_HI_ADDR) as u32
    }

    #[inline(always)]
    pub unsafe fn now_hi_write(w: u32) {
      write_volatile(NOW_HI_ADDR.offset(0), (w) as u32);
    }

    pub const NOW_LO_ADDR: *mut u32 = 0xa0000010 as *mut u32;
    pub const NOW_LO_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn now_lo_read() -> u32 {
      read_volatile(NOW_LO_ADDR) as u32
    }

    #[inline(always)]
    pub unsafe fn now_lo_write(w: u32) {
      write_volatile(NOW_LO_ADDR.offset(0), (w) as u32);
    }

    pub const O_DATA_ADDR: *mut u32 = 0xa0000018 as *mut u32;
    pub const O_DATA_SIZE: usize = 16;

    pub const O_STATUS_ADDR: *mut u32 = 0xa0000098 as *mut u32;
    pub const O_STATUS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn o_status_read() -> u8 {
      read_volatile(O_STATUS_ADDR) as u8
    }

    pub const I_TIMEOUT_ADDR: *mut u32 = 0xa00000a0 as *mut u32;
    pub const I_TIMEOUT_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn i_timeout_read() -> u64 {
      let r = read_volatile(I_TIMEOUT_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 32 | read_volatile(I_TIMEOUT_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn i_timeout_write(w: u64) {
      write_volatile(I_TIMEOUT_ADDR.offset(0), (w >> 32) as u32);
      write_volatile(I_TIMEOUT_ADDR.offset(2), (w) as u32);
    }

    pub const I_DATA_ADDR: *mut u32 = 0xa00000b0 as *mut u32;
    pub const I_DATA_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn i_data_read() -> u32 {
      read_volatile(I_DATA_ADDR) as u32
    }

    pub const I_TIMESTAMP_ADDR: *mut u32 = 0xa00000b8 as *mut u32;
    pub const I_TIMESTAMP_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn i_timestamp_read() -> u64 {
      let r = read_volatile(I_TIMESTAMP_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 32 | read_volatile(I_TIMESTAMP_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const I_STATUS_ADDR: *mut u32 = 0xa00000c8 as *mut u32;
    pub const I_STATUS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn i_status_read() -> u8 {
      read_volatile(I_STATUS_ADDR) as u8
    }

    pub const COUNTER_ADDR: *mut u32 = 0xa00000d0 as *mut u32;
    pub const COUNTER_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn counter_read() -> u64 {
      let r = read_volatile(COUNTER_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 32 | read_volatile(COUNTER_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const COUNTER_UPDATE_ADDR: *mut u32 = 0xa00000e0 as *mut u32;
    pub const COUNTER_UPDATE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn counter_update_read() -> u8 {
      read_volatile(COUNTER_UPDATE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn counter_update_write(w: u8) {
      write_volatile(COUNTER_UPDATE_ADDR.offset(0), (w) as u32);
    }

  }

  pub const RTIO_DMA_BASE: *mut u32 = 0xb0000000 as *mut u32;

  pub mod rtio_dma {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const ENABLE_ADDR: *mut u32 = 0xb0000000 as *mut u32;
    pub const ENABLE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn enable_read() -> u8 {
      read_volatile(ENABLE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn enable_write(w: u8) {
      write_volatile(ENABLE_ADDR.offset(0), (w) as u32);
    }

    pub const BASE_ADDRESS_ADDR: *mut u32 = 0xb0000008 as *mut u32;
    pub const BASE_ADDRESS_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn base_address_read() -> u64 {
      let r = read_volatile(BASE_ADDRESS_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 32 | read_volatile(BASE_ADDRESS_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn base_address_write(w: u64) {
      write_volatile(BASE_ADDRESS_ADDR.offset(0), (w >> 32) as u32);
      write_volatile(BASE_ADDRESS_ADDR.offset(2), (w) as u32);
    }

    pub const TIME_OFFSET_ADDR: *mut u32 = 0xb0000018 as *mut u32;
    pub const TIME_OFFSET_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn time_offset_read() -> u64 {
      let r = read_volatile(TIME_OFFSET_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 32 | read_volatile(TIME_OFFSET_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn time_offset_write(w: u64) {
      write_volatile(TIME_OFFSET_ADDR.offset(0), (w >> 32) as u32);
      write_volatile(TIME_OFFSET_ADDR.offset(2), (w) as u32);
    }

    pub const ERROR_ADDR: *mut u32 = 0xb0000028 as *mut u32;
    pub const ERROR_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn error_read() -> u8 {
      read_volatile(ERROR_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn error_write(w: u8) {
      write_volatile(ERROR_ADDR.offset(0), (w) as u32);
    }

    pub const ERROR_CHANNEL_ADDR: *mut u32 = 0xb0000030 as *mut u32;
    pub const ERROR_CHANNEL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn error_channel_read() -> u32 {
      read_volatile(ERROR_CHANNEL_ADDR) as u32
    }

    pub const ERROR_TIMESTAMP_ADDR: *mut u32 = 0xb0000038 as *mut u32;
    pub const ERROR_TIMESTAMP_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn error_timestamp_read() -> u64 {
      let r = read_volatile(ERROR_TIMESTAMP_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 32 | read_volatile(ERROR_TIMESTAMP_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const ERROR_ADDRESS_ADDR: *mut u32 = 0xb0000048 as *mut u32;
    pub const ERROR_ADDRESS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn error_address_read() -> u16 {
      read_volatile(ERROR_ADDRESS_ADDR) as u16
    }

  }

  pub const CRI_CON_BASE: *mut u32 = 0x90000000 as *mut u32;

  pub mod cri_con {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const SELECTED_ADDR: *mut u32 = 0x90000000 as *mut u32;
    pub const SELECTED_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn selected_read() -> u8 {
      read_volatile(SELECTED_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn selected_write(w: u8) {
      write_volatile(SELECTED_ADDR.offset(0), (w) as u32);
    }

  }

  pub const CRG_BASE: *mut u32 = 0xe0003000 as *mut u32;

  pub mod crg {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const SWITCH_DONE_ADDR: *mut u32 = 0xe0003000 as *mut u32;
    pub const SWITCH_DONE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn switch_done_read() -> u8 {
      read_volatile(SWITCH_DONE_ADDR) as u8
    }

    pub const CLOCK_SEL_ADDR: *mut u32 = 0xe0003008 as *mut u32;
    pub const CLOCK_SEL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn clock_sel_read() -> u8 {
      read_volatile(CLOCK_SEL_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn clock_sel_write(w: u8) {
      write_volatile(CLOCK_SEL_ADDR.offset(0), (w) as u32);
    }

  }

  pub const DDRPHY_BASE: *mut u32 = 0xe0003800 as *mut u32;

  pub mod ddrphy {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const DLY_SEL_ADDR: *mut u32 = 0xe0003800 as *mut u32;
    pub const DLY_SEL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn dly_sel_read() -> u8 {
      read_volatile(DLY_SEL_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn dly_sel_write(w: u8) {
      write_volatile(DLY_SEL_ADDR.offset(0), (w) as u32);
    }

    pub const RDLY_DQ_RST_ADDR: *mut u32 = 0xe0003808 as *mut u32;
    pub const RDLY_DQ_RST_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn rdly_dq_rst_read() -> u8 {
      read_volatile(RDLY_DQ_RST_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn rdly_dq_rst_write(w: u8) {
      write_volatile(RDLY_DQ_RST_ADDR.offset(0), (w) as u32);
    }

    pub const RDLY_DQ_INC_ADDR: *mut u32 = 0xe0003810 as *mut u32;
    pub const RDLY_DQ_INC_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn rdly_dq_inc_read() -> u8 {
      read_volatile(RDLY_DQ_INC_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn rdly_dq_inc_write(w: u8) {
      write_volatile(RDLY_DQ_INC_ADDR.offset(0), (w) as u32);
    }

    pub const RDLY_DQ_BITSLIP_ADDR: *mut u32 = 0xe0003818 as *mut u32;
    pub const RDLY_DQ_BITSLIP_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn rdly_dq_bitslip_read() -> u8 {
      read_volatile(RDLY_DQ_BITSLIP_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn rdly_dq_bitslip_write(w: u8) {
      write_volatile(RDLY_DQ_BITSLIP_ADDR.offset(0), (w) as u32);
    }

  }

  pub const DFII_BASE: *mut u32 = 0xe0002000 as *mut u32;

  pub mod dfii {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const CONTROL_ADDR: *mut u32 = 0xe0002000 as *mut u32;
    pub const CONTROL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn control_read() -> u8 {
      read_volatile(CONTROL_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn control_write(w: u8) {
      write_volatile(CONTROL_ADDR.offset(0), (w) as u32);
    }

    pub const PI0_COMMAND_ADDR: *mut u32 = 0xe0002008 as *mut u32;
    pub const PI0_COMMAND_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi0_command_read() -> u8 {
      read_volatile(PI0_COMMAND_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi0_command_write(w: u8) {
      write_volatile(PI0_COMMAND_ADDR.offset(0), (w) as u32);
    }

    pub const PI0_COMMAND_ISSUE_ADDR: *mut u32 = 0xe0002010 as *mut u32;
    pub const PI0_COMMAND_ISSUE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi0_command_issue_read() -> u8 {
      read_volatile(PI0_COMMAND_ISSUE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi0_command_issue_write(w: u8) {
      write_volatile(PI0_COMMAND_ISSUE_ADDR.offset(0), (w) as u32);
    }

    pub const PI0_ADDRESS_ADDR: *mut u32 = 0xe0002018 as *mut u32;
    pub const PI0_ADDRESS_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn pi0_address_read() -> u16 {
      let r = read_volatile(PI0_ADDRESS_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI0_ADDRESS_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn pi0_address_write(w: u16) {
      write_volatile(PI0_ADDRESS_ADDR.offset(0), (w >> 8) as u32);
      write_volatile(PI0_ADDRESS_ADDR.offset(2), (w) as u32);
    }

    pub const PI0_BADDRESS_ADDR: *mut u32 = 0xe0002028 as *mut u32;
    pub const PI0_BADDRESS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi0_baddress_read() -> u8 {
      read_volatile(PI0_BADDRESS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi0_baddress_write(w: u8) {
      write_volatile(PI0_BADDRESS_ADDR.offset(0), (w) as u32);
    }

    pub const PI0_WRDATA_ADDR: *mut u32 = 0xe0002030 as *mut u32;
    pub const PI0_WRDATA_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn pi0_wrdata_read() -> u32 {
      let r = read_volatile(PI0_WRDATA_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI0_WRDATA_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI0_WRDATA_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI0_WRDATA_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn pi0_wrdata_write(w: u32) {
      write_volatile(PI0_WRDATA_ADDR.offset(0), (w >> 24) as u32);
      write_volatile(PI0_WRDATA_ADDR.offset(2), (w >> 16) as u32);
      write_volatile(PI0_WRDATA_ADDR.offset(4), (w >> 8) as u32);
      write_volatile(PI0_WRDATA_ADDR.offset(6), (w) as u32);
    }

    pub const PI0_RDDATA_ADDR: *mut u32 = 0xe0002050 as *mut u32;
    pub const PI0_RDDATA_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn pi0_rddata_read() -> u32 {
      let r = read_volatile(PI0_RDDATA_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI0_RDDATA_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI0_RDDATA_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI0_RDDATA_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const PI1_COMMAND_ADDR: *mut u32 = 0xe0002070 as *mut u32;
    pub const PI1_COMMAND_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi1_command_read() -> u8 {
      read_volatile(PI1_COMMAND_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi1_command_write(w: u8) {
      write_volatile(PI1_COMMAND_ADDR.offset(0), (w) as u32);
    }

    pub const PI1_COMMAND_ISSUE_ADDR: *mut u32 = 0xe0002078 as *mut u32;
    pub const PI1_COMMAND_ISSUE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi1_command_issue_read() -> u8 {
      read_volatile(PI1_COMMAND_ISSUE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi1_command_issue_write(w: u8) {
      write_volatile(PI1_COMMAND_ISSUE_ADDR.offset(0), (w) as u32);
    }

    pub const PI1_ADDRESS_ADDR: *mut u32 = 0xe0002080 as *mut u32;
    pub const PI1_ADDRESS_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn pi1_address_read() -> u16 {
      let r = read_volatile(PI1_ADDRESS_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI1_ADDRESS_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn pi1_address_write(w: u16) {
      write_volatile(PI1_ADDRESS_ADDR.offset(0), (w >> 8) as u32);
      write_volatile(PI1_ADDRESS_ADDR.offset(2), (w) as u32);
    }

    pub const PI1_BADDRESS_ADDR: *mut u32 = 0xe0002090 as *mut u32;
    pub const PI1_BADDRESS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi1_baddress_read() -> u8 {
      read_volatile(PI1_BADDRESS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi1_baddress_write(w: u8) {
      write_volatile(PI1_BADDRESS_ADDR.offset(0), (w) as u32);
    }

    pub const PI1_WRDATA_ADDR: *mut u32 = 0xe0002098 as *mut u32;
    pub const PI1_WRDATA_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn pi1_wrdata_read() -> u32 {
      let r = read_volatile(PI1_WRDATA_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI1_WRDATA_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI1_WRDATA_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI1_WRDATA_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn pi1_wrdata_write(w: u32) {
      write_volatile(PI1_WRDATA_ADDR.offset(0), (w >> 24) as u32);
      write_volatile(PI1_WRDATA_ADDR.offset(2), (w >> 16) as u32);
      write_volatile(PI1_WRDATA_ADDR.offset(4), (w >> 8) as u32);
      write_volatile(PI1_WRDATA_ADDR.offset(6), (w) as u32);
    }

    pub const PI1_RDDATA_ADDR: *mut u32 = 0xe00020b8 as *mut u32;
    pub const PI1_RDDATA_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn pi1_rddata_read() -> u32 {
      let r = read_volatile(PI1_RDDATA_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI1_RDDATA_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI1_RDDATA_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI1_RDDATA_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const PI2_COMMAND_ADDR: *mut u32 = 0xe00020d8 as *mut u32;
    pub const PI2_COMMAND_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi2_command_read() -> u8 {
      read_volatile(PI2_COMMAND_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi2_command_write(w: u8) {
      write_volatile(PI2_COMMAND_ADDR.offset(0), (w) as u32);
    }

    pub const PI2_COMMAND_ISSUE_ADDR: *mut u32 = 0xe00020e0 as *mut u32;
    pub const PI2_COMMAND_ISSUE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi2_command_issue_read() -> u8 {
      read_volatile(PI2_COMMAND_ISSUE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi2_command_issue_write(w: u8) {
      write_volatile(PI2_COMMAND_ISSUE_ADDR.offset(0), (w) as u32);
    }

    pub const PI2_ADDRESS_ADDR: *mut u32 = 0xe00020e8 as *mut u32;
    pub const PI2_ADDRESS_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn pi2_address_read() -> u16 {
      let r = read_volatile(PI2_ADDRESS_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI2_ADDRESS_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn pi2_address_write(w: u16) {
      write_volatile(PI2_ADDRESS_ADDR.offset(0), (w >> 8) as u32);
      write_volatile(PI2_ADDRESS_ADDR.offset(2), (w) as u32);
    }

    pub const PI2_BADDRESS_ADDR: *mut u32 = 0xe00020f8 as *mut u32;
    pub const PI2_BADDRESS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi2_baddress_read() -> u8 {
      read_volatile(PI2_BADDRESS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi2_baddress_write(w: u8) {
      write_volatile(PI2_BADDRESS_ADDR.offset(0), (w) as u32);
    }

    pub const PI2_WRDATA_ADDR: *mut u32 = 0xe0002100 as *mut u32;
    pub const PI2_WRDATA_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn pi2_wrdata_read() -> u32 {
      let r = read_volatile(PI2_WRDATA_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI2_WRDATA_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI2_WRDATA_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI2_WRDATA_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn pi2_wrdata_write(w: u32) {
      write_volatile(PI2_WRDATA_ADDR.offset(0), (w >> 24) as u32);
      write_volatile(PI2_WRDATA_ADDR.offset(2), (w >> 16) as u32);
      write_volatile(PI2_WRDATA_ADDR.offset(4), (w >> 8) as u32);
      write_volatile(PI2_WRDATA_ADDR.offset(6), (w) as u32);
    }

    pub const PI2_RDDATA_ADDR: *mut u32 = 0xe0002120 as *mut u32;
    pub const PI2_RDDATA_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn pi2_rddata_read() -> u32 {
      let r = read_volatile(PI2_RDDATA_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI2_RDDATA_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI2_RDDATA_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI2_RDDATA_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const PI3_COMMAND_ADDR: *mut u32 = 0xe0002140 as *mut u32;
    pub const PI3_COMMAND_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi3_command_read() -> u8 {
      read_volatile(PI3_COMMAND_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi3_command_write(w: u8) {
      write_volatile(PI3_COMMAND_ADDR.offset(0), (w) as u32);
    }

    pub const PI3_COMMAND_ISSUE_ADDR: *mut u32 = 0xe0002148 as *mut u32;
    pub const PI3_COMMAND_ISSUE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi3_command_issue_read() -> u8 {
      read_volatile(PI3_COMMAND_ISSUE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi3_command_issue_write(w: u8) {
      write_volatile(PI3_COMMAND_ISSUE_ADDR.offset(0), (w) as u32);
    }

    pub const PI3_ADDRESS_ADDR: *mut u32 = 0xe0002150 as *mut u32;
    pub const PI3_ADDRESS_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn pi3_address_read() -> u16 {
      let r = read_volatile(PI3_ADDRESS_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI3_ADDRESS_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn pi3_address_write(w: u16) {
      write_volatile(PI3_ADDRESS_ADDR.offset(0), (w >> 8) as u32);
      write_volatile(PI3_ADDRESS_ADDR.offset(2), (w) as u32);
    }

    pub const PI3_BADDRESS_ADDR: *mut u32 = 0xe0002160 as *mut u32;
    pub const PI3_BADDRESS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn pi3_baddress_read() -> u8 {
      read_volatile(PI3_BADDRESS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn pi3_baddress_write(w: u8) {
      write_volatile(PI3_BADDRESS_ADDR.offset(0), (w) as u32);
    }

    pub const PI3_WRDATA_ADDR: *mut u32 = 0xe0002168 as *mut u32;
    pub const PI3_WRDATA_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn pi3_wrdata_read() -> u32 {
      let r = read_volatile(PI3_WRDATA_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI3_WRDATA_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI3_WRDATA_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI3_WRDATA_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn pi3_wrdata_write(w: u32) {
      write_volatile(PI3_WRDATA_ADDR.offset(0), (w >> 24) as u32);
      write_volatile(PI3_WRDATA_ADDR.offset(2), (w >> 16) as u32);
      write_volatile(PI3_WRDATA_ADDR.offset(4), (w >> 8) as u32);
      write_volatile(PI3_WRDATA_ADDR.offset(6), (w) as u32);
    }

    pub const PI3_RDDATA_ADDR: *mut u32 = 0xe0002188 as *mut u32;
    pub const PI3_RDDATA_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn pi3_rddata_read() -> u32 {
      let r = read_volatile(PI3_RDDATA_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI3_RDDATA_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI3_RDDATA_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PI3_RDDATA_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

  }

  pub const ERROR_LED_BASE: *mut u32 = 0xe0007000 as *mut u32;

  pub mod error_led {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const OUT_ADDR: *mut u32 = 0xe0007000 as *mut u32;
    pub const OUT_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn out_read() -> u8 {
      read_volatile(OUT_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn out_write(w: u8) {
      write_volatile(OUT_ADDR.offset(0), (w) as u32);
    }

  }

  pub const ETHMAC_BASE: *mut u32 = 0xe0006000 as *mut u32;

  pub mod ethmac {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const SRAM_WRITER_SLOT_ADDR: *mut u32 = 0xe0006000 as *mut u32;
    pub const SRAM_WRITER_SLOT_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_writer_slot_read() -> u8 {
      read_volatile(SRAM_WRITER_SLOT_ADDR) as u8
    }

    pub const SRAM_WRITER_LENGTH_ADDR: *mut u32 = 0xe0006008 as *mut u32;
    pub const SRAM_WRITER_LENGTH_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn sram_writer_length_read() -> u16 {
      let r = read_volatile(SRAM_WRITER_LENGTH_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(SRAM_WRITER_LENGTH_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const SRAM_WRITER_ERRORS_ADDR: *mut u32 = 0xe0006018 as *mut u32;
    pub const SRAM_WRITER_ERRORS_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn sram_writer_errors_read() -> u32 {
      let r = read_volatile(SRAM_WRITER_ERRORS_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(SRAM_WRITER_ERRORS_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(SRAM_WRITER_ERRORS_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(SRAM_WRITER_ERRORS_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const SRAM_WRITER_EV_STATUS_ADDR: *mut u32 = 0xe0006038 as *mut u32;
    pub const SRAM_WRITER_EV_STATUS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_writer_ev_status_read() -> u8 {
      read_volatile(SRAM_WRITER_EV_STATUS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sram_writer_ev_status_write(w: u8) {
      write_volatile(SRAM_WRITER_EV_STATUS_ADDR.offset(0), (w) as u32);
    }

    pub const SRAM_WRITER_EV_PENDING_ADDR: *mut u32 = 0xe0006040 as *mut u32;
    pub const SRAM_WRITER_EV_PENDING_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_writer_ev_pending_read() -> u8 {
      read_volatile(SRAM_WRITER_EV_PENDING_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sram_writer_ev_pending_write(w: u8) {
      write_volatile(SRAM_WRITER_EV_PENDING_ADDR.offset(0), (w) as u32);
    }

    pub const SRAM_WRITER_EV_ENABLE_ADDR: *mut u32 = 0xe0006048 as *mut u32;
    pub const SRAM_WRITER_EV_ENABLE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_writer_ev_enable_read() -> u8 {
      read_volatile(SRAM_WRITER_EV_ENABLE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sram_writer_ev_enable_write(w: u8) {
      write_volatile(SRAM_WRITER_EV_ENABLE_ADDR.offset(0), (w) as u32);
    }

    pub const SRAM_READER_START_ADDR: *mut u32 = 0xe0006050 as *mut u32;
    pub const SRAM_READER_START_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_reader_start_read() -> u8 {
      read_volatile(SRAM_READER_START_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sram_reader_start_write(w: u8) {
      write_volatile(SRAM_READER_START_ADDR.offset(0), (w) as u32);
    }

    pub const SRAM_READER_READY_ADDR: *mut u32 = 0xe0006058 as *mut u32;
    pub const SRAM_READER_READY_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_reader_ready_read() -> u8 {
      read_volatile(SRAM_READER_READY_ADDR) as u8
    }

    pub const SRAM_READER_SLOT_ADDR: *mut u32 = 0xe0006060 as *mut u32;
    pub const SRAM_READER_SLOT_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_reader_slot_read() -> u8 {
      read_volatile(SRAM_READER_SLOT_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sram_reader_slot_write(w: u8) {
      write_volatile(SRAM_READER_SLOT_ADDR.offset(0), (w) as u32);
    }

    pub const SRAM_READER_LENGTH_ADDR: *mut u32 = 0xe0006068 as *mut u32;
    pub const SRAM_READER_LENGTH_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn sram_reader_length_read() -> u16 {
      let r = read_volatile(SRAM_READER_LENGTH_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(SRAM_READER_LENGTH_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn sram_reader_length_write(w: u16) {
      write_volatile(SRAM_READER_LENGTH_ADDR.offset(0), (w >> 8) as u32);
      write_volatile(SRAM_READER_LENGTH_ADDR.offset(2), (w) as u32);
    }

    pub const SRAM_READER_EV_STATUS_ADDR: *mut u32 = 0xe0006078 as *mut u32;
    pub const SRAM_READER_EV_STATUS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_reader_ev_status_read() -> u8 {
      read_volatile(SRAM_READER_EV_STATUS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sram_reader_ev_status_write(w: u8) {
      write_volatile(SRAM_READER_EV_STATUS_ADDR.offset(0), (w) as u32);
    }

    pub const SRAM_READER_EV_PENDING_ADDR: *mut u32 = 0xe0006080 as *mut u32;
    pub const SRAM_READER_EV_PENDING_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_reader_ev_pending_read() -> u8 {
      read_volatile(SRAM_READER_EV_PENDING_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sram_reader_ev_pending_write(w: u8) {
      write_volatile(SRAM_READER_EV_PENDING_ADDR.offset(0), (w) as u32);
    }

    pub const SRAM_READER_EV_ENABLE_ADDR: *mut u32 = 0xe0006088 as *mut u32;
    pub const SRAM_READER_EV_ENABLE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sram_reader_ev_enable_read() -> u8 {
      read_volatile(SRAM_READER_EV_ENABLE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sram_reader_ev_enable_write(w: u8) {
      write_volatile(SRAM_READER_EV_ENABLE_ADDR.offset(0), (w) as u32);
    }

    pub const PREAMBLE_ERRORS_ADDR: *mut u32 = 0xe0006090 as *mut u32;
    pub const PREAMBLE_ERRORS_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn preamble_errors_read() -> u32 {
      let r = read_volatile(PREAMBLE_ERRORS_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PREAMBLE_ERRORS_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PREAMBLE_ERRORS_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(PREAMBLE_ERRORS_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const CRC_ERRORS_ADDR: *mut u32 = 0xe00060b0 as *mut u32;
    pub const CRC_ERRORS_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn crc_errors_read() -> u32 {
      let r = read_volatile(CRC_ERRORS_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(CRC_ERRORS_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(CRC_ERRORS_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(CRC_ERRORS_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

  }

  pub const I2C_BASE: *mut u32 = 0xe0007800 as *mut u32;

  pub mod i2c {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const IN_ADDR: *mut u32 = 0xe0007800 as *mut u32;
    pub const IN_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn in_read() -> u8 {
      read_volatile(IN_ADDR) as u8
    }

    pub const OUT_ADDR: *mut u32 = 0xe0007808 as *mut u32;
    pub const OUT_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn out_read() -> u8 {
      read_volatile(OUT_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn out_write(w: u8) {
      write_volatile(OUT_ADDR.offset(0), (w) as u32);
    }

    pub const OE_ADDR: *mut u32 = 0xe0007810 as *mut u32;
    pub const OE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn oe_read() -> u8 {
      read_volatile(OE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn oe_write(w: u8) {
      write_volatile(OE_ADDR.offset(0), (w) as u32);
    }

  }

  pub const ICAP_BASE: *mut u32 = 0xe0005000 as *mut u32;

  pub mod icap {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const IPROG_ADDR: *mut u32 = 0xe0005000 as *mut u32;
    pub const IPROG_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn iprog_read() -> u8 {
      read_volatile(IPROG_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn iprog_write(w: u8) {
      write_volatile(IPROG_ADDR.offset(0), (w) as u32);
    }

  }

  pub const IDENTIFIER_BASE: *mut u32 = 0xe0001000 as *mut u32;

  pub mod identifier {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const ADDRESS_ADDR: *mut u32 = 0xe0001000 as *mut u32;
    pub const ADDRESS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn address_read() -> u8 {
      read_volatile(ADDRESS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn address_write(w: u8) {
      write_volatile(ADDRESS_ADDR.offset(0), (w) as u32);
    }

    pub const DATA_ADDR: *mut u32 = 0xe0001008 as *mut u32;
    pub const DATA_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn data_read() -> u8 {
      read_volatile(DATA_ADDR) as u8
    }

  }

  pub const KERNEL_CPU_BASE: *mut u32 = 0xe0006800 as *mut u32;

  pub mod kernel_cpu {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const RESET_ADDR: *mut u32 = 0xe0006800 as *mut u32;
    pub const RESET_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn reset_read() -> u8 {
      read_volatile(RESET_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn reset_write(w: u8) {
      write_volatile(RESET_ADDR.offset(0), (w) as u32);
    }

  }

  pub const RTIO_ANALYZER_BASE: *mut u32 = 0xe0009000 as *mut u32;

  pub mod rtio_analyzer {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const ENABLE_ADDR: *mut u32 = 0xe0009000 as *mut u32;
    pub const ENABLE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn enable_read() -> u8 {
      read_volatile(ENABLE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn enable_write(w: u8) {
      write_volatile(ENABLE_ADDR.offset(0), (w) as u32);
    }

    pub const BUSY_ADDR: *mut u32 = 0xe0009008 as *mut u32;
    pub const BUSY_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn busy_read() -> u8 {
      read_volatile(BUSY_ADDR) as u8
    }

    pub const MESSAGE_ENCODER_OVERFLOW_ADDR: *mut u32 = 0xe0009010 as *mut u32;
    pub const MESSAGE_ENCODER_OVERFLOW_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn message_encoder_overflow_read() -> u8 {
      read_volatile(MESSAGE_ENCODER_OVERFLOW_ADDR) as u8
    }

    pub const MESSAGE_ENCODER_OVERFLOW_RESET_ADDR: *mut u32 = 0xe0009018 as *mut u32;
    pub const MESSAGE_ENCODER_OVERFLOW_RESET_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn message_encoder_overflow_reset_read() -> u8 {
      read_volatile(MESSAGE_ENCODER_OVERFLOW_RESET_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn message_encoder_overflow_reset_write(w: u8) {
      write_volatile(MESSAGE_ENCODER_OVERFLOW_RESET_ADDR.offset(0), (w) as u32);
    }

    pub const DMA_RESET_ADDR: *mut u32 = 0xe0009020 as *mut u32;
    pub const DMA_RESET_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn dma_reset_read() -> u8 {
      read_volatile(DMA_RESET_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn dma_reset_write(w: u8) {
      write_volatile(DMA_RESET_ADDR.offset(0), (w) as u32);
    }

    pub const DMA_BASE_ADDRESS_ADDR: *mut u32 = 0xe0009028 as *mut u32;
    pub const DMA_BASE_ADDRESS_SIZE: usize = 5;

    #[inline(always)]
    pub unsafe fn dma_base_address_read() -> u64 {
      let r = read_volatile(DMA_BASE_ADDRESS_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BASE_ADDRESS_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BASE_ADDRESS_ADDR.offset(4)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BASE_ADDRESS_ADDR.offset(6)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BASE_ADDRESS_ADDR.offset(8)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn dma_base_address_write(w: u64) {
      write_volatile(DMA_BASE_ADDRESS_ADDR.offset(0), (w >> 32) as u32);
      write_volatile(DMA_BASE_ADDRESS_ADDR.offset(2), (w >> 24) as u32);
      write_volatile(DMA_BASE_ADDRESS_ADDR.offset(4), (w >> 16) as u32);
      write_volatile(DMA_BASE_ADDRESS_ADDR.offset(6), (w >> 8) as u32);
      write_volatile(DMA_BASE_ADDRESS_ADDR.offset(8), (w) as u32);
    }

    pub const DMA_LAST_ADDRESS_ADDR: *mut u32 = 0xe0009050 as *mut u32;
    pub const DMA_LAST_ADDRESS_SIZE: usize = 5;

    #[inline(always)]
    pub unsafe fn dma_last_address_read() -> u64 {
      let r = read_volatile(DMA_LAST_ADDRESS_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_LAST_ADDRESS_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_LAST_ADDRESS_ADDR.offset(4)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_LAST_ADDRESS_ADDR.offset(6)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_LAST_ADDRESS_ADDR.offset(8)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn dma_last_address_write(w: u64) {
      write_volatile(DMA_LAST_ADDRESS_ADDR.offset(0), (w >> 32) as u32);
      write_volatile(DMA_LAST_ADDRESS_ADDR.offset(2), (w >> 24) as u32);
      write_volatile(DMA_LAST_ADDRESS_ADDR.offset(4), (w >> 16) as u32);
      write_volatile(DMA_LAST_ADDRESS_ADDR.offset(6), (w >> 8) as u32);
      write_volatile(DMA_LAST_ADDRESS_ADDR.offset(8), (w) as u32);
    }

    pub const DMA_BYTE_COUNT_ADDR: *mut u32 = 0xe0009078 as *mut u32;
    pub const DMA_BYTE_COUNT_SIZE: usize = 8;

    #[inline(always)]
    pub unsafe fn dma_byte_count_read() -> u64 {
      let r = read_volatile(DMA_BYTE_COUNT_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BYTE_COUNT_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BYTE_COUNT_ADDR.offset(4)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BYTE_COUNT_ADDR.offset(6)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BYTE_COUNT_ADDR.offset(8)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BYTE_COUNT_ADDR.offset(10)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BYTE_COUNT_ADDR.offset(12)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(DMA_BYTE_COUNT_ADDR.offset(14)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

  }

  pub const RTIO_CORE_BASE: *mut u32 = 0xe0008000 as *mut u32;

  pub mod rtio_core {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const RESET_ADDR: *mut u32 = 0xe0008000 as *mut u32;
    pub const RESET_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn reset_read() -> u8 {
      read_volatile(RESET_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn reset_write(w: u8) {
      write_volatile(RESET_ADDR.offset(0), (w) as u32);
    }

    pub const RESET_PHY_ADDR: *mut u32 = 0xe0008008 as *mut u32;
    pub const RESET_PHY_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn reset_phy_read() -> u8 {
      read_volatile(RESET_PHY_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn reset_phy_write(w: u8) {
      write_volatile(RESET_PHY_ADDR.offset(0), (w) as u32);
    }

    pub const SED_SPREAD_ENABLE_ADDR: *mut u32 = 0xe0008010 as *mut u32;
    pub const SED_SPREAD_ENABLE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn sed_spread_enable_read() -> u8 {
      read_volatile(SED_SPREAD_ENABLE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn sed_spread_enable_write(w: u8) {
      write_volatile(SED_SPREAD_ENABLE_ADDR.offset(0), (w) as u32);
    }

    pub const ASYNC_ERROR_ADDR: *mut u32 = 0xe0008018 as *mut u32;
    pub const ASYNC_ERROR_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn async_error_read() -> u8 {
      read_volatile(ASYNC_ERROR_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn async_error_write(w: u8) {
      write_volatile(ASYNC_ERROR_ADDR.offset(0), (w) as u32);
    }

    pub const COLLISION_CHANNEL_ADDR: *mut u32 = 0xe0008020 as *mut u32;
    pub const COLLISION_CHANNEL_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn collision_channel_read() -> u16 {
      let r = read_volatile(COLLISION_CHANNEL_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(COLLISION_CHANNEL_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const BUSY_CHANNEL_ADDR: *mut u32 = 0xe0008030 as *mut u32;
    pub const BUSY_CHANNEL_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn busy_channel_read() -> u16 {
      let r = read_volatile(BUSY_CHANNEL_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(BUSY_CHANNEL_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const SEQUENCE_ERROR_CHANNEL_ADDR: *mut u32 = 0xe0008040 as *mut u32;
    pub const SEQUENCE_ERROR_CHANNEL_SIZE: usize = 2;

    #[inline(always)]
    pub unsafe fn sequence_error_channel_read() -> u16 {
      let r = read_volatile(SEQUENCE_ERROR_CHANNEL_ADDR) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(SEQUENCE_ERROR_CHANNEL_ADDR.offset(2)) as u16;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

  }

  pub const RTIO_MONINJ_BASE: *mut u32 = 0xe0008800 as *mut u32;

  pub mod rtio_moninj {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const MON_CHAN_SEL_ADDR: *mut u32 = 0xe0008800 as *mut u32;
    pub const MON_CHAN_SEL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn mon_chan_sel_read() -> u8 {
      read_volatile(MON_CHAN_SEL_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn mon_chan_sel_write(w: u8) {
      write_volatile(MON_CHAN_SEL_ADDR.offset(0), (w) as u32);
    }

    pub const MON_PROBE_SEL_ADDR: *mut u32 = 0xe0008808 as *mut u32;
    pub const MON_PROBE_SEL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn mon_probe_sel_read() -> u8 {
      read_volatile(MON_PROBE_SEL_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn mon_probe_sel_write(w: u8) {
      write_volatile(MON_PROBE_SEL_ADDR.offset(0), (w) as u32);
    }

    pub const MON_VALUE_UPDATE_ADDR: *mut u32 = 0xe0008810 as *mut u32;
    pub const MON_VALUE_UPDATE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn mon_value_update_read() -> u8 {
      read_volatile(MON_VALUE_UPDATE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn mon_value_update_write(w: u8) {
      write_volatile(MON_VALUE_UPDATE_ADDR.offset(0), (w) as u32);
    }

    pub const MON_VALUE_ADDR: *mut u32 = 0xe0008818 as *mut u32;
    pub const MON_VALUE_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn mon_value_read() -> u32 {
      let r = read_volatile(MON_VALUE_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(MON_VALUE_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(MON_VALUE_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(MON_VALUE_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const INJ_CHAN_SEL_ADDR: *mut u32 = 0xe0008838 as *mut u32;
    pub const INJ_CHAN_SEL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn inj_chan_sel_read() -> u8 {
      read_volatile(INJ_CHAN_SEL_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn inj_chan_sel_write(w: u8) {
      write_volatile(INJ_CHAN_SEL_ADDR.offset(0), (w) as u32);
    }

    pub const INJ_OVERRIDE_SEL_ADDR: *mut u32 = 0xe0008840 as *mut u32;
    pub const INJ_OVERRIDE_SEL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn inj_override_sel_read() -> u8 {
      read_volatile(INJ_OVERRIDE_SEL_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn inj_override_sel_write(w: u8) {
      write_volatile(INJ_OVERRIDE_SEL_ADDR.offset(0), (w) as u32);
    }

    pub const INJ_VALUE_ADDR: *mut u32 = 0xe0008848 as *mut u32;
    pub const INJ_VALUE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn inj_value_read() -> u8 {
      read_volatile(INJ_VALUE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn inj_value_write(w: u8) {
      write_volatile(INJ_VALUE_ADDR.offset(0), (w) as u32);
    }

  }

  pub const SPIFLASH_BASE: *mut u32 = 0xe0004800 as *mut u32;

  pub mod spiflash {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const BITBANG_ADDR: *mut u32 = 0xe0004800 as *mut u32;
    pub const BITBANG_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn bitbang_read() -> u8 {
      read_volatile(BITBANG_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn bitbang_write(w: u8) {
      write_volatile(BITBANG_ADDR.offset(0), (w) as u32);
    }

    pub const MISO_ADDR: *mut u32 = 0xe0004808 as *mut u32;
    pub const MISO_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn miso_read() -> u8 {
      read_volatile(MISO_ADDR) as u8
    }

    pub const BITBANG_EN_ADDR: *mut u32 = 0xe0004810 as *mut u32;
    pub const BITBANG_EN_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn bitbang_en_read() -> u8 {
      read_volatile(BITBANG_EN_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn bitbang_en_write(w: u8) {
      write_volatile(BITBANG_EN_ADDR.offset(0), (w) as u32);
    }

  }

  pub const TIMER0_BASE: *mut u32 = 0xe0001800 as *mut u32;

  pub mod timer0 {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const LOAD_ADDR: *mut u32 = 0xe0001800 as *mut u32;
    pub const LOAD_SIZE: usize = 8;

    #[inline(always)]
    pub unsafe fn load_read() -> u64 {
      let r = read_volatile(LOAD_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(LOAD_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(LOAD_ADDR.offset(4)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(LOAD_ADDR.offset(6)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(LOAD_ADDR.offset(8)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(LOAD_ADDR.offset(10)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(LOAD_ADDR.offset(12)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(LOAD_ADDR.offset(14)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn load_write(w: u64) {
      write_volatile(LOAD_ADDR.offset(0), (w >> 56) as u32);
      write_volatile(LOAD_ADDR.offset(2), (w >> 48) as u32);
      write_volatile(LOAD_ADDR.offset(4), (w >> 40) as u32);
      write_volatile(LOAD_ADDR.offset(6), (w >> 32) as u32);
      write_volatile(LOAD_ADDR.offset(8), (w >> 24) as u32);
      write_volatile(LOAD_ADDR.offset(10), (w >> 16) as u32);
      write_volatile(LOAD_ADDR.offset(12), (w >> 8) as u32);
      write_volatile(LOAD_ADDR.offset(14), (w) as u32);
    }

    pub const RELOAD_ADDR: *mut u32 = 0xe0001840 as *mut u32;
    pub const RELOAD_SIZE: usize = 8;

    #[inline(always)]
    pub unsafe fn reload_read() -> u64 {
      let r = read_volatile(RELOAD_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(RELOAD_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(RELOAD_ADDR.offset(4)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(RELOAD_ADDR.offset(6)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(RELOAD_ADDR.offset(8)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(RELOAD_ADDR.offset(10)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(RELOAD_ADDR.offset(12)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(RELOAD_ADDR.offset(14)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn reload_write(w: u64) {
      write_volatile(RELOAD_ADDR.offset(0), (w >> 56) as u32);
      write_volatile(RELOAD_ADDR.offset(2), (w >> 48) as u32);
      write_volatile(RELOAD_ADDR.offset(4), (w >> 40) as u32);
      write_volatile(RELOAD_ADDR.offset(6), (w >> 32) as u32);
      write_volatile(RELOAD_ADDR.offset(8), (w >> 24) as u32);
      write_volatile(RELOAD_ADDR.offset(10), (w >> 16) as u32);
      write_volatile(RELOAD_ADDR.offset(12), (w >> 8) as u32);
      write_volatile(RELOAD_ADDR.offset(14), (w) as u32);
    }

    pub const EN_ADDR: *mut u32 = 0xe0001880 as *mut u32;
    pub const EN_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn en_read() -> u8 {
      read_volatile(EN_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn en_write(w: u8) {
      write_volatile(EN_ADDR.offset(0), (w) as u32);
    }

    pub const UPDATE_VALUE_ADDR: *mut u32 = 0xe0001888 as *mut u32;
    pub const UPDATE_VALUE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn update_value_read() -> u8 {
      read_volatile(UPDATE_VALUE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn update_value_write(w: u8) {
      write_volatile(UPDATE_VALUE_ADDR.offset(0), (w) as u32);
    }

    pub const VALUE_ADDR: *mut u32 = 0xe0001890 as *mut u32;
    pub const VALUE_SIZE: usize = 8;

    #[inline(always)]
    pub unsafe fn value_read() -> u64 {
      let r = read_volatile(VALUE_ADDR) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(VALUE_ADDR.offset(2)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(VALUE_ADDR.offset(4)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(VALUE_ADDR.offset(6)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(VALUE_ADDR.offset(8)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(VALUE_ADDR.offset(10)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(VALUE_ADDR.offset(12)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(VALUE_ADDR.offset(14)) as u64;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    pub const EV_STATUS_ADDR: *mut u32 = 0xe00018d0 as *mut u32;
    pub const EV_STATUS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn ev_status_read() -> u8 {
      read_volatile(EV_STATUS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn ev_status_write(w: u8) {
      write_volatile(EV_STATUS_ADDR.offset(0), (w) as u32);
    }

    pub const EV_PENDING_ADDR: *mut u32 = 0xe00018d8 as *mut u32;
    pub const EV_PENDING_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn ev_pending_read() -> u8 {
      read_volatile(EV_PENDING_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn ev_pending_write(w: u8) {
      write_volatile(EV_PENDING_ADDR.offset(0), (w) as u32);
    }

    pub const EV_ENABLE_ADDR: *mut u32 = 0xe00018e0 as *mut u32;
    pub const EV_ENABLE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn ev_enable_read() -> u8 {
      read_volatile(EV_ENABLE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn ev_enable_write(w: u8) {
      write_volatile(EV_ENABLE_ADDR.offset(0), (w) as u32);
    }

  }

  pub const UART_BASE: *mut u32 = 0xe0000800 as *mut u32;

  pub mod uart {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const RXTX_ADDR: *mut u32 = 0xe0000800 as *mut u32;
    pub const RXTX_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn rxtx_read() -> u8 {
      read_volatile(RXTX_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn rxtx_write(w: u8) {
      write_volatile(RXTX_ADDR.offset(0), (w) as u32);
    }

    pub const TXFULL_ADDR: *mut u32 = 0xe0000808 as *mut u32;
    pub const TXFULL_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn txfull_read() -> u8 {
      read_volatile(TXFULL_ADDR) as u8
    }

    pub const RXEMPTY_ADDR: *mut u32 = 0xe0000810 as *mut u32;
    pub const RXEMPTY_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn rxempty_read() -> u8 {
      read_volatile(RXEMPTY_ADDR) as u8
    }

    pub const EV_STATUS_ADDR: *mut u32 = 0xe0000818 as *mut u32;
    pub const EV_STATUS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn ev_status_read() -> u8 {
      read_volatile(EV_STATUS_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn ev_status_write(w: u8) {
      write_volatile(EV_STATUS_ADDR.offset(0), (w) as u32);
    }

    pub const EV_PENDING_ADDR: *mut u32 = 0xe0000820 as *mut u32;
    pub const EV_PENDING_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn ev_pending_read() -> u8 {
      read_volatile(EV_PENDING_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn ev_pending_write(w: u8) {
      write_volatile(EV_PENDING_ADDR.offset(0), (w) as u32);
    }

    pub const EV_ENABLE_ADDR: *mut u32 = 0xe0000828 as *mut u32;
    pub const EV_ENABLE_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn ev_enable_read() -> u8 {
      read_volatile(EV_ENABLE_ADDR) as u8
    }

    #[inline(always)]
    pub unsafe fn ev_enable_write(w: u8) {
      write_volatile(EV_ENABLE_ADDR.offset(0), (w) as u32);
    }

  }

  pub const UART_PHY_BASE: *mut u32 = 0xe0000000 as *mut u32;

  pub mod uart_phy {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const TUNING_WORD_ADDR: *mut u32 = 0xe0000000 as *mut u32;
    pub const TUNING_WORD_SIZE: usize = 4;

    #[inline(always)]
    pub unsafe fn tuning_word_read() -> u32 {
      let r = read_volatile(TUNING_WORD_ADDR) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(TUNING_WORD_ADDR.offset(2)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(TUNING_WORD_ADDR.offset(4)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      let r = r << 8 | read_volatile(TUNING_WORD_ADDR.offset(6)) as u32;
      #[cfg(target_arch = "arm")]      dmb();
      r
    }

    #[inline(always)]
    pub unsafe fn tuning_word_write(w: u32) {
      write_volatile(TUNING_WORD_ADDR.offset(0), (w >> 24) as u32);
      write_volatile(TUNING_WORD_ADDR.offset(2), (w >> 16) as u32);
      write_volatile(TUNING_WORD_ADDR.offset(4), (w >> 8) as u32);
      write_volatile(TUNING_WORD_ADDR.offset(6), (w) as u32);
    }

  }

  pub const VIRTUAL_LEDS_BASE: *mut u32 = 0xe0004000 as *mut u32;

  pub mod virtual_leds {
    #[allow(unused_imports)]
    use core::ptr::{read_volatile, write_volatile};
    #[cfg(target_arch = "arm")]    #[allow(unused_imports)]
    use libcortex_a9::asm::dmb;

    pub const STATUS_ADDR: *mut u32 = 0xe0004000 as *mut u32;
    pub const STATUS_SIZE: usize = 1;

    #[inline(always)]
    pub unsafe fn status_read() -> u8 {
      read_volatile(STATUS_ADDR) as u8
    }

  }

  pub const UART_INTERRUPT: u32 = 0;
  pub const TIMER0_INTERRUPT: u32 = 1;
  pub const ETHMAC_INTERRUPT: u32 = 2;
  pub const ETHMAC_CORE_PREAMBLE_CRC: u32 = 1;
  pub const ETHMAC_RX_SLOTS: u32 = 4;
  pub const ETHMAC_TX_SLOTS: u32 = 4;
  pub const ETHMAC_SLOT_SIZE: u32 = 2048;
  pub const CONFIG_CLOCK_FREQUENCY: u32 = 125000000;
  pub const CONFIG_DATA_WIDTH_BYTES: u32 = 8;
  pub const CONFIG_DRTIO_ROLE: &'static str = "standalone";
  pub const CONFIG_HAS_RTIO_LOG: u32 = 1;
  pub const CONFIG_HAS_SI5324: u32 = 1;
  pub const CONFIG_HW_REV: &'static str = "v2.0";
  pub const CONFIG_I2C_BUS_COUNT: u32 = 1;
  pub const CONFIG_IDENTIFIER_STR: &'static str = "9.0+unknown.beta;testbed";
  pub const CONFIG_L2_SIZE: u32 = 131072;
  pub const CONFIG_RTIO_FREQUENCY: &'static str = "125.0";
  pub const CONFIG_RTIO_LOG_CHANNEL: u32 = 37;
  pub const CONFIG_SI5324_SOFT_RESET: u32 = 1;
  pub const CONFIG_SOC_PLATFORM: &'static str = "kasli";
  pub const CONFIG_SPIFLASH_PAGE_SIZE: u32 = 256;
  pub const CONFIG_SPIFLASH_SECTOR_SIZE: u32 = 65536;
  pub const CONFIG_KERNEL_HAS_CRI_CON: u32 = 1;
  pub const CONFIG_KERNEL_HAS_RTIO: u32 = 1;
  pub const CONFIG_KERNEL_HAS_RTIO_DMA: u32 = 1;
}
