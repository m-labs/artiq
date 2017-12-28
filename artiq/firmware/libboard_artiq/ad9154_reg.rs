#![allow(dead_code)]

pub const SPI_INTFCONFA                    : u16 = 0x000;
pub const SOFTRESET                        : u8 = 1 << 0;
pub const LSBFIRST                         : u8 = 1 << 1;
pub const ADDRINC                          : u8 = 1 << 2;
pub const SDOACTIVE                        : u8 = 1 << 3;
pub const SDOACTIVE_M                      : u8 = 1 << 4;
pub const ADDRINC_M                        : u8 = 1 << 5;
pub const LSBFIRST_M                       : u8 = 1 << 6;
pub const SOFTRESET_M                      : u8 = 1 << 7;

pub const CHIPTYPE                         : u16 = 0x003;

pub const PRODIDL                          : u16 = 0x004;

pub const PRODIDH                          : u16 = 0x005;

pub const CHIPGRADE                        : u16 = 0x006;
pub const DEV_REVISION                     : u8 = 1 << 0;
pub const PROD_GRADE                       : u8 = 1 << 4;

pub const SPI_PAGEINDX                     : u16 = 0x008;

pub const PWRCNTRL0                        : u16 = 0x011;
pub const PD_DAC3                          : u8 = 1 << 3;
pub const PD_DAC2                          : u8 = 1 << 4;
pub const PD_DAC1                          : u8 = 1 << 5;
pub const PD_DAC0                          : u8 = 1 << 6;
pub const PD_BG                            : u8 = 1 << 7;

pub const TXENMASK1                        : u16 = 0x012;
pub const DACA_MASK                        : u8 = 1 << 6;
pub const DACB_MASK                        : u8 = 1 << 7;

pub const PWRCNTRL3                        : u16 = 0x013;
pub const SPI_TXEN                         : u8 = 1 << 0;
pub const ENA_SPI_TXEN                     : u8 = 1 << 1;
pub const SPI_PA_CTRL                      : u8 = 1 << 2;
pub const ENA_PA_CTRL_FROM_SPI             : u8 = 1 << 3;
pub const ENA_PA_CTRL_FROM_BLSM            : u8 = 1 << 4;
pub const ENA_PA_CTRL_FROM_TXENSM          : u8 = 1 << 5;
pub const ENA_PA_CTRL_FROM_PARROT_ERR      : u8 = 1 << 6;

pub const GROUP_DLY                        : u16 = 0x014;
pub const COARSE_GROUP_DELAY               : u8 = 1 << 0;
pub const GROUP_DELAY_RESERVED             : u8 = 1 << 4;

pub const IRQEN_STATUSMODE0                : u16 = 0x01f;
pub const IRQEN_SMODE_LANEFIFOERR          : u8 = 1 << 1;
pub const IRQEN_SMODE_SERPLLLOCK           : u8 = 1 << 2;
pub const IRQEN_SMODE_SERPLLLOST           : u8 = 1 << 3;
pub const IRQEN_SMODE_DACPLLLOCK           : u8 = 1 << 4;
pub const IRQEN_SMODE_DACPLLLOST           : u8 = 1 << 5;

pub const IRQEN_STATUSMODE1                : u16 = 0x020;
pub const IRQEN_SMODE_PRBS0                : u8 = 1 << 0;
pub const IRQEN_SMODE_PRBS1                : u8 = 1 << 1;
pub const IRQEN_SMODE_PRBS2                : u8 = 1 << 2;
pub const IRQEN_SMODE_PRBS3                : u8 = 1 << 3;

pub const IRQEN_STATUSMODE2                : u16 = 0x021;
pub const IRQEN_SMODE_SYNC_TRIP0           : u8 = 1 << 0;
pub const IRQEN_SMODE_SYNC_WLIM0           : u8 = 1 << 1;
pub const IRQEN_SMODE_SYNC_ROTATE0         : u8 = 1 << 2;
pub const IRQEN_SMODE_SYNC_LOCK0           : u8 = 1 << 3;
pub const IRQEN_SMODE_NCO_ALIGN0           : u8 = 1 << 4;
pub const IRQEN_SMODE_BLNKDONE0            : u8 = 1 << 5;
pub const IRQEN_SMODE_PDPERR0              : u8 = 1 << 7;

pub const IRQEN_STATUSMODE3                : u16 = 0x022;
pub const IRQEN_SMODE_SYNC_TRIP1           : u8 = 1 << 0;
pub const IRQEN_SMODE_SYNC_WLIM1           : u8 = 1 << 1;
pub const IRQEN_SMODE_SYNC_ROTATE1         : u8 = 1 << 2;
pub const IRQEN_SMODE_SYNC_LOCK1           : u8 = 1 << 3;
pub const IRQEN_SMODE_NCO_ALIGN1           : u8 = 1 << 4;
pub const IRQEN_SMODE_BLNKDONE1            : u8 = 1 << 5;
pub const IRQEN_SMODE_PDPERR1              : u8 = 1 << 7;

