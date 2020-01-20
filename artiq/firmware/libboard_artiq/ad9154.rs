use board_misoc::{csr, clock};
use ad9154_reg;

fn spi_setup(dacno: u8) {
    unsafe {
        while csr::converter_spi::idle_read() == 0 {}
        csr::converter_spi::offline_write(0);
        csr::converter_spi::end_write(1);
        csr::converter_spi::cs_polarity_write(0b0001);
        csr::converter_spi::clk_polarity_write(0);
        csr::converter_spi::clk_phase_write(0);
        csr::converter_spi::lsb_first_write(0);
        csr::converter_spi::half_duplex_write(0);
        csr::converter_spi::length_write(24 - 1);
        csr::converter_spi::div_write(16 - 2);
        csr::converter_spi::cs_write(1 << (csr::CONFIG_CONVERTER_SPI_FIRST_AD9154_CS + dacno as u32));
    }
}

fn write(addr: u16, data: u8) {
    unsafe {
        while csr::converter_spi::writable_read() == 0 {}
        csr::converter_spi::data_write(
            ((addr as u32) << 16) | ((data as u32) << 8));
    }
}

fn read(addr: u16) -> u8 {
    unsafe {
        write((1 << 15) | addr, 0);
        while csr::converter_spi::writable_read() == 0 {}
        csr::converter_spi::data_read() as u8
    }
}

// ad9154 mode 1
// linerate 5Gbps or 6Gbps
// deviceclock_fpga 125MHz or 150MHz
// deviceclock_dac 500MHz or 600MHz

struct JESDSettings {
    did: u8,
    bid: u8,

    l: u8,  // lanes
    m: u8,  // converters
    n: u8,  // bits/converter
    np: u8, // bits/sample

    f: u8,  // octets/(lane and frame)
    s: u8,  // samples/(converter and frame)
    k: u8,  // frames/multiframe
    cs: u8, // control bits/sample

    subclassv: u8,
    jesdv: u8
}

fn jesd_checksum(settings: &JESDSettings) -> u8 {
    let mut r: u8 = 0;
    for field in [
        settings.did,
        settings.bid,
        settings.l - 1,
        settings.f - 1,
        settings.k - 1,
        settings.m - 1,
        settings.n - 1,
        settings.cs,
        settings.np - 1,
        settings.subclassv,
        settings.s - 1,
        settings.jesdv,
    ].iter() {
        r = r.overflowing_add(*field).0;
    }
    r
}

const JESD_SETTINGS: JESDSettings = JESDSettings {
    did: 0x5a,
    bid: 0x5,

    l: 8,
    m: 4,
    n: 16,
    np: 16,
    f: 2,
    s: 2,
    k: 16,
    cs: 0,

    subclassv: 1,
    jesdv: 1
};

pub fn reset_and_detect(dacno: u8) -> Result<(), &'static str> {
    spi_setup(dacno);
    // reset
    write(ad9154_reg::SPI_INTFCONFA,
            1*ad9154_reg::SOFTRESET_M | 1*ad9154_reg::SOFTRESET |
            0*ad9154_reg::LSBFIRST_M | 0*ad9154_reg::LSBFIRST |
            0*ad9154_reg::ADDRINC_M | 0*ad9154_reg::ADDRINC |
            1*ad9154_reg::SDOACTIVE_M | 1*ad9154_reg::SDOACTIVE);
    clock::spin_us(100);
    write(ad9154_reg::SPI_INTFCONFA,
            0*ad9154_reg::SOFTRESET_M | 0*ad9154_reg::SOFTRESET |
            0*ad9154_reg::LSBFIRST_M | 0*ad9154_reg::LSBFIRST |
            0*ad9154_reg::ADDRINC_M | 0*ad9154_reg::ADDRINC |
            1*ad9154_reg::SDOACTIVE_M | 1*ad9154_reg::SDOACTIVE);
    clock::spin_us(100);
    if (read(ad9154_reg::PRODIDH) as u16) << 8 | (read(ad9154_reg::PRODIDL) as u16) != 0x9154 {
        return Err("invalid AD9154 identification");
    } else {
        info!("AD9154-{} found", dacno);
    }
    Ok(())
}

