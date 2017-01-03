use csr;
use clock;
use ad9154_reg;

fn spi_setup() {
    unsafe {
        csr::converter_spi::offline_write(1);
        csr::converter_spi::cs_polarity_write(0);
        csr::converter_spi::clk_polarity_write(0);
        csr::converter_spi::clk_phase_write(0);
        csr::converter_spi::lsb_first_write(0);
        csr::converter_spi::half_duplex_write(0);
        csr::converter_spi::clk_div_write_write(16);
        csr::converter_spi::clk_div_read_write(16);
        csr::converter_spi::xfer_len_write_write(24);
        csr::converter_spi::xfer_len_read_write(0);
        csr::converter_spi::cs_write(1 << csr::CONFIG_CONVERTER_SPI_DAC_CS);
        csr::converter_spi::offline_write(0);
    }
}

fn write(addr: u16, data: u8) {
    unsafe {
        csr::converter_spi::data_write_write(
            ((addr as u32) << 16) | ((data as u32) << 8));
        while csr::converter_spi::pending_read() != 0 {}
        while csr::converter_spi::active_read() != 0 {}
    }
}

fn read(addr: u16) -> u8 {
    unsafe {
        write((1 << 15) | addr, 0);
        csr::converter_spi::data_read_read() as u8
    }
}

fn jesd_reset(rst: bool) {
    unsafe {
        csr::ad9154::jesd_jreset_write(if rst {1} else {0})
    }
}

fn jesd_enable(en: bool) {
    unsafe {
        csr::ad9154::jesd_control_enable_write(if en {1} else {0})
    }
}

fn jesd_ready() -> bool {
    unsafe {
        csr::ad9154::jesd_control_ready_read() != 0
    }
}

fn jesd_prbs(en: bool) {
    unsafe {
        csr::ad9154::jesd_control_prbs_config_write(if en {1} else {0})
    }
}

fn jesd_stpl(en: bool) {
    unsafe {
        csr::ad9154::jesd_control_stpl_enable_write(if en {1} else {0})
    }
}

fn jesd_jsync() -> bool {
    unsafe {
        csr::ad9154::jesd_jsync_read() != 0
    }
}

// ad9154 mode 2
// external clk=300MHz
// pclock=150MHz
// deviceclock_fpga=150MHz
// deviceclock_dac=300MHz

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

    l: 4,
    m: 4,
    n: 16,
    np: 16,
    f: 2,
    s: 1,
    k: 16,
    cs: 1,

    subclassv: 1,
    jesdv: 1
};

fn dac_setup() -> Result<(), &'static str> {
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
        return Err("AD9154 not found")
    }

    write(ad9154_reg::PWRCNTRL0,
            0*ad9154_reg::PD_DAC0 | 0*ad9154_reg::PD_DAC1 |
            0*ad9154_reg::PD_DAC2 | 0*ad9154_reg::PD_DAC3 |
            0*ad9154_reg::PD_BG);
    clock::spin_us(100);
    write(ad9154_reg::TXENMASK1, 0*ad9154_reg::DACA_MASK |
            0*ad9154_reg::DACB_MASK); // TX not controlled by TXEN pins
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

    write(ad9154_reg::INTERP_MODE, 0); // 1x
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
    write(ad9154_reg::PHY_PD, 0x0f); // power down lanes 0-3
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
    write(ad9154_reg::LANEDESKEW, 0x0f);
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
    write(ad9154_reg::LANEENABLE, 0x0f); // CGS _after_ this

    write(ad9154_reg::TERM_BLK1_CTRLREG0, 1);
    write(ad9154_reg::TERM_BLK2_CTRLREG0, 1);
    write(ad9154_reg::SERDES_SPI_REG, 1);
    write(ad9154_reg::CDR_OPERATING_MODE_REG_0,
            0*ad9154_reg::CDR_OVERSAMP | 0x2*ad9154_reg::CDR_RESERVED |
            1*ad9154_reg::ENHALFRATE);
    write(ad9154_reg::CDR_RESET, 0);
    write(ad9154_reg::CDR_RESET, 1);
    write(ad9154_reg::REF_CLK_DIVIDER_LDO,
            0x0*ad9154_reg::SPI_CDR_OVERSAMP |
            1*ad9154_reg::SPI_LDO_BYPASS_FILT |
            0*ad9154_reg::SPI_LDO_REF_SEL);
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
    write(ad9154_reg::SYNC_CONTROL,
            0x9*ad9154_reg::SYNCMODE | 0*ad9154_reg::SYNCENABLE |
            0*ad9154_reg::SYNCARM | 1*ad9154_reg::SYNCCLRSTKY |
            1*ad9154_reg::SYNCCLRLAST);
    write(ad9154_reg::SYNC_CONTROL,
            0x9*ad9154_reg::SYNCMODE | 1*ad9154_reg::SYNCENABLE |
            0*ad9154_reg::SYNCARM | 1*ad9154_reg::SYNCCLRSTKY |
            1*ad9154_reg::SYNCCLRLAST);
    write(ad9154_reg::SYNC_CONTROL,
            0x9*ad9154_reg::SYNCMODE | 1*ad9154_reg::SYNCENABLE |
            1*ad9154_reg::SYNCARM | 0*ad9154_reg::SYNCCLRSTKY |
            0*ad9154_reg::SYNCCLRLAST);
    clock::spin_us(1000); // ensure at least one sysref edge
    if read(ad9154_reg::SYNC_STATUS) & ad9154_reg::SYNC_LOCK == 0 {
        return Err("no sync lock")
    }
    write(ad9154_reg::XBAR_LN_0_1,
            7*ad9154_reg::LOGICAL_LANE0_SRC | 6*ad9154_reg::LOGICAL_LANE1_SRC);
    write(ad9154_reg::XBAR_LN_2_3,
            5*ad9154_reg::LOGICAL_LANE2_SRC | 4*ad9154_reg::LOGICAL_LANE3_SRC);
    write(ad9154_reg::XBAR_LN_4_5,
            0*ad9154_reg::LOGICAL_LANE4_SRC | 0*ad9154_reg::LOGICAL_LANE5_SRC);
    write(ad9154_reg::XBAR_LN_6_7,
            0*ad9154_reg::LOGICAL_LANE6_SRC | 0*ad9154_reg::LOGICAL_LANE7_SRC);
    write(ad9154_reg::JESD_BIT_INVERSE_CTRL, 0x00);
    write(ad9154_reg::GENERAL_JRX_CTRL_0,
            0x1*ad9154_reg::LINK_EN | 0*ad9154_reg::LINK_PAGE |
            0*ad9154_reg::LINK_MODE | 0*ad9154_reg::CHECKSUM_MODE);
    Ok(())
}