pub const IRQ_STATUS0                      : u16 = 0x023;
pub const LANEFIFOERR                      : u8 = 1 << 1;
pub const SERPLLLOCK                       : u8 = 1 << 2;
pub const SERPLLLOST                       : u8 = 1 << 3;
pub const DACPLLLOCK                       : u8 = 1 << 4;
pub const DACPLLLOST                       : u8 = 1 << 5;

pub const IRQ_STATUS1                      : u16 = 0x024;
pub const PRBS0                            : u8 = 1 << 0;
pub const PRBS1                            : u8 = 1 << 1;
pub const PRBS2                            : u8 = 1 << 2;
pub const PRBS3                            : u8 = 1 << 3;

pub const IRQ_STATUS2                      : u16 = 0x025;
pub const SYNC_TRIP0                       : u8 = 1 << 0;
pub const SYNC_WLIM0                       : u8 = 1 << 1;
pub const SYNC_ROTATE0                     : u8 = 1 << 2;
pub const SYNC_LOCK0                       : u8 = 1 << 3;
pub const NCO_ALIGN0                       : u8 = 1 << 4;
pub const BLNKDONE0                        : u8 = 1 << 5;
pub const PDPERR0                          : u8 = 1 << 7;

pub const IRQ_STATUS3                      : u16 = 0x026;
pub const SYNC_TRIP1                       : u8 = 1 << 0;
pub const SYNC_WLIM1                       : u8 = 1 << 1;
pub const SYNC_ROTATE1                     : u8 = 1 << 2;
pub const SYNC_LOCK1                       : u8 = 1 << 3;
pub const NCO_ALIGN1                       : u8 = 1 << 4;
pub const BLNKDONE1                        : u8 = 1 << 5;
pub const PDPERR1                          : u8 = 1 << 7;

pub const JESD_CHECKS                      : u16 = 0x030;
pub const ERR_INTSUPP                      : u8 = 1 << 0;
pub const ERR_SUBCLASS                     : u8 = 1 << 1;
pub const ERR_KUNSUPP                      : u8 = 1 << 2;
pub const ERR_JESDBAD                      : u8 = 1 << 3;
pub const ERR_WINLIMIT                     : u8 = 1 << 4;
pub const ERR_DLYOVER                      : u8 = 1 << 5;

pub const SYNC_ERRWINDOW                   : u16 = 0x034;

pub const SYNC_LASTERR_L                   : u16 = 0x038;

pub const SYNC_LASTERR_H                   : u16 = 0x039;
pub const LASTERROR_H                      : u8 = 1 << 0;
pub const LASTOVER                         : u8 = 1 << 6;
pub const LASTUNDER                        : u8 = 1 << 7;

pub const SYNC_CONTROL                     : u16 = 0x03a;
pub const SYNCMODE                         : u8 = 1 << 0;
pub const SYNCCLRLAST                      : u8 = 1 << 4;
pub const SYNCCLRSTKY                      : u8 = 1 << 5;
pub const SYNCARM                          : u8 = 1 << 6;
pub const SYNCENABLE                       : u8 = 1 << 7;

pub const SYNC_STATUS                      : u16 = 0x03b;
pub const SYNC_TRIP                        : u8 = 1 << 0;
pub const SYNC_WLIM                        : u8 = 1 << 1;
pub const SYNC_ROTATE                      : u8 = 1 << 2;
pub const SYNC_LOCK                        : u8 = 1 << 3;
pub const SYNC_BUSY                        : u8 = 1 << 7;

pub const SYNC_CURRERR_L                   : u16 = 0x03c;

pub const SYNC_CURRERR_H                   : u16 = 0x03d;
pub const CURRERROR_H                      : u8 = 1 << 0;
pub const CURROVER                         : u8 = 1 << 6;
pub const CURRUNDER                        : u8 = 1 << 7;

pub const DACGAIN0_I                       : u16 = 0x040;

pub const DACGAIN1_I                       : u16 = 0x041;

pub const DACGAIN0_Q                       : u16 = 0x042;

pub const DACGAIN1_Q                       : u16 = 0x043;

pub const GROUPDELAY_COMP_I                : u16 = 0x044;

pub const GROUPDELAY_COMP_Q                : u16 = 0x045;

pub const GROUPDELAY_COMP_BYP              : u16 = 0x046;
pub const GROUPCOMP_BYPQ                   : u8 = 1 << 0;
pub const GROUPCOMP_BYPI                   : u8 = 1 << 1;

pub const MIX_MODE                         : u16 = 0x04a;

pub const NCOALIGN_MODE                    : u16 = 0x050;
pub const NCO_ALIGN_MODE                   : u8 = 1 << 0;
pub const NCO_ALIGN_FAIL                   : u8 = 1 << 3;
pub const NCO_ALIGN_PASS                   : u8 = 1 << 4;
pub const NCO_ALIGN_MTCH                   : u8 = 1 << 5;
pub const NCO_ALIGN_ARM                    : u8 = 1 << 7;

pub const NCOKEY_ILSB                      : u16 = 0x051;

pub const NCOKEY_IMSB                      : u16 = 0x052;

pub const NCOKEY_QLSB                      : u16 = 0x053;

