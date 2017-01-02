pub const SERIAL_PORT_CONFIGURATION         : u16 = 0x000;
pub const SDO_ACTIVE                        : u8 = 1 << 0;
pub const LSB_FIRST                         : u8 = 1 << 1;
pub const SOFT_RESET                        : u8 = 1 << 2;
pub const LONG_INSTRUCTION                  : u8 = 1 << 3;
pub const LONG_INSTRUCTION_MIRRORED         : u8 = 1 << 4;
pub const SOFT_RESET_MIRRORED               : u8 = 1 << 5;
pub const LSB_FIRST_MIRRORED                : u8 = 1 << 6;
pub const SDO_ACTIVE_MIRRORED               : u8 = 1 << 7;

pub const PART_ID                           : u16 = 0x003;

pub const READBACK_CONTROL                  : u16 = 0x004;
pub const READ_BACK_ACTIVE_REGISTERS        : u8 = 1 << 0;

pub const PFD_AND_CHARGE_PUMP               : u16 = 0x010;
pub const PLL_POWER_DOWN                    : u8 = 1 << 0;
pub const CHARGE_PUMP_MODE                  : u8 = 1 << 2;
pub const CHARGE_PUMP_CURRENT               : u8 = 1 << 4;
pub const PFD_POLARITY                      : u8 = 1 << 7;

pub const R_COUNTER_LSB                     : u16 = 0x011;
pub const R_COUNTER_MSB                     : u16 = 0x012;

pub const A_COUNTER                         : u16 = 0x013;

pub const B_COUNTER_LSB                     : u16 = 0x014;
pub const B_COUNTER_MSB                     : u16 = 0x015;

pub const PLL_CONTROL_1                     : u16 = 0x016;
pub const PRESCALER_P                       : u8 = 1 << 0;
pub const B_COUNTER_BYPASS                  : u8 = 1 << 3;
pub const RESET_ALL_COUNTERS                : u8 = 1 << 4;
pub const RESET_A_AND_B_COUNTERS            : u8 = 1 << 5;
pub const RESET_R_COUNTER                   : u8 = 1 << 6;
pub const SET_CP_PIN_TO_VCP_2               : u8 = 1 << 7;

pub const PLL_CONTROL_2                     : u16 = 0x017;
pub const ANTIBACKLASH_PULSE_WIDTH          : u8 = 1 << 0;
pub const STATUS_PIN_CONTROL                : u8 = 1 << 2;

pub const PLL_CONTROL_3                     : u16 = 0x018;
pub const VCO_CAL_NOW                       : u8 = 1 << 0;
pub const VCO_CALIBRATION_DIVIDER           : u8 = 1 << 1;
pub const DISABLE_DIGITAL_LOCK_DETECT       : u8 = 1 << 3;
pub const DIGITAL_LOCK_DETECT_WINDOW        : u8 = 1 << 4;
pub const LOCK_DETECT_COUNTER               : u8 = 1 << 5;

pub const PLL_CONTROL_4                     : u16 = 0x019;
pub const N_PATH_DELAY                      : u8 = 1 << 0;
pub const R_PATH_DELAY                      : u8 = 1 << 3;
pub const R_A_B_COUNTERS_SYNC_PIN_RESET     : u8 = 1 << 6;

pub const PLL_CONTROL_5                     : u16 = 0x01a;
pub const LD_PIN_CONTROL                    : u8 = 1 << 0;
pub const REFERENCE_FREQUENCY_MONITOR_THR   : u8 = 1 << 6;

pub const PLL_CONTROL_6                     : u16 = 0x01b;
pub const REFMON_PIN_CONTROL                : u8 = 1 << 0;
pub const REF1_REFIN_FREQUENCY_MONITOR      : u8 = 1 << 5;
pub const REF2_REFIN_FREQUENCY_MONITOR      : u8 = 1 << 6;
pub const VCO_FREQUENCY_MONITOR             : u8 = 1 << 7;

pub const PLL_CONTROL_7                     : u16 = 0x01c;
pub const DIFFERENTIAL_REFERENCE            : u8 = 1 << 0;
pub const REF1_POWER_ON                     : u8 = 1 << 1;
pub const REF2_POWER_ON                     : u8 = 1 << 2;
pub const USE_REF_SEL_PIN                   : u8 = 1 << 5;
pub const SELECT_REF2                       : u8 = 1 << 6;
pub const DISABLE_SWITCHOVER_DEGLITCH       : u8 = 1 << 7;