fn monitor() {
    write(ad9154_reg::IRQ_STATUS0, 0x00);
    write(ad9154_reg::IRQ_STATUS1, 0x00);
    write(ad9154_reg::IRQ_STATUS2, 0x00);
    write(ad9154_reg::IRQ_STATUS3, 0x00);

    write(ad9154_reg::IRQEN_STATUSMODE0,
          ad9154_reg::IRQEN_SMODE_LANEFIFOERR |
          ad9154_reg::IRQEN_SMODE_SERPLLLOCK |
          ad9154_reg::IRQEN_SMODE_SERPLLLOST |
          ad9154_reg::IRQEN_SMODE_DACPLLLOCK |
          ad9154_reg::IRQEN_SMODE_DACPLLLOST);

    write(ad9154_reg::IRQEN_STATUSMODE1,
          ad9154_reg::IRQEN_SMODE_PRBS0 |
          ad9154_reg::IRQEN_SMODE_PRBS1 |
          ad9154_reg::IRQEN_SMODE_PRBS2 |
          ad9154_reg::IRQEN_SMODE_PRBS3);

    write(ad9154_reg::IRQEN_STATUSMODE2,
          ad9154_reg::IRQEN_SMODE_SYNC_TRIP0 |
          ad9154_reg::IRQEN_SMODE_SYNC_WLIM0 |
          ad9154_reg::IRQEN_SMODE_SYNC_ROTATE0 |
          ad9154_reg::IRQEN_SMODE_SYNC_LOCK0 |
          ad9154_reg::IRQEN_SMODE_NCO_ALIGN0 |
          ad9154_reg::IRQEN_SMODE_BLNKDONE0 |
          ad9154_reg::IRQEN_SMODE_PDPERR0);

    write(ad9154_reg::IRQEN_STATUSMODE3,
          ad9154_reg::IRQEN_SMODE_SYNC_TRIP1 |
          ad9154_reg::IRQEN_SMODE_SYNC_WLIM1 |
          ad9154_reg::IRQEN_SMODE_SYNC_ROTATE1 |
          ad9154_reg::IRQEN_SMODE_SYNC_LOCK1 |
          ad9154_reg::IRQEN_SMODE_NCO_ALIGN1 |
          ad9154_reg::IRQEN_SMODE_BLNKDONE1 |
          ad9154_reg::IRQEN_SMODE_PDPERR1);

    write(ad9154_reg::IRQ_STATUS0, 0x00);
    write(ad9154_reg::IRQ_STATUS1, 0x00);
    write(ad9154_reg::IRQ_STATUS2, 0x00);
    write(ad9154_reg::IRQ_STATUS3, 0x00);
}

fn cfg() -> Result<(), &'static str> {
    jesd_enable(false);
    jesd_prbs(false);
    jesd_stpl(false);
    clock::spin_us(10000);
    jesd_enable(true);
    dac_setup()?;
    jesd_enable(false);
    clock::spin_us(10000);
    jesd_enable(true);
    monitor();
    let t = clock::get_ms();
    while !jesd_ready() {
        if clock::get_ms() > t + 200 {
            return Err("JESD ready timeout");
        }
    }
    clock::spin_us(10000);
    if read(ad9154_reg::CODEGRPSYNCFLG) != 0x0f {
        return Err("bad CODEGRPSYNCFLG")
    }
    if !jesd_jsync() {
        return Err("bad SYNC")
    }
    if read(ad9154_reg::FRAMESYNCFLG) != 0x0f {
        return Err("bad FRAMESYNCFLG")
    }
    if read(ad9154_reg::GOODCHKSUMFLG) != 0x0f {
        return Err("bad GOODCHECKSUMFLG")
    }
    if read(ad9154_reg::INITLANESYNCFLG) != 0x0f {
        return Err("bad INITLANESYNCFLG")
    }
    Ok(())
}

pub fn init() -> Result<(), &'static str> {
    spi_setup();

    // Release the JESD clock domain reset late, as we need to 
    // set up clock chips before.
    jesd_reset(false);

    for i in 0..99 {
        let outcome = cfg();
        match outcome {
            Ok(_) => return outcome,
            Err(e) => warn!("config attempt #{} failed ({}), retrying", i, e)
        }
    }
    cfg()
}