pub const NCOKEY_QMSB                      : u16 = 0x054;

pub const PDP_THRES0                       : u16 = 0x060;

pub const PDP_THRES1                       : u16 = 0x061;

pub const PDP_AVG_TIME                     : u16 = 0x062;
pub const PDP_AVG_TIME_                    : u8 = 1 << 0;
pub const PA_BUS_SWAP                      : u8 = 1 << 6;
pub const PDP_ENABLE                       : u8 = 1 << 7;

pub const PDP_POWER0                       : u16 = 0x063;

pub const PDP_POWER1                       : u16 = 0x064;

pub const CLKCFG0                          : u16 = 0x080;
pub const REF_CLKDIV_EN                    : u8 = 1 << 0;
pub const RF_SYNC_EN                       : u8 = 1 << 1;
pub const DUTY_EN                          : u8 = 1 << 2;
pub const PD_CLK_REC                       : u8 = 1 << 3;
pub const PD_SERDES_PCLK                   : u8 = 1 << 4;
pub const PD_CLK_DIG                       : u8 = 1 << 5;
pub const PD_CLK23                         : u8 = 1 << 6;
pub const PD_CLK01                         : u8 = 1 << 7;

pub const SYSREF_ACTRL0                    : u16 = 0x081;
pub const HYS_CNTRL1                       : u8 = 1 << 0;
pub const SYSREF_RISE                      : u8 = 1 << 2;
pub const HYS_ON                           : u8 = 1 << 3;
pub const PD_SYSREF_BUFFER                 : u8 = 1 << 4;

pub const SYSREF_ACTRL1                    : u16 = 0x082;

pub const DACPLLCNTRL                      : u16 = 0x083;
pub const ENABLE_DACPLL                    : u8 = 1 << 4;
pub const RECAL_DACPLL                     : u8 = 1 << 7;

pub const DACPLLSTATUS                     : u16 = 0x084;
pub const DACPLL_LOCK                      : u8 = 1 << 1;
pub const VCO_CAL_PROGRESS                 : u8 = 1 << 3;
pub const CP_CAL_VALID                     : u8 = 1 << 4;
pub const CP_OVERRANGE_L                   : u8 = 1 << 5;
pub const CP_OVERRANGE_H                   : u8 = 1 << 6;

pub const DACINTEGERWORD0                  : u16 = 0x085;

pub const DACLOOPFILT1                     : u16 = 0x087;
pub const LF_C1_WORD                       : u8 = 1 << 0;
pub const LF_C2_WORD                       : u8 = 1 << 4;

pub const DACLOOPFILT2                     : u16 = 0x088;
pub const LF_C3_WORD                       : u8 = 1 << 0;
pub const LF_R1_WORD                       : u8 = 1 << 4;

pub const DACLOOPFILT3                     : u16 = 0x089;
pub const LF_R3_WORD                       : u8 = 1 << 0;
pub const LF_BYPASS_C1                     : u8 = 1 << 4;
pub const LF_BYPASS_C2                     : u8 = 1 << 5;
pub const LF_BYPASS_R1                     : u8 = 1 << 6;
pub const LF_BYPASS_R3                     : u8 = 1 << 7;

pub const DACCPCNTRL                       : u16 = 0x08a;
pub const CP_CURRENT                       : u8 = 1 << 0;
pub const VT_FORCE                         : u8 = 1 << 6;

pub const DACLOGENCNTRL                    : u16 = 0x08b;
pub const LODIVMODE                        : u8 = 1 << 0;
pub const LO_POWER_MODE                    : u8 = 1 << 4;

pub const DACLDOCNTRL1                     : u16 = 0x08c;
pub const REFDIVMODE                       : u8 = 1 << 0;
pub const LDO_BYPASS_FLT                   : u8 = 1 << 6;
pub const LDO_REF_SEL                      : u8 = 1 << 7;

pub const DACLDOCNTRL2                     : u16 = 0x08d;
pub const LDO_VDROP                        : u8 = 1 << 0;
pub const LDO_SEL                          : u8 = 1 << 2;
pub const LDO_INRUSH                       : u8 = 1 << 5;
pub const LDO_BYPASS                       : u8 = 1 << 7;

pub const DATA_FORMAT                      : u16 = 0x110;
pub const BINARY_FORMAT                    : u8 = 1 << 7;

pub const DATAPATH_CTRL                    : u16 = 0x111;
pub const I_TO_Q                           : u8 = 1 << 0;
pub const SEL_SIDEBAND                     : u8 = 1 << 1;
pub const MODULATION_TYPE                  : u8 = 1 << 2;
pub const PHASE_ADJ_ENABLE                 : u8 = 1 << 4;
pub const DIG_GAIN_ENABLE                  : u8 = 1 << 5;
pub const INVSINC_ENABLE                   : u8 = 1 << 7;

pub const INTERP_MODE                      : u16 = 0x112;

pub const NCO_FTW_UPDATE                   : u16 = 0x113;
pub const FTW_UPDATE_REQ                   : u8 = 1 << 0;
pub const FTW_UPDATE_ACK                   : u8 = 1 << 1;