pub const PLL_CONTROL_8                     : u16 = 0x01d;
pub const HOLDOVER_ENABLE                   : u8 = 1 << 0;
pub const EXTERNAL_HOLDOVER_CONTROL         : u8 = 1 << 1;
pub const HOLDOVER_ENABLED                  : u8 = 1 << 2;
pub const LD_PIN_COMPARATOR_ENABLE          : u8 = 1 << 3;
pub const PLL_STATUS_REGISTER_DISABLE       : u8 = 1 << 4;

pub const PLL_READBACK                      : u16 = 0x01f;
pub const DIGITAL_LOCK_DETECT               : u8 = 1 << 0;
pub const REF1_FREQUENCY_THRESHOLD          : u8 = 1 << 1;
pub const REF2_FREQUENCY_THRESHOLD          : u8 = 1 << 2;
pub const VCO_FREQUENCY_THRESHOLD           : u8 = 1 << 3;
pub const REF2_SELECTED                     : u8 = 1 << 4;
pub const HOLDOVER_ACTIVE                   : u8 = 1 << 5;
pub const VCO_CAL_FINISHED                  : u8 = 1 << 6;

pub const OUT6_DELAY_BYPASS                 : u16 = 0x0a0;

pub const OUT6_DELAY_FULL_SCALE             : u16 = 0x0a1;
pub const OUT6_RAMP_CURRENT                 : u8 = 1 << 0;
pub const OUT6_RAMP_CAPACITORS              : u8 = 1 << 3;

pub const OUT6_DELAY_FRACTION               : u16 = 0x0a2;

pub const OUT7_DELAY_BYPASS                 : u16 = 0x0a3;

pub const OUT7_DELAY_FULL_SCALE             : u16 = 0x0a4;
pub const OUT7_RAMP_CURRENT                 : u8 = 1 << 0;
pub const OUT7_RAMP_CAPACITORS              : u8 = 1 << 3;

pub const OUT7_DELAY_FRACTION               : u16 = 0x0a5;

pub const OUT8_DELAY_BYPASS                 : u16 = 0x0a6;

pub const OUT8_DELAY_FULL_SCALE             : u16 = 0x0a7;
pub const OUT8_RAMP_CURRENT                 : u8 = 1 << 0;
pub const OUT8_RAMP_CAPACITORS              : u8 = 1 << 3;

pub const OUT8_DELAY_FRACTION               : u16 = 0x0a8;

pub const OUT9_DELAY_BYPASS                 : u16 = 0x0a9;

pub const OUT9_DELAY_FULL_SCALE             : u16 = 0x0aa;
pub const OUT9_RAMP_CURRENT                 : u8 = 1 << 0;
pub const OUT9_RAMP_CAPACITORS              : u8 = 1 << 3;

pub const OUT9_DELAY_FRACTION               : u16 = 0x0ab;

pub const OUT0                              : u16 = 0x0f0;
pub const OUT0_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT0_LVPECL_DIFFERENTIAL_VOLTAGE  : u8 = 1 << 2;
pub const OUT0_INVERT                       : u8 = 1 << 4;

pub const OUT1                              : u16 = 0x0f1;
pub const OUT1_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT1_LVPECLDIFFERENTIAL_VOLTAGE   : u8 = 1 << 2;
pub const OUT1_INVERT                       : u8 = 1 << 4;

pub const OUT2                              : u16 = 0x0f2;
pub const OUT2_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT2_LVPECL_DIFFERENTIAL_VOLTAGE  : u8 = 1 << 2;
pub const OUT2_INVERT                       : u8 = 1 << 4;

pub const OUT3                              : u16 = 0x0f3;
pub const OUT3_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT3_LVPECL_DIFFERENTIAL_VOLTAGE  : u8 = 1 << 2;
pub const OUT3_INVERT                       : u8 = 1 << 4;

pub const OUT4                              : u16 = 0x0f4;
pub const OUT4_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT4_LVPECL_DIFFERENTIAL_VOLTAGE  : u8 = 1 << 2;
pub const OUT4_INVERT                       : u8 = 1 << 4;

pub const OUT5                              : u16 = 0x0f5;
pub const OUT5_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT5_LVPECL_DIFFERENTIAL_VOLTAGE  : u8 = 1 << 2;
pub const OUT5_INVERT                       : u8 = 1 << 4;