pub fn setup(dacno: u8, linerate: u64) -> Result<(), &'static str> {
    spi_setup(dacno);
    info!("AD9154-{} initializing...", dacno);
    write(ad9154_reg::PWRCNTRL0,
            0*ad9154_reg::PD_DAC0 | 0*ad9154_reg::PD_DAC1 |
            0*ad9154_reg::PD_DAC2 | 0*ad9154_reg::PD_DAC3 |
            0*ad9154_reg::PD_BG);
    clock::spin_us(100);
    write(ad9154_reg::TXENMASK1, 0*ad9154_reg::DACA_MASK |
            0*ad9154_reg::DACB_MASK); // DAC PD not controlled by TXEN pins
    write(ad9154_reg::PWRCNTRL3, 1*ad9154_reg::ENA_SPI_TXEN |
            1*ad9154_reg::SPI_TXEN);
    write(ad9154_reg::CLKCFG0,
            0*ad9154_reg::REF_CLKDIV_EN | 1*ad9154_reg::RF_SYNC_EN |
            1*ad9154_reg::DUTY_EN | 0*ad9154_reg::PD_CLK_REC |
            0*ad9154_reg::PD_SERDES_PCLK | 0*ad9154_reg::PD_CLK_DIG |
            0*ad9154_reg::PD_CLK23 | 0*ad9154_reg::PD_CLK01);
    write(ad9154_reg::DACPLLCNTRL,
            0*ad9154_reg::ENABLE_DACPLL | 0*ad9154_reg::RECAL_DACPLL);
    write(ad9154_reg::SYSREF_ACTRL0, // jesd204b subclass 1
            0*ad9154_reg::HYS_CNTRL1 | 0*ad9154_reg::SYSREF_RISE |
            0*ad9154_reg::HYS_ON | 0*ad9154_reg::PD_SYSREF_BUFFER);

    write(ad9154_reg::DEVICE_CONFIG_REG_0, 0x8b); // magic
    write(ad9154_reg::DEVICE_CONFIG_REG_1, 0x01); // magic
    write(ad9154_reg::DEVICE_CONFIG_REG_2, 0x01); // magic

    write(ad9154_reg::SPI_PAGEINDX, 0x3); // A and B dual

    write(ad9154_reg::INTERP_MODE, 0x03); // 4x
    write(ad9154_reg::MIX_MODE, 0);
    write(ad9154_reg::DATA_FORMAT, 0*ad9154_reg::BINARY_FORMAT); // s16
    write(ad9154_reg::DATAPATH_CTRL,
            0*ad9154_reg::I_TO_Q | 0*ad9154_reg::SEL_SIDEBAND |
            0*ad9154_reg::MODULATION_TYPE | 0*ad9154_reg::PHASE_ADJ_ENABLE |
            1*ad9154_reg::DIG_GAIN_ENABLE | 0*ad9154_reg::INVSINC_ENABLE);
    write(ad9154_reg::IDAC_DIG_GAIN0, 0x00);
    write(ad9154_reg::IDAC_DIG_GAIN1, 0x8);
    write(ad9154_reg::QDAC_DIG_GAIN0, 0x00);
    write(ad9154_reg::QDAC_DIG_GAIN1, 0x8);
    write(ad9154_reg::DC_OFFSET_CTRL, 0);
    write(ad9154_reg::IPATH_DC_OFFSET_1PART0, 0x00);
    write(ad9154_reg::IPATH_DC_OFFSET_1PART1, 0x00);
    write(ad9154_reg::IPATH_DC_OFFSET_2PART, 0x00);
    write(ad9154_reg::QPATH_DC_OFFSET_1PART0, 0x00);
    write(ad9154_reg::QPATH_DC_OFFSET_1PART1, 0x00);
    write(ad9154_reg::QPATH_DC_OFFSET_2PART, 0x00);
    write(ad9154_reg::PHASE_ADJ0, 0);
    write(ad9154_reg::PHASE_ADJ1, 0);
    write(ad9154_reg::GROUP_DLY, 0x8*ad9154_reg::COARSE_GROUP_DELAY |
            0x8*ad9154_reg::GROUP_DELAY_RESERVED);
    write(ad9154_reg::GROUPDELAY_COMP_BYP,
            1*ad9154_reg::GROUPCOMP_BYPQ |
            1*ad9154_reg::GROUPCOMP_BYPI);
    write(ad9154_reg::GROUPDELAY_COMP_I, 0);
    write(ad9154_reg::GROUPDELAY_COMP_Q, 0);
    write(ad9154_reg::PDP_AVG_TIME, 0*ad9154_reg::PDP_ENABLE);

    write(ad9154_reg::MASTER_PD, 0);
    write(ad9154_reg::PHY_PD, 0x00); // lanes 0-7 enabled
    write(ad9154_reg::GENERIC_PD,
            0*ad9154_reg::PD_SYNCOUT0B |
            1*ad9154_reg::PD_SYNCOUT1B);
    write(ad9154_reg::GENERAL_JRX_CTRL_0,
            0x0*ad9154_reg::LINK_EN | 0*ad9154_reg::LINK_PAGE |
            0*ad9154_reg::LINK_MODE | 0*ad9154_reg::CHECKSUM_MODE);
    write(ad9154_reg::ILS_DID, JESD_SETTINGS.did);
    write(ad9154_reg::ILS_BID, JESD_SETTINGS.bid);
    write(ad9154_reg::ILS_LID0, 0x00); // lane id
    write(ad9154_reg::ILS_SCR_L,
            (JESD_SETTINGS.l - 1)*ad9154_reg::L_1 |
            1*ad9154_reg::SCR);
    write(ad9154_reg::ILS_F, JESD_SETTINGS.f - 1);
    write(ad9154_reg::ILS_K, JESD_SETTINGS.k - 1);
    write(ad9154_reg::ILS_M, JESD_SETTINGS.m - 1);
    write(ad9154_reg::ILS_CS_N,
            (JESD_SETTINGS.n - 1)*ad9154_reg::N_1 |
            0*ad9154_reg::CS);
    write(ad9154_reg::ILS_NP,
            (JESD_SETTINGS.np - 1)*ad9154_reg::NP_1 |
            JESD_SETTINGS.subclassv*ad9154_reg::SUBCLASSV);
    write(ad9154_reg::ILS_S,
            (JESD_SETTINGS.s - 1)*ad9154_reg::S_1 |
            JESD_SETTINGS.jesdv*ad9154_reg::JESDV);
    write(ad9154_reg::ILS_HD_CF,
            0*ad9154_reg::HD | 0*ad9154_reg::CF);
    write(ad9154_reg::ILS_CHECKSUM, jesd_checksum(&JESD_SETTINGS));
    write(ad9154_reg::LANEDESKEW, 0xff);
    for i in 0..8 {
        write(ad9154_reg::BADDISPARITY, 0*ad9154_reg::RST_IRQ_DIS |
                0*ad9154_reg::DISABLE_ERR_CNTR_DIS |
                1*ad9154_reg::RST_ERR_CNTR_DIS | i*ad9154_reg::LANE_ADDR_DIS);
        write(ad9154_reg::BADDISPARITY, 0*ad9154_reg::RST_IRQ_DIS |
                0*ad9154_reg::DISABLE_ERR_CNTR_DIS |
                0*ad9154_reg::RST_ERR_CNTR_DIS | i*ad9154_reg::LANE_ADDR_DIS);
        write(ad9154_reg::NIT_W, 0*ad9154_reg::RST_IRQ_NIT |
                0*ad9154_reg::DISABLE_ERR_CNTR_NIT |
                1*ad9154_reg::RST_ERR_CNTR_NIT | i*ad9154_reg::LANE_ADDR_NIT);
        write(ad9154_reg::NIT_W, 0*ad9154_reg::RST_IRQ_NIT |
                0*ad9154_reg::DISABLE_ERR_CNTR_NIT |
                0*ad9154_reg::RST_ERR_CNTR_NIT | i*ad9154_reg::LANE_ADDR_NIT);
        write(ad9154_reg::UNEXPECTEDCONTROL_W, 0*ad9154_reg::RST_IRQ_UCC |
                0*ad9154_reg::DISABLE_ERR_CNTR_UCC |
                1*ad9154_reg::RST_ERR_CNTR_UCC | i*ad9154_reg::LANE_ADDR_UCC);
        write(ad9154_reg::BADDISPARITY, 0*ad9154_reg::RST_IRQ_UCC |
                0*ad9154_reg::DISABLE_ERR_CNTR_UCC |
                0*ad9154_reg::RST_ERR_CNTR_UCC | i*ad9154_reg::LANE_ADDR_UCC);
    }
    write(ad9154_reg::CTRLREG1, JESD_SETTINGS.f);
    write(ad9154_reg::CTRLREG2, 0*ad9154_reg::ILAS_MODE |
            0*ad9154_reg::THRESHOLD_MASK_EN);
    write(ad9154_reg::KVAL, 1); // *4*K multiframes during ILAS
    write(ad9154_reg::LANEENABLE, 0xff); // CGS _after_ this

    write(ad9154_reg::TERM_BLK1_CTRLREG0, 1);
    write(ad9154_reg::TERM_BLK2_CTRLREG0, 1);
    write(ad9154_reg::SERDES_SPI_REG, 1);
    if linerate > 5_650_000_000 {
        write(ad9154_reg::CDR_OPERATING_MODE_REG_0,
                0*ad9154_reg::CDR_OVERSAMP | 0x2*ad9154_reg::CDR_RESERVED |
                1*ad9154_reg::ENHALFRATE);
    } else {
        write(ad9154_reg::CDR_OPERATING_MODE_REG_0,
                0*ad9154_reg::CDR_OVERSAMP | 0x2*ad9154_reg::CDR_RESERVED |
                0*ad9154_reg::ENHALFRATE);
    }
    write(ad9154_reg::CDR_RESET, 0);
    write(ad9154_reg::CDR_RESET, 1);
    if linerate > 5_650_000_000 {
        write(ad9154_reg::REF_CLK_DIVIDER_LDO,
            0*ad9154_reg::SPI_CDR_OVERSAMP |
            1*ad9154_reg::SPI_LDO_BYPASS_FILT |
            0*ad9154_reg::SPI_LDO_REF_SEL);
    } else {
        write(ad9154_reg::REF_CLK_DIVIDER_LDO,
            1*ad9154_reg::SPI_CDR_OVERSAMP |
            1*ad9154_reg::SPI_LDO_BYPASS_FILT |
            0*ad9154_reg::SPI_LDO_REF_SEL);
    }
    write(ad9154_reg::LDO_FILTER_1, 0x62); // magic
    write(ad9154_reg::LDO_FILTER_2, 0xc9); // magic
    write(ad9154_reg::LDO_FILTER_3, 0x0e); // magic
    write(ad9154_reg::CP_CURRENT_SPI,
            0x12*ad9154_reg::SPI_CP_CURRENT |
            0*ad9154_reg::SPI_SERDES_LOGEN_POWER_MODE);
    write(ad9154_reg::VCO_LDO, 0x7b); // magic
    write(ad9154_reg::PLL_RD_REG,
            0*ad9154_reg::SPI_SERDES_LOGEN_PD_CORE |
            0*ad9154_reg::SPI_SERDES_LDO_PD | 0*ad9154_reg::SPI_SYN_PD |
            0*ad9154_reg::SPI_VCO_PD_ALC | 0*ad9154_reg::SPI_VCO_PD_PTAT |
            0*ad9154_reg::SPI_VCO_PD);
    write(ad9154_reg::ALC_VARACTOR,
            0x9*ad9154_reg::SPI_VCO_VARACTOR |
            0x8*ad9154_reg::SPI_INIT_ALC_VALUE);
    write(ad9154_reg::VCO_OUTPUT,
            0xc*ad9154_reg::SPI_VCO_OUTPUT_LEVEL |
            0x4*ad9154_reg::SPI_VCO_OUTPUT_RESERVED);
    write(ad9154_reg::CP_CONFIG,
            0*ad9154_reg::SPI_CP_TEST |
            1*ad9154_reg::SPI_CP_CAL_EN |
            0*ad9154_reg::SPI_CP_FORCE_CALBITS |
            0*ad9154_reg::SPI_CP_OFFSET_OFF |
            1*ad9154_reg::SPI_CP_ENABLE_MACHINE |
            0*ad9154_reg::SPI_CP_DITHER_MODE |
            0*ad9154_reg::SPI_CP_HALF_VCO_CAL_CLK);
    write(ad9154_reg::VCO_BIAS_1,
            0x3*ad9154_reg::SPI_VCO_BIAS_REF |
            0x3*ad9154_reg::SPI_VCO_BIAS_TCF);
    write(ad9154_reg::VCO_BIAS_2,
            0x1*ad9154_reg::SPI_PRESCALE_BIAS |
            1*ad9154_reg::SPI_LAST_ALC_EN |
            0x1*ad9154_reg::SPI_PRESCALE_BYPASS_R |
            0*ad9154_reg::SPI_VCO_COMP_BYPASS_BIASR |
            0*ad9154_reg::SPI_VCO_BYPASS_DAC_R);
    write(ad9154_reg::VCO_PD_OVERRIDES,
            0*ad9154_reg::SPI_VCO_PD_OVERRIDE_VCO_BUF |
            1*ad9154_reg::SPI_VCO_PD_OVERRIDE_CAL_TCF |
            0*ad9154_reg::SPI_VCO_PD_OVERRIDE_VAR_REF_TCF |
            0*ad9154_reg::SPI_VCO_PD_OVERRIDE_VAR_REF);
    write(ad9154_reg::VCO_CAL,
            0x2*ad9154_reg::SPI_FB_CLOCK_ADV |
            0x3*ad9154_reg::SPI_VCO_CAL_COUNT |
            0*ad9154_reg::SPI_VCO_CAL_ALC_WAIT |
            1*ad9154_reg::SPI_VCO_CAL_EN);
    write(ad9154_reg::CP_LEVEL_DETECT,
            0x2*ad9154_reg::SPI_CP_LEVEL_THRESHOLD_HIGH |
            0x5*ad9154_reg::SPI_CP_LEVEL_THRESHOLD_LOW |
            0*ad9154_reg::SPI_CP_LEVEL_DET_PD);
    write(ad9154_reg::VCO_VARACTOR_CTRL_0,
            0xe*ad9154_reg::SPI_VCO_VARACTOR_OFFSET | 
            0x7*ad9154_reg::SPI_VCO_VARACTOR_REF_TCF);
    write(ad9154_reg::VCO_VARACTOR_CTRL_1,
            0x6*ad9154_reg::SPI_VCO_VARACTOR_REF);
    // ensure link is txing
    //write(ad9154_reg::SERDESPLL_ENABLE_CNTRL,
    //        1*ad9154_reg::ENABLE_SERDESPLL | 1*ad9154_reg::RECAL_SERDESPLL)
    write(ad9154_reg::SERDESPLL_ENABLE_CNTRL,
            1*ad9154_reg::ENABLE_SERDESPLL | 0*ad9154_reg::RECAL_SERDESPLL);
    let t = clock::get_ms();
    while read(ad9154_reg::PLL_STATUS) & ad9154_reg::SERDES_PLL_LOCK_RB == 0 {
        if clock::get_ms() > t + 200 {
            return Err("SERDES PLL lock timeout");
        }
    }

    write(ad9154_reg::EQ_BIAS_REG, 0x22*ad9154_reg::EQ_BIAS_RESERVED |
            1*ad9154_reg::EQ_POWER_MODE);

    write(ad9154_reg::GENERAL_JRX_CTRL_1, 1); // subclass 1
    write(ad9154_reg::LMFC_DELAY_0, 0);
    write(ad9154_reg::LMFC_DELAY_1, 0);
    write(ad9154_reg::LMFC_VAR_0, 0x0a); // receive buffer delay
    write(ad9154_reg::LMFC_VAR_1, 0x0a);
    write(ad9154_reg::SYNC_ERRWINDOW, 0); // +- 1/2 DAC clock
    // datasheet seems to say ENABLE and ARM should be separate steps,
    // so enable now so it can be armed in sync().
    write(ad9154_reg::SYNC_CONTROL,
        0x1*ad9154_reg::SYNCMODE | 1*ad9154_reg::SYNCENABLE |
        0*ad9154_reg::SYNCARM | 0*ad9154_reg::SYNCCLRSTKY);

    write(ad9154_reg::XBAR_LN_0_1,
            0*ad9154_reg::LOGICAL_LANE0_SRC | 1*ad9154_reg::LOGICAL_LANE1_SRC);
    write(ad9154_reg::XBAR_LN_2_3,
            2*ad9154_reg::LOGICAL_LANE2_SRC | 3*ad9154_reg::LOGICAL_LANE3_SRC);
    write(ad9154_reg::XBAR_LN_4_5,
            4*ad9154_reg::LOGICAL_LANE4_SRC | 5*ad9154_reg::LOGICAL_LANE5_SRC);
    write(ad9154_reg::XBAR_LN_6_7,
            6*ad9154_reg::LOGICAL_LANE6_SRC | 7*ad9154_reg::LOGICAL_LANE7_SRC);
    write(ad9154_reg::JESD_BIT_INVERSE_CTRL, 0x00);
    write(ad9154_reg::GENERAL_JRX_CTRL_0,
            0x1*ad9154_reg::LINK_EN | 0*ad9154_reg::LINK_PAGE |
            0*ad9154_reg::LINK_MODE | 0*ad9154_reg::CHECKSUM_MODE);
    info!("  ...done");
    Ok(())
}