pub const FTW0                             : u16 = 0x114;

pub const FTW1                             : u16 = 0x115;

pub const FTW2                             : u16 = 0x116;

pub const FTW3                             : u16 = 0x117;

pub const FTW4                             : u16 = 0x118;

pub const FTW5                             : u16 = 0x119;

pub const NCO_PHASE_OFFSET0                : u16 = 0x11a;

pub const NCO_PHASE_OFFSET1                : u16 = 0x11b;

pub const PHASE_ADJ0                       : u16 = 0x11c;

pub const PHASE_ADJ1                       : u16 = 0x11d;

pub const TXEN_SM_0                        : u16 = 0x11f;
pub const TXEN_SM_EN                       : u8 = 1 << 0;
pub const GP_PA_CTRL                       : u8 = 1 << 1;
pub const GP_PA_ON_INVERT                  : u8 = 1 << 2;
pub const RISE_COUNTERS                    : u8 = 1 << 4;
pub const FALL_COUNTERS                    : u8 = 1 << 6;

pub const TXEN_RISE_COUNT_0                : u16 = 0x121;

pub const TXEN_RISE_COUNT_1                : u16 = 0x122;

pub const TXEN_FALL_COUNT_0                : u16 = 0x123;

pub const TXEN_FALL_COUNT_1                : u16 = 0x124;

pub const DEVICE_CONFIG_REG_0              : u16 = 0x12d;

pub const DIE_TEMP_CTRL0                   : u16 = 0x12f;
pub const AUXADC_ENABLE                    : u8 = 1 << 0;
pub const AUXADC_RESERVED                  : u8 = 1 << 1;

pub const DIE_TEMP0                        : u16 = 0x132;

pub const DIE_TEMP1                        : u16 = 0x133;

pub const DIE_TEMP_UPDATE                  : u16 = 0x134;

pub const DC_OFFSET_CTRL                   : u16 = 0x135;

pub const IPATH_DC_OFFSET_1PART0           : u16 = 0x136;

pub const IPATH_DC_OFFSET_1PART1           : u16 = 0x137;

pub const QPATH_DC_OFFSET_1PART0           : u16 = 0x138;

pub const QPATH_DC_OFFSET_1PART1           : u16 = 0x139;

pub const IPATH_DC_OFFSET_2PART            : u16 = 0x13a;

pub const QPATH_DC_OFFSET_2PART            : u16 = 0x13b;

pub const IDAC_DIG_GAIN0                   : u16 = 0x13c;

pub const IDAC_DIG_GAIN1                   : u16 = 0x13d;

pub const QDAC_DIG_GAIN0                   : u16 = 0x13e;

pub const QDAC_DIG_GAIN1                   : u16 = 0x13f;

pub const GAIN_RAMP_UP_STEP0               : u16 = 0x140;

pub const GAIN_RAMP_UP_STEP1               : u16 = 0x141;

pub const GAIN_RAMP_DOWN_STEP0             : u16 = 0x142;

pub const GAIN_RAMP_DOWN_STEP1             : u16 = 0x143;

pub const DEVICE_CONFIG_REG_1              : u16 = 0x146;

pub const BSM_STAT                         : u16 = 0x147;
pub const SOFTBLANKRB                      : u8 = 1 << 6;

pub const PRBS                             : u16 = 0x14b;
pub const PRBS_EN                          : u8 = 1 << 0;
pub const PRBS_RESET                       : u8 = 1 << 1;
pub const PRBS_MODE                        : u8 = 1 << 2;
pub const PRBS_GOOD_I                      : u8 = 1 << 6;
pub const PRBS_GOOD_Q                      : u8 = 1 << 7;

pub const PRBS_ERROR_I                     : u16 = 0x14c;

pub const PRBS_ERROR_Q                     : u16 = 0x14d;

pub const DACPLLT0                         : u16 = 0x1b0;
pub const LOGEN_PD                         : u8 = 1 << 1;
pub const LDO_PD                           : u8 = 1 << 3;
pub const SYNTH_PD                         : u8 = 1 << 4;
pub const VCO_PD_ALC                       : u8 = 1 << 5;
pub const VCO_PD_PTAT                      : u8 = 1 << 6;
pub const VCO_PD_IN                        : u8 = 1 << 7;

pub const DACPLLT1                         : u16 = 0x1b1;
pub const PFD_EDGE                         : u8 = 1 << 1;
pub const PFD_DELAY                        : u8 = 1 << 2;

pub const DACPLLT2                         : u16 = 0x1b2;
pub const EXT_ALC_WORD                     : u8 = 1 << 0;
pub const EXT_ALC_WORD_EN                  : u8 = 1 << 7;

pub const DACPLLT3                         : u16 = 0x1b3;
pub const EXT_BAND1                        : u8 = 1 << 0;

pub const DACPLLT4                         : u16 = 0x1b4;
pub const EXT_BAND2                        : u8 = 1 << 0;
pub const EXT_BAND_EN                      : u8 = 1 << 1;
pub const VCO_CAL_OFFSET                   : u8 = 1 << 3;
pub const BYP_LOAD_DELAY                   : u8 = 1 << 7;

