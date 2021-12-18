use super::{csr, clock};

// Sayma MMC SSP1 configuration:
//
// References:
// (i) Sayma MMC FPGA SPI port initialisation: https://github.com/sinara-hw/openMMC/blob/sayma-devel/modules/fpga_spi.c
// (ii) Sayma MMC configuration: https://github.com/sinara-hw/openMMC/blob/sayma-devel/port/ucontroller/nxp/lpc17xx/lpc17_ssp.c::ssp_init()
// (iii) openMMC SSP driver: https://github.com/sinara-hw/openMMC/blob/sayma-devel/port/ucontroller/nxp/lpc17xx/lpcopen/src/ssp_17xx_40xx.c)
//
// * Data Size Select <DSS>: 8-bit transfer (see FPGA_SPI_FRAME_SIZE)
// * Frame Format <FRF>: SPI (see lpc17_ssp.c::ssp_init())
// * Clock Out Polarity <CPOL>: CPOL=0 (CLK is low when idling) (see lpc17_ssp.c::ssp_init())
// * Clock Out Phase <CPHA>: CPHA=0 (data is captured on leading edge) (see lpc17_ssp.c::ssp_init())
//   * CPOL=0, CPHA=0 ==> data is captured at rising edge
// * Clock Frequency: 10000000 == 10 MHz (see FPGA_SPI_BITRATE)

// TODO: consider making a generic SPI receiver for customisable configuration

static mut PREV_CS_N: bool = true;      // High when idling
static mut PREV_CLK: bool = false;      // Low when idling

// List of expected values
// openMMC modules/fpga_spi.h
const WR_COMMAND: u8 = 0x80;
const ADDR_HEADER: u16 = 0x0005;    // "Data Valid Byte"
const DATA_HEADER: u32 = 0x55555555;
const FPGA_UPDATE_RATE: u64 = 5000; // Delay interval between broadcast

// Layout of MMC-to-FPGA data
// (see openMMC modules/fpga_spi.h board_diagnostic_t)
// cardID: u32 array of length 4
const ADDR_CARD_ID_0: u16 = 0;      // cardID[0]: bits[31:24] = EUI48 byte 3
                                    //            bits[23:16] = EUI48 byte 2 (0x3D)
                                    //            bits[15: 8] = EUI48 byte 1 (0xC2)
                                    //            bits[ 7: 0] = EUI48 byte 0 (0xFC)
const ADDR_CARD_ID_1: u16 = 1;      // cardID[1]: bits[47:40] = EUI48 byte 5
                                    //            bits[39:32] = EUI48 byte 4
const ADDR_SLOT_ID: u16 = 16;       // Note: currently unused by FPGA
const ADDR_IPMI_ADDR: u16 = 20;     // Note: currently unused by FPGA
const ADDR_DATA_VALID: u16 = 24;    // Note: currently unused by FPGA
const ADDR_SENSOR: u16 = 28;        // u32 array of length 21; see openMMC modules/sdr.h NUM_SENSOR
                                    // Note: currently unused by FPGA
const ADDR_FMC_SLOT: u16 = 112;     // Note: currently unused by FPGA


fn cs_n() -> bool {
    unsafe { csr::mmcspi::cs_n_in_read() == 1 }
}

fn detect_cs_n_rise(timeout_us: u64) -> bool {
    let start = clock::get_us();
    while clock::get_us() - start < timeout_us {
        if cs_n() && unsafe { !PREV_CS_N } {
            unsafe { PREV_CS_N = true; }
            return true;
        }
    }
    false
}

fn detect_cs_n_fall(timeout_us: u64) -> bool {
    let start = clock::get_us();
    while clock::get_us() - start < timeout_us {
        if !cs_n() && unsafe { PREV_CS_N } {
            unsafe { PREV_CS_N = false; }
            return true;
        }
    }
    false
}

fn clk() -> bool {
    unsafe { csr::mmcspi::clk_in_read() == 1 }
}

fn detect_clk_rise(timeout_us: u64) -> bool {
    let start = clock::get_us();
    while clock::get_us() - start < timeout_us {
        if clk() && unsafe { !PREV_CLK } {
            unsafe { PREV_CLK = true; }
            return true;
        }
    }
    false
}

