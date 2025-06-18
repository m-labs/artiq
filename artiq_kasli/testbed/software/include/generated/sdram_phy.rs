// Include this file as:
//     include!(concat!(env!("BUILDINC_DIRECTORY"), "/generated/sdram_phy.rs"));
#[allow(dead_code)]
pub mod sdram_phy {
    use csr;

    // Since Rust version (approx.) 1.44.0, asm! macro has been updated and replaced
    // by llvm_asm! macro / the new asm! macro.
    //
    // The ARTIQ OpenRisc port is built using version 1.28, so it needs the old macro.
    // At the same time, the RISC-V port uses version 1.51, where the update applies.
    //
    // Both llvm_asm! and the new asm! change the syntax, so the following asm line
    // needs conditional compilation. The cleaner way would be to use cfg_version,
    // but it wasn't available back in version 1.28. We use the target architecture
    // for this purpose instead.

    pub fn spin_cycles(mut cycles: usize) {
        while cycles > 0 {
            unsafe {
                #[cfg(not(target_arch = "or1k"))]
                asm!("");

                #[cfg(target_arch = "or1k")]
                asm!(""::::"volatile")
            }
            cycles -= 1;
        }
    }

    pub const DFII_CONTROL_SEL:     u8 = 0x01;
    pub const DFII_CONTROL_CKE:     u8 = 0x02;
    pub const DFII_CONTROL_ODT:     u8 = 0x04;
    pub const DFII_CONTROL_RESET_N: u8 = 0x08;

    pub const DFII_COMMAND_CS:      u8 = 0x01;
    pub const DFII_COMMAND_WE:      u8 = 0x02;
    pub const DFII_COMMAND_CAS:     u8 = 0x04;
    pub const DFII_COMMAND_RAS:     u8 = 0x08;
    pub const DFII_COMMAND_WRDATA:  u8 = 0x10;
    pub const DFII_COMMAND_RDDATA:  u8 = 0x20;

    pub const DFII_NPHASES: usize = 4;

    
    pub unsafe fn command_p0(cmd: u8) {
        csr::dfii::pi0_command_write(cmd);
        csr::dfii::pi0_command_issue_write(1);
    }
    
    pub unsafe fn command_p1(cmd: u8) {
        csr::dfii::pi1_command_write(cmd);
        csr::dfii::pi1_command_issue_write(1);
    }
    
    pub unsafe fn command_p2(cmd: u8) {
        csr::dfii::pi2_command_write(cmd);
        csr::dfii::pi2_command_issue_write(1);
    }
    
    pub unsafe fn command_p3(cmd: u8) {
        csr::dfii::pi3_command_write(cmd);
        csr::dfii::pi3_command_issue_write(1);
    }
    

    pub unsafe fn dfii_pird_address_write(a: u16) { csr::dfii::pi1_address_write(a) }
    pub unsafe fn dfii_piwr_address_write(a: u16) { csr::dfii::pi2_address_write(a) }

    pub unsafe fn dfii_pird_baddress_write(a: u8) { csr::dfii::pi1_baddress_write(a) }
    pub unsafe fn dfii_piwr_baddress_write(a: u8) { csr::dfii::pi2_baddress_write(a) }

    pub unsafe fn command_prd(cmd: u8) { command_p1(cmd) }
    pub unsafe fn command_pwr(cmd: u8) { command_p2(cmd) }

    pub const DFII_PIX_DATA_SIZE: usize = csr::dfii::PI0_WRDATA_SIZE;

    pub const DFII_PIX_WRDATA_ADDR: [*mut u32; 4] = [
        csr::dfii::PI0_WRDATA_ADDR,
        csr::dfii::PI1_WRDATA_ADDR,
        csr::dfii::PI2_WRDATA_ADDR,
        csr::dfii::PI3_WRDATA_ADDR,
    ];

    pub const DFII_PIX_RDDATA_ADDR: [*mut u32; 4] = [
        csr::dfii::PI0_RDDATA_ADDR,
        csr::dfii::PI1_RDDATA_ADDR,
        csr::dfii::PI2_RDDATA_ADDR,
        csr::dfii::PI3_RDDATA_ADDR,
    ];

    
    pub const DDR3_MR1: u32 = 6;
    

    pub unsafe fn initialize() {
        /* Release reset */
        csr::dfii::pi0_address_write(0x0);
        csr::dfii::pi0_baddress_write(0);
        csr::dfii::control_write(DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
        spin_cycles(50000);
    
        /* Bring CKE high */
        csr::dfii::pi0_address_write(0x0);
        csr::dfii::pi0_baddress_write(0);
        csr::dfii::control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
        spin_cycles(10000);
    
        /* Load Mode Register 2 */
        csr::dfii::pi0_address_write(0x408);
        csr::dfii::pi0_baddress_write(2);
        command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
        
    
        /* Load Mode Register 3 */
        csr::dfii::pi0_address_write(0x0);
        csr::dfii::pi0_baddress_write(3);
        command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
        
    
        /* Load Mode Register 1 */
        csr::dfii::pi0_address_write(0x6);
        csr::dfii::pi0_baddress_write(1);
        command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
        
    
        /* Load Mode Register 0, CL=7, BL=8 */
        csr::dfii::pi0_address_write(0x930);
        csr::dfii::pi0_baddress_write(0);
        command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
        spin_cycles(200);
    
        /* ZQ Calibration */
        csr::dfii::pi0_address_write(0x400);
        csr::dfii::pi0_baddress_write(0);
        command_p0(DFII_COMMAND_WE|DFII_COMMAND_CS);
        spin_cycles(200);
    }
}