pub const DACPLLT5                         : u16 = 0x1b5;

pub const DACPLLT6                         : u16 = 0x1b6;

pub const DACPLLT7                         : u16 = 0x1b7;

pub const DACPLLT8                         : u16 = 0x1b8;

pub const DACPLLT9                         : u16 = 0x1b9;

pub const DACPLLTA                         : u16 = 0x1ba;

pub const DACPLLTB                         : u16 = 0x1bb;
pub const VCO_BIAS_REF                     : u8 = 1 << 0;
pub const VCO_BIAS_TCF                     : u8 = 1 << 3;

pub const DACPLLTC                         : u16 = 0x1bc;

pub const DACPLLTD                         : u16 = 0x1bd;

pub const DACPLLTE                         : u16 = 0x1be;

pub const DACPLLTF                         : u16 = 0x1bf;

pub const DACPLLT10                        : u16 = 0x1c0;

pub const DACPLLT11                        : u16 = 0x1c1;

pub const DACPLLT15                        : u16 = 0x1c2;

pub const DACPLLT16                        : u16 = 0x1c3;

pub const DACPLLT17                        : u16 = 0x1c4;

pub const DACPLLT18                        : u16 = 0x1c5;

pub const MASTER_PD                        : u16 = 0x200;

pub const PHY_PD                           : u16 = 0x201;

pub const GENERIC_PD                       : u16 = 0x203;
pub const PD_SYNCOUT1B                     : u8 = 1 << 0;
pub const PD_SYNCOUT0B                     : u8 = 1 << 1;

pub const CDR_RESET                        : u16 = 0x206;

pub const CDR_OPERATING_MODE_REG_0         : u16 = 0x230;
pub const CDR_OVERSAMP                     : u8 = 1 << 1;
pub const CDR_RESERVED                     : u8 = 1 << 2;
pub const ENHALFRATE                       : u8 = 1 << 5;

pub const EQ_BIAS_REG                      : u16 = 0x268;
pub const EQ_BIAS_RESERVED                 : u8 = 1 << 0;
pub const EQ_POWER_MODE                    : u8 = 1 << 6;

pub const SERDESPLL_ENABLE_CNTRL           : u16 = 0x280;
pub const ENABLE_SERDESPLL                 : u8 = 1 << 0;
pub const RECAL_SERDESPLL                  : u8 = 1 << 2;

pub const PLL_STATUS                       : u16 = 0x281;
pub const SERDES_PLL_LOCK_RB               : u8 = 1 << 0;
pub const SERDES_CURRENTS_READY_RB         : u8 = 1 << 1;
pub const SERDES_VCO_CAL_IN_PROGRESS_RB    : u8 = 1 << 2;
pub const SERDES_PLL_CAL_VALID_RB          : u8 = 1 << 3;
pub const SERDES_PLL_OVERRANGE_L_RB        : u8 = 1 << 4;
pub const SERDES_PLL_OVERRANGE_H_RB        : u8 = 1 << 5;

pub const LDO_FILTER_1                     : u16 = 0x284;

pub const LDO_FILTER_2                     : u16 = 0x285;

pub const LDO_FILTER_3                     : u16 = 0x286;

pub const CP_CURRENT_SPI                   : u16 = 0x287;
pub const SPI_CP_CURRENT                   : u8 = 1 << 0;
pub const SPI_SERDES_LOGEN_POWER_MODE      : u8 = 1 << 6;

pub const REF_CLK_DIVIDER_LDO              : u16 = 0x289;
pub const SPI_CDR_OVERSAMP                 : u8 = 1 << 0;
pub const SPI_LDO_BYPASS_FILT              : u8 = 1 << 2;
pub const SPI_LDO_REF_SEL                  : u8 = 1 << 3;

pub const VCO_LDO                          : u16 = 0x28a;

pub const PLL_RD_REG                       : u16 = 0x28b;
pub const SPI_SERDES_LOGEN_PD_CORE         : u8 = 1 << 0;
pub const SPI_SERDES_LDO_PD                : u8 = 1 << 2;
pub const SPI_SYN_PD                       : u8 = 1 << 3;
pub const SPI_VCO_PD_ALC                   : u8 = 1 << 4;
pub const SPI_VCO_PD_PTAT                  : u8 = 1 << 5;
pub const SPI_VCO_PD                       : u8 = 1 << 6;

pub const ALC_VARACTOR                     : u16 = 0x290;
pub const SPI_VCO_VARACTOR                 : u8 = 1 << 0;
pub const SPI_INIT_ALC_VALUE               : u8 = 1 << 4;

pub const VCO_OUTPUT                       : u16 = 0x291;
pub const SPI_VCO_OUTPUT_LEVEL             : u8 = 1 << 0;
pub const SPI_VCO_OUTPUT_RESERVED          : u8 = 1 << 4;