pub const OUT6                              : u16 = 0x140;
pub const OUT6_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT6_LVDS_OUTPUT_CURRENT          : u8 = 1 << 1;
pub const OUT6_SELECT_LVDS_CMOS             : u8 = 1 << 3;
pub const OUT6_CMOS_B                       : u8 = 1 << 4;
pub const OUT6_LVDS_CMOS_OUTPUT_POLARITY    : u8 = 1 << 5;
pub const OUT6_CMOS_OUTPUT_POLARITY         : u8 = 1 << 6;

pub const OUT7                              : u16 = 0x141;
pub const OUT7_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT7_LVDS_OUTPUT_CURRENT          : u8 = 1 << 1;
pub const OUT7_SELECT_LVDS_CMOS             : u8 = 1 << 3;
pub const OUT7_CMOS_B                       : u8 = 1 << 4;
pub const OUT7_LVDS_CMOS_OUTPUT_POLARITY    : u8 = 1 << 5;
pub const OUT7_CMOS_OUTPUT_POLARITY         : u8 = 1 << 6;

pub const OUT8                              : u16 = 0x142;
pub const OUT8_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT8_LVDS_OUTPUT_CURRENT          : u8 = 1 << 1;
pub const OUT8_SELECT_LVDS_CMOS             : u8 = 1 << 3;
pub const OUT8_CMOS_B                       : u8 = 1 << 4;
pub const OUT8_LVDS_CMOS_OUTPUT_POLARITY    : u8 = 1 << 5;
pub const OUT8_CMOS_OUTPUT_POLARITY         : u8 = 1 << 6;

pub const OUT9                              : u16 = 0x143;
pub const OUT9_POWER_DOWN                   : u8 = 1 << 0;
pub const OUT9_LVDS_OUTPUT_CURRENT          : u8 = 1 << 1;
pub const OUT9_SELECT_LVDS_CMOS             : u8 = 1 << 3;
pub const OUT9_CMOS_B                       : u8 = 1 << 4;
pub const OUT9_LVDS_CMOS_OUTPUT_POLARITY    : u8 = 1 << 5;
pub const OUT9_CMOS_OUTPUT_POLARITY         : u8 = 1 << 6;

pub const DIVIDER_0_0                       : u16 = 0x190;
pub const DIVIDER_0_HIGH_CYCLES             : u8 = 1 << 0;
pub const DIVIDER_0_LOW_CYCLES              : u8 = 1 << 4;

pub const DIVIDER_0_1                       : u16 = 0x191;
pub const DIVIDER_0_PHASE_OFFSET            : u8 = 1 << 0;
pub const DIVIDER_0_START_HIGH              : u8 = 1 << 4;
pub const DIVIDER_0_FORCE_HIGH              : u8 = 1 << 5;
pub const DIVIDER_0_NOSYNC                  : u8 = 1 << 6;
pub const DIVIDER_0_BYPASS                  : u8 = 1 << 7;

pub const DIVIDER_0_2                       : u16 = 0x192;
pub const DIVIDER_0_DCCOFF                  : u8 = 1 << 0;
pub const DIVIDER_0_DIRECT_TO_OUTPUT        : u8 = 1 << 1;

pub const DIVIDER_1_0                       : u16 = 0x193;
pub const DIVIDER_1_HIGH_CYCLES             : u8 = 1 << 0;
pub const DIVIDER_1_LOW_CYCLES              : u8 = 1 << 4;

pub const DIVIDER_1_1                       : u16 = 0x194;
pub const DIVIDER_1_PHASE_OFFSET            : u8 = 1 << 0;
pub const DIVIDER_1_START_HIGH              : u8 = 1 << 4;
pub const DIVIDER_1_FORCE_HIGH              : u8 = 1 << 5;
pub const DIVIDER_1_NOSYNC                  : u8 = 1 << 6;
pub const DIVIDER_1_BYPASS                  : u8 = 1 << 7;

pub const DIVIDER_1_2                       : u16 = 0x195;
pub const DIVIDER_1_DCCOFF                  : u8 = 1 << 0;
pub const DIVIDER_1_DIRECT_TO_OUTPUT        : u8 = 1 << 1;

pub const DIVIDER_2_0                       : u16 = 0x196;
pub const DIVIDER_2_HIGH_CYCLES             : u8 = 1 << 0;
pub const DIVIDER_2_LOW_CYCLES              : u8 = 1 << 4;

pub const DIVIDER_2_1                       : u16 = 0x197;
pub const DIVIDER_2_PHASE_OFFSET            : u8 = 1 << 0;
pub const DIVIDER_2_START_HIGH              : u8 = 1 << 4;
pub const DIVIDER_2_FORCE_HIGH              : u8 = 1 << 5;
pub const DIVIDER_2_NOSYNC                  : u8 = 1 << 6;
pub const DIVIDER_2_BYPASS                  : u8 = 1 << 7;