pub fn status(dacno: u8) {
    spi_setup(dacno);
    info!("Printing status of AD9154-{}", dacno);
    info!("PRODID: 0x{:04x}", (read(ad9154_reg::PRODIDH) as u16) << 8 | (read(ad9154_reg::PRODIDL) as u16));
    info!("SERDES_PLL_LOCK: {}",
        (read(ad9154_reg::PLL_STATUS) & ad9154_reg::SERDES_PLL_LOCK_RB));
    info!("");
    info!("CODEGRPSYNC: 0x{:02x}", read(ad9154_reg::CODEGRPSYNCFLG));
    info!("FRAMESYNC: 0x{:02x}", read(ad9154_reg::FRAMESYNCFLG));
    info!("GOODCHECKSUM: 0x{:02x}", read(ad9154_reg::GOODCHKSUMFLG));
    info!("INITLANESYNC: 0x{:02x}", read(ad9154_reg::INITLANESYNCFLG));
    info!("");
    info!("DID_REG: 0x{:02x}", read(ad9154_reg::DID_REG));
    info!("BID_REG: 0x{:02x}", read(ad9154_reg::BID_REG));
    info!("SCR_L_REG: 0x{:02x}", read(ad9154_reg::SCR_L_REG));
    info!("F_REG: 0x{:02x}", read(ad9154_reg::F_REG));
    info!("K_REG: 0x{:02x}", read(ad9154_reg::K_REG));
    info!("M_REG: 0x{:02x}", read(ad9154_reg::M_REG));
    info!("CS_N_REG: 0x{:02x}", read(ad9154_reg::CS_N_REG));
    info!("NP_REG: 0x{:02x}", read(ad9154_reg::NP_REG));
    info!("S_REG: 0x{:02x}", read(ad9154_reg::S_REG));
    info!("HD_CF_REG: 0x{:02x}", read(ad9154_reg::HD_CF_REG));
    info!("RES1_REG: 0x{:02x}", read(ad9154_reg::RES1_REG));
    info!("RES2_REG: 0x{:02x}", read(ad9154_reg::RES2_REG));
    info!("LIDx_REG: 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x}",
         read(ad9154_reg::LID0_REG),
         read(ad9154_reg::LID1_REG),
         read(ad9154_reg::LID2_REG),
         read(ad9154_reg::LID3_REG),
         read(ad9154_reg::LID4_REG),
         read(ad9154_reg::LID5_REG),
         read(ad9154_reg::LID6_REG),
         read(ad9154_reg::LID7_REG));
    info!("CHECKSUMx_REG: 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x}",
        read(ad9154_reg::CHECKSUM0_REG),
        read(ad9154_reg::CHECKSUM1_REG),
        read(ad9154_reg::CHECKSUM2_REG),
        read(ad9154_reg::CHECKSUM3_REG),
        read(ad9154_reg::CHECKSUM4_REG),
        read(ad9154_reg::CHECKSUM5_REG),
        read(ad9154_reg::CHECKSUM6_REG),
        read(ad9154_reg::CHECKSUM7_REG));
    info!("COMPSUMx_REG: 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x} 0x{:02x}",
        read(ad9154_reg::COMPSUM0_REG),
        read(ad9154_reg::COMPSUM1_REG),
        read(ad9154_reg::COMPSUM2_REG),
        read(ad9154_reg::COMPSUM3_REG),
        read(ad9154_reg::COMPSUM4_REG),
        read(ad9154_reg::COMPSUM5_REG),
        read(ad9154_reg::COMPSUM6_REG),
        read(ad9154_reg::COMPSUM7_REG));
    info!("BADDISPARITY: 0x{:02x}", read(ad9154_reg::BADDISPARITY));
    info!("NITDISPARITY: 0x{:02x}", read(ad9154_reg::NIT_W));
}