pub const CP_CONFIG                        : u16 = 0x294;
pub const SPI_CP_TEST                      : u8 = 1 << 0;
pub const SPI_CP_CAL_EN                    : u8 = 1 << 2;
pub const SPI_CP_FORCE_CALBITS             : u8 = 1 << 3;
pub const SPI_CP_OFFSET_OFF                : u8 = 1 << 4;
pub const SPI_CP_ENABLE_MACHINE            : u8 = 1 << 5;
pub const SPI_CP_DITHER_MODE               : u8 = 1 << 6;
pub const SPI_CP_HALF_VCO_CAL_CLK          : u8 = 1 << 7;

pub const VCO_BIAS_1                       : u16 = 0x296;
pub const SPI_VCO_BIAS_REF                 : u8 = 1 << 0;
pub const SPI_VCO_BIAS_TCF                 : u8 = 1 << 3;

pub const VCO_BIAS_2                       : u16 = 0x297;
pub const SPI_PRESCALE_BIAS                : u8 = 1 << 0;
pub const SPI_LAST_ALC_EN                  : u8 = 1 << 2;
pub const SPI_PRESCALE_BYPASS_R            : u8 = 1 << 3;
pub const SPI_VCO_COMP_BYPASS_BIASR        : u8 = 1 << 4;
pub const SPI_VCO_BYPASS_DAC_R             : u8 = 1 << 5;

pub const VCO_PD_OVERRIDES                 : u16 = 0x299;
pub const SPI_VCO_PD_OVERRIDE_VCO_BUF      : u8 = 1 << 0;
pub const SPI_VCO_PD_OVERRIDE_CAL_TCF      : u8 = 1 << 1;
pub const SPI_VCO_PD_OVERRIDE_VAR_REF_TCF  : u8 = 1 << 2;
pub const SPI_VCO_PD_OVERRIDE_VAR_REF      : u8 = 1 << 3;

pub const VCO_CAL                          : u16 = 0x29a;
pub const SPI_FB_CLOCK_ADV                 : u8 = 1 << 0;
pub const SPI_VCO_CAL_COUNT                : u8 = 1 << 2;
pub const SPI_VCO_CAL_ALC_WAIT             : u8 = 1 << 4;
pub const SPI_VCO_CAL_EN                   : u8 = 1 << 7;

pub const CP_LEVEL_DETECT                  : u16 = 0x29c;
pub const SPI_CP_LEVEL_THRESHOLD_HIGH      : u8 = 1 << 0;
pub const SPI_CP_LEVEL_THRESHOLD_LOW       : u8 = 1 << 3;
pub const SPI_CP_LEVEL_DET_PD              : u8 = 1 << 6;

pub const VCO_VARACTOR_CTRL_0              : u16 = 0x29f;
pub const SPI_VCO_VARACTOR_OFFSET          : u8 = 1 << 0;
pub const SPI_VCO_VARACTOR_REF_TCF         : u8 = 1 << 4;

pub const VCO_VARACTOR_CTRL_1              : u16 = 0x2a0;
pub const SPI_VCO_VARACTOR_REF             : u8 = 1 << 0;

pub const TERM_BLK1_CTRLREG0               : u16 = 0x2a7;

pub const TERM_BLK2_CTRLREG0               : u16 = 0x2ae;

pub const GENERAL_JRX_CTRL_0               : u16 = 0x300;
pub const LINK_EN                          : u8 = 1 << 0;
pub const LINK_PAGE                        : u8 = 1 << 2;
pub const LINK_MODE                        : u8 = 1 << 3;
pub const CHECKSUM_MODE                    : u8 = 1 << 6;

pub const GENERAL_JRX_CTRL_1               : u16 = 0x301;

pub const DYN_LINK_LATENCY_0               : u16 = 0x302;

pub const DYN_LINK_LATENCY_1               : u16 = 0x303;

pub const LMFC_DELAY_0                     : u16 = 0x304;

pub const LMFC_DELAY_1                     : u16 = 0x305;

pub const LMFC_VAR_0                       : u16 = 0x306;

pub const LMFC_VAR_1                       : u16 = 0x307;

pub const XBAR_LN_0_1                      : u16 = 0x308;
pub const LOGICAL_LANE0_SRC                : u8 = 1 << 0;
pub const LOGICAL_LANE1_SRC                : u8 = 1 << 3;

pub const XBAR_LN_2_3                      : u16 = 0x309;
pub const LOGICAL_LANE2_SRC                : u8 = 1 << 0;
pub const LOGICAL_LANE3_SRC                : u8 = 1 << 3;

pub const XBAR_LN_4_5                      : u16 = 0x30a;
pub const LOGICAL_LANE4_SRC                : u8 = 1 << 0;
pub const LOGICAL_LANE5_SRC                : u8 = 1 << 3;

pub const XBAR_LN_6_7                      : u16 = 0x30b;
pub const LOGICAL_LANE6_SRC                : u8 = 1 << 0;
pub const LOGICAL_LANE7_SRC                : u8 = 1 << 3;

pub const FIFO_STATUS_REG_0                : u16 = 0x30c;

pub const FIFO_STATUS_REG_1                : u16 = 0x30d;

pub const SYNCB_GEN_1                      : u16 = 0x312;
pub const SYNCB_ERR_DUR                    : u8 = 1 << 4;

pub const SERDES_SPI_REG                   : u16 = 0x314;