pub const DIVIDER_2_2                       : u16 = 0x198;
pub const DIVIDER_2_DCCOFF                  : u8 = 1 << 0;
pub const DIVIDER_2_DIRECT_TO_OUTPUT        : u8 = 1 << 1;

pub const DIVIDER_3_0                       : u16 = 0x199;
pub const DIVIDER_3_HIGH_CYCLES_1           : u8 = 1 << 0;
pub const DIVIDER_3_LOW_CYCLES_1            : u8 = 1 << 4;

pub const DIVIDER_3_1                       : u16 = 0x19a;
pub const DIVIDER_3_PHASE_OFFSET_1          : u8 = 1 << 0;
pub const DIVIDER_3_PHASE_OFFSET_2          : u8 = 1 << 4;

pub const DIVIDER_3_2                       : u16 = 0x19b;
pub const DIVIDER_3_HIGH_CYCLES_2           : u8 = 1 << 0;
pub const DIVIDER_3_LOW_CYCLES_2            : u8 = 1 << 4;

pub const DIVIDER_3_3                       : u16 = 0x19c;
pub const DIVIDER_3_START_HIGH_1            : u8 = 1 << 0;
pub const DIVIDER_3_START_HIGH_2            : u8 = 1 << 1;
pub const DIVIDER_3_FORCE_HIGH              : u8 = 1 << 2;
pub const DIVIDER_3_NOSYNC                  : u8 = 1 << 3;
pub const DIVIDER_3_BYPASS_1                : u8 = 1 << 4;
pub const DIVIDER_3_BYPASS_2                : u8 = 1 << 5;

pub const DIVIDER_3_4                       : u16 = 0x19d;
pub const DIVIDER_3_DCCOFF                  : u8 = 1 << 0;

pub const DIVIDER_4_0                       : u16 = 0x19e;
pub const DIVIDER_4_HIGH_CYCLES_1           : u8 = 1 << 0;
pub const DIVIDER_4_LOW_CYCLES_1            : u8 = 1 << 4;

pub const DIVIDER_4_1                       : u16 = 0x19f;
pub const DIVIDER_4_PHASE_OFFSET_1          : u8 = 1 << 0;
pub const DIVIDER_4_PHASE_OFFSET_2          : u8 = 1 << 4;

pub const DIVIDER_4_2                       : u16 = 0x1a0;
pub const DIVIDER_4_HIGH_CYCLES_2           : u8 = 1 << 0;
pub const DIVIDER_4_LOW_CYCLES_2            : u8 = 1 << 4;

pub const DIVIDER_4_3                       : u16 = 0x1a1;
pub const DIVIDER_4_START_HIGH_1            : u8 = 1 << 0;
pub const DIVIDER_4_START_HIGH_2            : u8 = 1 << 1;
pub const DIVIDER_4_FORCE_HIGH              : u8 = 1 << 2;
pub const DIVIDER_4_NOSYNC                  : u8 = 1 << 3;
pub const DIVIDER_4_BYPASS_1                : u8 = 1 << 4;
pub const DIVIDER_4_BYPASS_2                : u8 = 1 << 5;

pub const DIVIDER_4_4                       : u16 = 0x1a2;
pub const DIVIDER_4_DCCOFF                  : u8 = 1 << 0;

pub const VCO_DIVIDER                       : u16 = 0x1e0;

pub const INPUT_CLKS                        : u16 = 0x1e1;
pub const BYPASS_VCO_DIVIDER                : u8 = 1 << 0;
pub const SELECT_VCO_OR_CLK                 : u8 = 1 << 1;
pub const POWER_DOWN_VCO_AND_CLK            : u8 = 1 << 2;
pub const POWER_DOWN_VCO_CLOCK_INTERFACE    : u8 = 1 << 3;
pub const POWER_DOWN_CLOCK_INPUT_SECTION    : u8 = 1 << 4;

pub const POWER_DOWN_AND_SYNC               : u16 = 0x230;
pub const SOFT_SYNC                         : u8 = 1 << 0;
pub const POWER_DOWN_DISTRIBUTION_REFERENCE : u8 = 1 << 1;
pub const POWER_DOWN_SYNC                   : u8 = 1 << 2;

pub const UPDATE_ALL_REGISTERS              : u16 = 0x232;