pub fn prbs(dacno: u8) -> Result<(), &'static str> {
    let mut prbs_errors: u32 = 0;
    spi_setup(dacno);

    /* follow phy prbs testing (p58 of ad9154 datasheet) */
    info!("AD9154-{} running PRBS test...", dacno);

    /* step 2: select prbs mode */
    write(ad9154_reg::PHY_PRBS_TEST_CTRL,
        0b00*ad9154_reg::PHY_PRBS_PAT_SEL);

    /* step 3: enable test for all lanes */
    write(ad9154_reg::PHY_PRBS_TEST_EN, 0xff);

    /* step 4: reset */
    write(ad9154_reg::PHY_PRBS_TEST_CTRL,
        0b00*ad9154_reg::PHY_PRBS_PAT_SEL |
        1*ad9154_reg::PHY_TEST_RESET);
    write(ad9154_reg::PHY_PRBS_TEST_CTRL,
        0b00*ad9154_reg::PHY_PRBS_PAT_SEL);

    /* step 5: prbs threshold */
    write(ad9154_reg::PHY_PRBS_TEST_THRESHOLD_LOBITS, 0);
    write(ad9154_reg::PHY_PRBS_TEST_THRESHOLD_MIDBITS, 0);
    write(ad9154_reg::PHY_PRBS_TEST_THRESHOLD_HIBITS, 0);

    /* step 6: start */
    write(ad9154_reg::PHY_PRBS_TEST_CTRL,
        0b00*ad9154_reg::PHY_PRBS_PAT_SEL);
    write(ad9154_reg::PHY_PRBS_TEST_CTRL,
        0b00*ad9154_reg::PHY_PRBS_PAT_SEL |
        1*ad9154_reg::PHY_TEST_START);

    /* step 7: wait 500 ms */
    clock::spin_us(500000);

    /* step 8 : stop */
    write(ad9154_reg::PHY_PRBS_TEST_CTRL,
        0b00*ad9154_reg::PHY_PRBS_PAT_SEL);

    for i in 0..8 {
        /* step 9.a: select src err */
        write(ad9154_reg::PHY_PRBS_TEST_CTRL,
        i*ad9154_reg::PHY_SRC_ERR_CNT);
        /* step 9.b: retrieve number of errors */
        let lane_errors =  (read(ad9154_reg::PHY_PRBS_TEST_ERRCNT_LOBITS) as u32) |
                          ((read(ad9154_reg::PHY_PRBS_TEST_ERRCNT_MIDBITS) as u32) << 8) |
                          ((read(ad9154_reg::PHY_PRBS_TEST_ERRCNT_HIBITS) as u32) << 16);
        if lane_errors > 0 {
            warn!("  PRBS errors on lane{}: {:06x}", i, lane_errors);
        }
        prbs_errors += lane_errors
    }

    if prbs_errors > 0 {
        return Err("PRBS failed")
    }
    info!("  ...passed");
    Ok(())
}