fn detect_clk_fall(timeout_us: u64) -> bool {
    let start = clock::get_us();
    while clock::get_us() - start < timeout_us {
        if !clk() && unsafe { PREV_CLK } {
            unsafe { PREV_CLK = false; }
            return true;
        }
    }
    false
}

fn mosi() -> u8 {
    unsafe { csr::mmcspi::mosi_in_read() & 1 }
}

/// Detects CS_n assertion and keeps reading until the buffer is full or CS_n is deasserted
/// TODO: Generalise this driver for future possible changes to the MMC SPI master settings
fn read_continuous(buf: &mut [u8], timeout_ms: u64) {
    // Register CS_n and CLK states
    unsafe {
        // Give up if CS_n has already been asserted (we're in the middle of transaction)
        if !cs_n() { return } else { PREV_CS_N = true }
        PREV_CLK = clk();
    }

    // Wait until timeout or CS_n falling edge is detected, which indicates a new transaction
    if !detect_cs_n_fall(timeout_ms * 1000) { return }

    for byte_ind in 0..buf.len() {
        // Read bits from MSB to LSB
        for bit_ind in (0..8).rev() {
            // If CS_n goes high, return to indicate a complete SPI transaction
            if cs_n() { break }
            // Detect and register CLK rising edge
            if !detect_clk_rise(1000) { return }
            // Store the MOSI state as the current bit of the current byte
            if mosi() == 1 {
                buf[byte_ind] |= 1 << bit_ind;
            }
            // Detect and register CLK falling edge
            if !detect_clk_fall(1000) { return }
        }
    }
}

/// Convert bytes to u16 (from big-endian)
fn to_u16(buf: &[u8]) -> u16 {
    let mut value = 0_u16;
    for i in 0..2 {
        value |= (buf[i] as u16) << ((1-i) * 8);
    }
    value
}

/// Convert bytes to u32 (from big-endian)
fn to_u32(buf: &[u8]) -> u32 {
    let mut value = 0_u32;
    for i in 0..4 {
        value |= (buf[i] as u32) << ((3-i) * 8);
    }
    value
}

/// Check if the bytes are the MMC broadcast header
fn is_broadcast_header(buf: &[u8]) -> bool {
    buf.len() == 7 &&
    buf[0] == WR_COMMAND &&
    to_u16(&buf[1..3]) == ADDR_HEADER &&
    to_u32(&buf[3..7]) == DATA_HEADER
}

/// Read the SPI to wait and capture the EUI48, and store it to a u8 array;
/// Returns Ok() to indicate if the data is captured
pub fn read_eui48(buf: &mut [u8]) -> Result<(), ()> {
    assert!(buf.len() >= 6);
    let mut spi_buf = [0_u8; 21];
    let mut is_broadcast = false;

    // Loop 10s to read a continuous byte transaction until the header correspond to the MMC broadcast format
    let start = clock::get_ms();
    while !is_broadcast && clock::get_ms() - start <= 10_000 {
        // Read 21 contiguous bytes in a row, which is broadcast every 5 seconds
        read_continuous(&mut spi_buf, FPGA_UPDATE_RATE + 100);  // +100ms margin
        // Check the header
        is_broadcast = is_broadcast_header(&spi_buf[0..7]);
    }
    // Return Err(()) if no broadcast header is detected
    if !is_broadcast { return Err(()) }
    // Truncate the header to get all data captured
    let data = &spi_buf[7..];

    let (mut eui48_lo_ok, mut eui48_hi_ok) = (false, false);
    for i in 0..data.len()/7 {
        match to_u16(&data[i*7+1..i*7+3]) {
            // EUI48[31:0], big-endian
            ADDR_CARD_ID_0 => {
                for j in 0..4 { buf[j] = data[i*7 + 6-j] }
                eui48_lo_ok = true;
            }
            // EUI48[47:32], big-endian
            ADDR_CARD_ID_1 => {
                for j in 0..2 { buf[4 + j] = data[i*7 + 6-j] }
                eui48_hi_ok = true;
            }
            _ => {}
        }
    }

    match (eui48_lo_ok, eui48_hi_ok) {
        (true, true) => Ok(()),
        // This should never return Err(), unless the broadcast format has changed
        _ => Err(()),
    }
}