pub const PHY_PRBS_TEST_EN                 : u16 = 0x315;

pub const PHY_PRBS_TEST_CTRL               : u16 = 0x316;
pub const PHY_TEST_RESET                   : u8 = 1 << 0;
pub const PHY_TEST_START                   : u8 = 1 << 1;
pub const PHY_PRBS_PAT_SEL                 : u8 = 1 << 2;
pub const PHY_SRC_ERR_CNT                  : u8 = 1 << 4;

pub const PHY_PRBS_TEST_THRESHOLD_LOBITS   : u16 = 0x317;

pub const PHY_PRBS_TEST_THRESHOLD_MIDBITS  : u16 = 0x318;

pub const PHY_PRBS_TEST_THRESHOLD_HIBITS   : u16 = 0x319;

pub const PHY_PRBS_TEST_ERRCNT_LOBITS      : u16 = 0x31a;

pub const PHY_PRBS_TEST_ERRCNT_MIDBITS     : u16 = 0x31b;

pub const PHY_PRBS_TEST_ERRCNT_HIBITS      : u16 = 0x31c;

pub const PHY_PRBS_TEST_STATUS             : u16 = 0x31d;

pub const SHORT_TPL_TEST_0                 : u16 = 0x32c;
pub const SHORT_TPL_TEST_EN                : u8 = 1 << 0;
pub const SHORT_TPL_TEST_RESET             : u8 = 1 << 1;
pub const SHORT_TPL_DAC_SEL                : u8 = 1 << 2;
pub const SHORT_TPL_SP_SEL                 : u8 = 1 << 4;

pub const SHORT_TPL_TEST_1                 : u16 = 0x32d;

pub const SHORT_TPL_TEST_2                 : u16 = 0x32e;

pub const SHORT_TPL_TEST_3                 : u16 = 0x32f;

pub const DEVICE_CONFIG_REG_2              : u16 = 0x333;

pub const JESD_BIT_INVERSE_CTRL            : u16 = 0x334;

pub const DID_REG                          : u16 = 0x400;

pub const BID_REG                          : u16 = 0x401;
pub const BID_RD                           : u8 = 1 << 0;
pub const ADJCNT_RD                        : u8 = 1 << 4;

pub const LID0_REG                         : u16 = 0x402;
pub const LID0_RD                          : u8 = 1 << 0;
pub const PHADJ_RD                         : u8 = 1 << 5;
pub const ADJDIR_RD                        : u8 = 1 << 6;

pub const SCR_L_REG                        : u16 = 0x403;
pub const L_1_RD                           : u8 = 1 << 0;
pub const SCR_RD                           : u8 = 1 << 7;

pub const F_REG                            : u16 = 0x404;

pub const K_REG                            : u16 = 0x405;

pub const M_REG                            : u16 = 0x406;

pub const CS_N_REG                         : u16 = 0x407;
pub const N_1_RD                           : u8 = 1 << 0;
pub const CS_RD                            : u8 = 1 << 6;

pub const NP_REG                           : u16 = 0x408;
pub const NP_1_RD                          : u8 = 1 << 0;
pub const SUBCLASSV_RD                     : u8 = 1 << 5;

pub const S_REG                            : u16 = 0x409;
pub const S_1_RD                           : u8 = 1 << 0;
pub const JESDV_RD                         : u8 = 1 << 5;

pub const HD_CF_REG                        : u16 = 0x40a;
pub const CF_RD                            : u8 = 1 << 0;
pub const HD_RD                            : u8 = 1 << 7;

pub const RES1_REG                         : u16 = 0x40b;

pub const RES2_REG                         : u16 = 0x40c;

pub const CHECKSUM0_REG                    : u16 = 0x40d;

pub const COMPSUM0_REG                     : u16 = 0x40e;

pub const LID1_REG                         : u16 = 0x412;

pub const CHECKSUM1_REG                    : u16 = 0x415;

pub const COMPSUM1_REG                     : u16 = 0x416;

pub const LID2_REG                         : u16 = 0x41a;

pub const CHECKSUM2_REG                    : u16 = 0x41d;

pub const COMPSUM2_REG                     : u16 = 0x41e;

pub const LID3_REG                         : u16 = 0x422;

pub const CHECKSUM3_REG                    : u16 = 0x425;

pub const COMPSUM3_REG                     : u16 = 0x426;

pub const LID4_REG                         : u16 = 0x42a;

pub const CHECKSUM4_REG                    : u16 = 0x42d;

pub const COMPSUM4_REG                     : u16 = 0x42e;

pub const LID5_REG                         : u16 = 0x432;

pub const CHECKSUM5_REG                    : u16 = 0x435;

pub const COMPSUM5_REG                     : u16 = 0x436;

pub const LID6_REG                         : u16 = 0x43a;

pub const CHECKSUM6_REG                    : u16 = 0x43d;

pub const COMPSUM6_REG                     : u16 = 0x43e;

pub const LID7_REG                         : u16 = 0x442;

pub const CHECKSUM7_REG                    : u16 = 0x445;

pub const COMPSUM7_REG                     : u16 = 0x446;