pub fn stpl(dacno: u8, m: u8, s: u8) -> Result<(), &'static str> {
    spi_setup(dacno);

    info!("AD9154-{} running STPL test...", dacno);

    fn prng(seed: u32) -> u32 {
        return ((seed + 1)*0x31415979 + 1) & 0xffff;
    }

    for i in 0..m {
        let mut data: u32;
        let mut errors: u8 = 0;
        for j in 0..s {
            /* select converter */
            write(ad9154_reg::SHORT_TPL_TEST_0,
                0b0*ad9154_reg::SHORT_TPL_TEST_EN |
                0b0*ad9154_reg::SHORT_TPL_TEST_RESET |
                i*ad9154_reg::SHORT_TPL_DAC_SEL |
                j*ad9154_reg::SHORT_TPL_SP_SEL);

            /* set expected value */
            data = prng(((i as u32) << 8) | (j as u32));
            write(ad9154_reg::SHORT_TPL_TEST_1, (data & 0x00ff) as u8);
            write(ad9154_reg::SHORT_TPL_TEST_2, ((data & 0xff00) >> 8) as u8);

            /* enable stpl */
            write(ad9154_reg::SHORT_TPL_TEST_0,
                0b1*ad9154_reg::SHORT_TPL_TEST_EN |
                0b0*ad9154_reg::SHORT_TPL_TEST_RESET |
                i*ad9154_reg::SHORT_TPL_DAC_SEL |
                j*ad9154_reg::SHORT_TPL_SP_SEL);

            /* reset stpl */
            write(ad9154_reg::SHORT_TPL_TEST_0,
                0b1*ad9154_reg::SHORT_TPL_TEST_EN |
                0b1*ad9154_reg::SHORT_TPL_TEST_RESET |
                i*ad9154_reg::SHORT_TPL_DAC_SEL |
                j*ad9154_reg::SHORT_TPL_SP_SEL);

            /* release reset stpl */
            write(ad9154_reg::SHORT_TPL_TEST_0,
                0b1*ad9154_reg::SHORT_TPL_TEST_EN |
                0b0*ad9154_reg::SHORT_TPL_TEST_RESET |
                i*ad9154_reg::SHORT_TPL_DAC_SEL |
                j*ad9154_reg::SHORT_TPL_SP_SEL);
            errors += read(ad9154_reg::SHORT_TPL_TEST_3);
        }
        info!("  c{} errors: {}", i, errors);
        if errors > 0 {
            return Err("STPL failed")
        }
    }

    info!("  ...passed");
    Ok(())
}

pub fn sync(dacno: u8) -> Result<bool, &'static str> {
    spi_setup(dacno);

    write(ad9154_reg::SYNC_CONTROL,
        0x1*ad9154_reg::SYNCMODE | 1*ad9154_reg::SYNCENABLE |
        1*ad9154_reg::SYNCARM | 1*ad9154_reg::SYNCCLRSTKY);
    clock::spin_us(1000); // ensure at least one sysref edge
    let sync_status = read(ad9154_reg::SYNC_STATUS);

    if sync_status & ad9154_reg::SYNC_BUSY != 0 {
        return Err("sync logic busy");
    }
    if sync_status & ad9154_reg::SYNC_LOCK == 0 {
        return Err("no sync lock");
    }
    if sync_status & ad9154_reg::SYNC_TRIP == 0 {
        return Err("no sysref edge");
    }
    let realign_occured = sync_status & ad9154_reg::SYNC_ROTATE != 0;
    Ok(realign_occured)
}