pub const ILS_DID                          : u16 = 0x450;

pub const ILS_BID                          : u16 = 0x451;
pub const BID                              : u8 = 1 << 0;
pub const ADJCNT                           : u8 = 1 << 4;

pub const ILS_LID0                         : u16 = 0x452;
pub const LID0                             : u8 = 1 << 0;
pub const PHADJ                            : u8 = 1 << 5;
pub const ADJDIR                           : u8 = 1 << 6;

pub const ILS_SCR_L                        : u16 = 0x453;
pub const L_1                              : u8 = 1 << 0;
pub const SCR                              : u8 = 1 << 7;

pub const ILS_F                            : u16 = 0x454;

pub const ILS_K                            : u16 = 0x455;

pub const ILS_M                            : u16 = 0x456;

pub const ILS_CS_N                         : u16 = 0x457;
pub const N_1                              : u8 = 1 << 0;
pub const CS                               : u8 = 1 << 6;

pub const ILS_NP                           : u16 = 0x458;
pub const NP_1                             : u8 = 1 << 0;
pub const SUBCLASSV                        : u8 = 1 << 5;

pub const ILS_S                            : u16 = 0x459;
pub const S_1                              : u8 = 1 << 0;
pub const JESDV                            : u8 = 1 << 5;

pub const ILS_HD_CF                        : u16 = 0x45a;
pub const CF                               : u8 = 1 << 0;
pub const HD                               : u8 = 1 << 7;

pub const ILS_RES1                         : u16 = 0x45b;

pub const ILS_RES2                         : u16 = 0x45c;

pub const ILS_CHECKSUM                     : u16 = 0x45d;

pub const ERRCNTRMON                       : u16 = 0x46b;
pub const CNTRSEL                          : u8 = 1 << 0;
pub const LANESEL                          : u8 = 1 << 4;

pub const LANEDESKEW                       : u16 = 0x46c;

pub const BADDISPARITY                     : u16 = 0x46d;
pub const LANE_ADDR_DIS                    : u8 = 1 << 0;
pub const RST_ERR_CNTR_DIS                 : u8 = 1 << 5;
pub const DISABLE_ERR_CNTR_DIS             : u8 = 1 << 6;
pub const RST_IRQ_DIS                      : u8 = 1 << 7;

pub const NIT_W                            : u16 = 0x46e;
pub const LANE_ADDR_NIT                    : u8 = 1 << 0;
pub const RST_ERR_CNTR_NIT                 : u8 = 1 << 5;
pub const DISABLE_ERR_CNTR_NIT             : u8 = 1 << 6;
pub const RST_IRQ_NIT                      : u8 = 1 << 7;

pub const UNEXPECTEDCONTROL_W              : u16 = 0x46f;
pub const LANE_ADDR_UCC                    : u8 = 1 << 0;
pub const RST_ERR_CNTR_UCC                 : u8 = 1 << 5;
pub const DISABLE_ERR_CNTR_UCC             : u8 = 1 << 6;
pub const RST_IRQ_UCC                      : u8 = 1 << 7;

pub const CODEGRPSYNCFLG                   : u16 = 0x470;

pub const FRAMESYNCFLG                     : u16 = 0x471;

pub const GOODCHKSUMFLG                    : u16 = 0x472;

pub const INITLANESYNCFLG                  : u16 = 0x473;

pub const CTRLREG1                         : u16 = 0x476;

pub const CTRLREG2                         : u16 = 0x477;
pub const THRESHOLD_MASK_EN                : u8 = 1 << 3;
pub const ILAS_MODE                        : u8 = 1 << 7;

pub const KVAL                             : u16 = 0x478;

pub const IRQVECTOR_MASK                   : u16 = 0x47a;
pub const CODEGRPSYNC_MASK                 : u8 = 1 << 0;
pub const BADCHECKSUM_MASK                 : u8 = 1 << 2;
pub const INITIALLANESYNC_MASK             : u8 = 1 << 3;
pub const UCC_MASK                         : u8 = 1 << 5;
pub const NIT_MASK                         : u8 = 1 << 6;
pub const BADDIS_MASK                      : u8 = 1 << 7;

pub const SYNCASSERTIONMASK                : u16 = 0x47b;
pub const CMM_ENABLE                       : u8 = 1 << 3;
pub const CMM                              : u8 = 1 << 4;
pub const UCC_S                            : u8 = 1 << 5;
pub const NIT_S                            : u8 = 1 << 6;
pub const BADDIS_S                         : u8 = 1 << 7;

pub const ERRORTHRES                       : u16 = 0x47c;

pub const LANEENABLE                       : u16 = 0x47d;

pub const RAMP_ENA                         : u16 = 0x47e;

pub const DIG_TEST0                        : u16 = 0x520;
pub const DC_TEST_MODE                     : u8 = 1 << 1;

pub const DC_TEST_VALUEI0                  : u16 = 0x521;

pub const DC_TEST_VALUEI1                  : u16 = 0x522;

pub const DC_TEST_VALUEQ0                  : u16 = 0x523;

pub const DC_TEST_VALUEQ1                  : u16 = 0x524;
