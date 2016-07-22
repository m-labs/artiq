#  = auto-generated, do not edit
from artiq.language.core import kernel


AD9516_SERIAL_PORT_CONFIGURATION         = 0x000
AD9516_SDO_ACTIVE                        = 1 << 0  # 1, 0x00 R/W
AD9516_LSB_FIRST                         = 1 << 1  # 1, 0x00 R/W
AD9516_SOFT_RESET                        = 1 << 2  # 1, 0x00 R/W
AD9516_LONG_INSTRUCTION                  = 1 << 3  # 1, 0x01 R/W
AD9516_LONG_INSTRUCTION_MIRRORED         = 1 << 4  # 1, 0x01 R/W
AD9516_SOFT_RESET_MIRRORED               = 1 << 5  # 1, 0x00 R/W
AD9516_LSB_FIRST_MIRRORED                = 1 << 6  # 1, 0x00 R/W
AD9516_SDO_ACTIVE_MIRRORED               = 1 << 7  # 1, 0x00 R/W

AD9516_PART_ID                           = 0x003

AD9516_READBACK_CONTROL                  = 0x004
AD9516_READ_BACK_ACTIVE_REGISTERS        = 1 << 0  # 1, 0x00 R/W

AD9516_PFD_AND_CHARGE_PUMP               = 0x010
AD9516_PLL_POWER_DOWN                    = 1 << 0  # 2, 0x01 R/W
AD9516_CHARGE_PUMP_MODE                  = 1 << 2  # 2, 0x03 R/W
AD9516_CHARGE_PUMP_CURRENT               = 1 << 4  # 3, 0x07 R/W
AD9516_PFD_POLARITY                      = 1 << 7  # 1, 0x00 R/W

AD9516_R_COUNTER_LSB                     = 0x011
AD9516_R_COUNTER_MSB                     = 0x012

AD9516_A_COUNTER                         = 0x013

AD9516_B_COUNTER_LSB                     = 0x014
AD9516_B_COUNTER_MSB                     = 0x015

AD9516_PLL_CONTROL_1                     = 0x016
AD9516_PRESCALER_P                       = 1 << 0  # 3, 0x06 R/W
AD9516_B_COUNTER_BYPASS                  = 1 << 3  # 1, 0x00 R/W
AD9516_RESET_ALL_COUNTERS                = 1 << 4  # 1, 0x00 R/W
AD9516_RESET_A_AND_B_COUNTERS            = 1 << 5  # 1, 0x00 R/W
AD9516_RESET_R_COUNTER                   = 1 << 6  # 1, 0x00 R/W
AD9516_SET_CP_PIN_TO_VCP_2               = 1 << 7  # 1, 0x00 R/W

AD9516_PLL_CONTROL_2                     = 0x017
AD9516_ANTIBACKLASH_PULSE_WIDTH          = 1 << 0  # 2, 0x00 R/W
AD9516_STATUS_PIN_CONTROL                = 1 << 2  # 6, 0x00 R/W

AD9516_PLL_CONTROL_3                     = 0x018
AD9516_VCO_CAL_NOW                       = 1 << 0  # 1, 0x00 R/W
AD9516_VCO_CALIBRATION_DIVIDER           = 1 << 1  # 2, 0x03 R/W
AD9516_DISABLE_DIGITAL_LOCK_DETECT       = 1 << 3  # 1, 0x00 R/W
AD9516_DIGITAL_LOCK_DETECT_WINDOW        = 1 << 4  # 1, 0x00 R/W
AD9516_LOCK_DETECT_COUNTER               = 1 << 5  # 2, 0x00 R/W

AD9516_PLL_CONTROL_4                     = 0x019
AD9516_N_PATH_DELAY                      = 1 << 0  # 3, 0x00 R/W
AD9516_R_PATH_DELAY                      = 1 << 3  # 3, 0x00 R/W
AD9516_R_A_B_COUNTERS_SYNC_PIN_RESET     = 1 << 6  # 2, 0x00 R/W

AD9516_PLL_CONTROL_5                     = 0x01a
AD9516_LD_PIN_CONTROL                    = 1 << 0  # 6, 0x00 R/W
AD9516_REFERENCE_FREQUENCY_MONITOR_THRESHOLD  = 1 << 6  # 1, 0x00 R/W

AD9516_PLL_CONTROL_6                     = 0x01b
AD9516_REFMON_PIN_CONTROL                = 1 << 0  # 5, 0x00 R/W
AD9516_REF1_REFIN_FREQUENCY_MONITOR      = 1 << 5  # 1, 0x00 R/W
AD9516_REF2_REFIN_FREQUENCY_MONITOR      = 1 << 6  # 1, 0x00 R/W
AD9516_VCO_FREQUENCY_MONITOR             = 1 << 7  # 1, 0x00 R/W

AD9516_PLL_CONTROL_7                     = 0x01c
AD9516_DIFFERENTIAL_REFERENCE            = 1 << 0  # 1, 0x00 R/W
AD9516_REF1_POWER_ON                     = 1 << 1  # 1, 0x00 R/W
AD9516_REF2_POWER_ON                     = 1 << 2  # 1, 0x00 R/W
AD9516_USE_REF_SEL_PIN                   = 1 << 5  # 1, 0x00 R/W
AD9516_SELECT_REF2                       = 1 << 6  # 1, 0x00 R/W
AD9516_DISABLE_SWITCHOVER_DEGLITCH       = 1 << 7  # 1, 0x00 R/W

AD9516_PLL_CONTROL_8                     = 0x01d
AD9516_HOLDOVER_ENABLE                   = 1 << 0  # 1, 0x00 R/W
AD9516_EXTERNAL_HOLDOVER_CONTROL         = 1 << 1  # 1, 0x00 R/W
AD9516_HOLDOVER_ENABLEreg001D            = 1 << 2  # 1, 0x00 R/W
AD9516_LD_PIN_COMPARATOR_ENABLE          = 1 << 3  # 1, 0x00 R/W
AD9516_PLL_STATUS_REGISTER_DISABLE       = 1 << 4  # 1, 0x00 R/W

AD9516_PLL_READBACK                      = 0x01f
AD9516_DIGITAL_LOCK_DETECT               = 1 << 0  # 1, 0x00 R
AD9516_REF1_FREQUENCY_THRESHOLD          = 1 << 1  # 1, 0x00 R
AD9516_REF2_FREQUENCY_THRESHOLD          = 1 << 2  # 1, 0x00 R
AD9516_VCO_FREQUENCY_THRESHOLD           = 1 << 3  # 1, 0x00 R
AD9516_REF2_SELECTED                     = 1 << 4  # 1, 0x00 R
AD9516_HOLDOVER_ACTIVE                   = 1 << 5  # 1, 0x00 R
AD9516_VCO_CAL_FINISHED                  = 1 << 6  # 1, 0x00 R

AD9516_OUT6_DELAY_BYPASS                 = 0x0a0

AD9516_OUT6_DELAY_FULL_SCALE             = 0x0a1
AD9516_OUT6_RAMP_CURRENT                 = 1 << 0  # 3, 0x00 R/W
AD9516_OUT6_RAMP_CAPACITORS              = 1 << 3  # 3, 0x00 R/W

AD9516_OUT6_DELAY_FRACTION               = 0x0a2

AD9516_OUT7_DELAY_BYPASS                 = 0x0a3

AD9516_OUT7_DELAY_FULL_SCALE             = 0x0a4
AD9516_OUT7_RAMP_CURRENT                 = 1 << 0  # 3, 0x00 R/W
AD9516_OUT7_RAMP_CAPACITORS              = 1 << 3  # 3, 0x00 R/W

AD9516_OUT7_DELAY_FRACTION               = 0x0a5

AD9516_OUT8_DELAY_BYPASS                 = 0x0a6

AD9516_OUT8_DELAY_FULL_SCALE             = 0x0a7
AD9516_OUT8_RAMP_CURRENT                 = 1 << 0  # 3, 0x00 R/W
AD9516_OUT8_RAMP_CAPACITORS              = 1 << 3  # 3, 0x00 R/W

AD9516_OUT8_DELAY_FRACTION               = 0x0a8

AD9516_OUT9_DELAY_BYPASS                 = 0x0a9

AD9516_OUT9_DELAY_FULL_SCALE             = 0x0aa
AD9516_OUT9_RAMP_CURRENT                 = 1 << 0  # 3, 0x00 R/W
AD9516_OUT9_RAMP_CAPACITORS              = 1 << 3  # 3, 0x00 R/W

AD9516_OUT9_DELAY_FRACTION               = 0x0ab

AD9516_OUT0                              = 0x0f0
AD9516_OUT0_POWER_DOWN                   = 1 << 0  # 2, 0x00 R/W
AD9516_OUT0_LVPECL_DIFFERENTIAL_VOLTAGE  = 1 << 2  # 2, 0x02 R/W
AD9516_OUT0_INVERT                       = 1 << 4  # 1, 0x00 R/W

AD9516_OUT1                              = 0x0f1
AD9516_OUT1_POWER_DOWN                   = 1 << 0  # 2, 0x02 R/W
AD9516_OUT1_LVPECLDIFFERENTIAL_VOLTAGE   = 1 << 2  # 2, 0x02 R/W
AD9516_OUT1_INVERT                       = 1 << 4  # 1, 0x00 R/W

AD9516_OUT2                              = 0x0f2
AD9516_OUT2_POWER_DOWN                   = 1 << 0  # 2, 0x00 R/W
AD9516_OUT2_LVPECL_DIFFERENTIAL_VOLTAGE  = 1 << 2  # 2, 0x02 R/W
AD9516_OUT2_INVERT                       = 1 << 4  # 1, 0x00 R/W

AD9516_OUT3                              = 0x0f3
AD9516_OUT3_POWER_DOWN                   = 1 << 0  # 2, 0x02 R/W
AD9516_OUT3_LVPECL_DIFFERENTIAL_VOLTAGE  = 1 << 2  # 2, 0x02 R/W
AD9516_OUT3_INVERT                       = 1 << 4  # 1, 0x00 R/W

AD9516_OUT4                              = 0x0f4
AD9516_OUT4_POWER_DOWN                   = 1 << 0  # 2, 0x02 R/W
AD9516_OUT4_LVPECL_DIFFERENTIAL_VOLTAGE  = 1 << 2  # 2, 0x02 R/W
AD9516_OUT4_INVERT                       = 1 << 4  # 1, 0x00 R/W

AD9516_OUT5                              = 0x0f5
AD9516_OUT5_POWER_DOWN                   = 1 << 0  # 2, 0x02 R/W
AD9516_OUT5_LVPECL_DIFFERENTIAL_VOLTAGE  = 1 << 2  # 2, 0x02 R/W
AD9516_OUT5_INVERT                       = 1 << 4  # 1, 0x00 R/W

AD9516_OUT6                              = 0x140
AD9516_OUT6_POWER_DOWN                   = 1 << 0  # 1, 0x00 R/W
AD9516_OUT6_LVDS_OUTPUT_CURRENT          = 1 << 1  # 2, 0x01 R/W
AD9516_OUT6_SELECT_LVDS_CMOS             = 1 << 3  # 1, 0x00 R/W
AD9516_OUT6_CMOS_B                       = 1 << 4  # 1, 0x00 R/W
AD9516_OUT6_LVDS_CMOS_OUTPUT_POLARITY    = 1 << 5  # 1, 0x00 R/W
AD9516_OUT6_CMOS_OUTPUT_POLARITY         = 1 << 6  # 2, 0x01 R/W

AD9516_OUT7                              = 0x141
AD9516_OUT7_POWER_DOWN                   = 1 << 0  # 1, 0x01 R/W
AD9516_OUT7_LVDS_OUTPUT_CURRENT          = 1 << 1  # 2, 0x01 R/W
AD9516_OUT7_SELECT_LVDS_CMOS             = 1 << 3  # 1, 0x00 R/W
AD9516_OUT7_CMOS_B                       = 1 << 4  # 1, 0x00 R/W
AD9516_OUT7_LVDS_CMOS_OUTPUT_POLARITY    = 1 << 5  # 1, 0x00 R/W
AD9516_OUT7_CMOS_OUTPUT_POLARITY         = 1 << 6  # 2, 0x01 R/W

AD9516_OUT8                              = 0x142
AD9516_OUT8_POWER_DOWN                   = 1 << 0  # 1, 0x00 R/W
AD9516_OUT8_LVDS_OUTPUT_CURRENT          = 1 << 1  # 2, 0x01 R/W
AD9516_OUT8_SELECT_LVDS_CMOS             = 1 << 3  # 1, 0x00 R/W
AD9516_OUT8_CMOS_B                       = 1 << 4  # 1, 0x00 R/W
AD9516_OUT8_LVDS_CMOS_OUTPUT_POLARITY    = 1 << 5  # 1, 0x00 R/W
AD9516_OUT8_CMOS_OUTPUT_POLARITY         = 1 << 6  # 2, 0x01 R/W

AD9516_OUT9                              = 0x143
AD9516_OUT9_POWER_DOWN                   = 1 << 0  # 1, 0x01 R/W
AD9516_OUT9_LVDS_OUTPUT_CURRENT          = 1 << 1  # 2, 0x01 R/W
AD9516_OUT9_SELECT_LVDS_CMOS             = 1 << 3  # 1, 0x00 R/W
AD9516_OUT9_CMOS_B                       = 1 << 4  # 1, 0x00 R/W
AD9516_OUT9_LVDS_CMOS_OUTPUT_POLARITY    = 1 << 5  # 1, 0x00 R/W
AD9516_OUT9_CMOS_OUTPUT_POLARITY         = 1 << 6  # 2, 0x01 R/W

AD9516_DIVIDER_0_0                       = 0x190
AD9516_DIVIDER_0_HIGH_CYCLES             = 1 << 0  # 4, 0x00 R/W
AD9516_DIVIDER_0_LOW_CYCLES              = 1 << 4  # 4, 0x00 R/W

AD9516_DIVIDER_0_1                       = 0x191
AD9516_DIVIDER_0_PHASE_OFFSET            = 1 << 0  # 4, 0x00 R/W
AD9516_DIVIDER_0_START_HIGH              = 1 << 4  # 1, 0x00 R/W
AD9516_DIVIDER_0_FORCE_HIGH              = 1 << 5  # 1, 0x00 R/W
AD9516_DIVIDER_0_NOSYNC                  = 1 << 6  # 1, 0x00 R/W
AD9516_DIVIDER_0_BYPASS                  = 1 << 7  # 1, 0x01 R/W

AD9516_DIVIDER_0_2                       = 0x192
AD9516_DIVIDER_0_DCCOFF                  = 1 << 0  # 1, 0x00 R/W
AD9516_DIVIDER_0_DIRECT_TO_OUTPUT        = 1 << 1  # 1, 0x00 R/W

AD9516_DIVIDER_1_0                       = 0x193
AD9516_DIVIDER_1_HIGH_CYCLES             = 1 << 0  # 4, 0x00 R/W
AD9516_DIVIDER_1_LOW_CYCLES              = 1 << 4  # 4, 0x00 R/W

AD9516_DIVIDER_1_1                       = 0x194
AD9516_DIVIDER_1_PHASE_OFFSET            = 1 << 0  # 4, 0x00 R/W
AD9516_DIVIDER_1_START_HIGH              = 1 << 4  # 1, 0x00 R/W
AD9516_DIVIDER_1_FORCE_HIGH              = 1 << 5  # 1, 0x00 R/W
AD9516_DIVIDER_1_NOSYNC                  = 1 << 6  # 1, 0x00 R/W
AD9516_DIVIDER_1_BYPASS                  = 1 << 7  # 1, 0x00 R/W

AD9516_DIVIDER_1_2                       = 0x195
AD9516_DIVIDER_1_DCCOFF                  = 1 << 0  # 1, 0x00 R/W
AD9516_DIVIDER_1_DIRECT_TO_OUTPUT        = 1 << 1  # 1, 0x00 R/W

AD9516_DIVIDER_2_0                       = 0x196
AD9516_DIVIDER_2_HIGH_CYCLES             = 1 << 0  # 4, 0x00 R/W
AD9516_DIVIDER_2_LOW_CYCLES              = 1 << 4  # 4, 0x00 R/W

AD9516_DIVIDER_2_1                       = 0x197
AD9516_DIVIDER_2_PHASE_OFFSET            = 1 << 0  # 4, 0x00 R/W
AD9516_DIVIDER_2_START_HIGH              = 1 << 4  # 1, 0x00 R/W
AD9516_DIVIDER_2_FORCE_HIGH              = 1 << 5  # 1, 0x00 R/W
AD9516_DIVIDER_2_NOSYNC                  = 1 << 6  # 1, 0x00 R/W
AD9516_DIVIDER_2_BYPASS                  = 1 << 7  # 1, 0x00 R/W

AD9516_DIVIDER_2_2                       = 0x198
AD9516_DIVIDER_2_DCCOFF                  = 1 << 0  # 1, 0x00 R/W
AD9516_DIVIDER_2_DIRECT_TO_OUTPUT        = 1 << 1  # 1, 0x00 R/W

AD9516_DIVIDER_3_0                       = 0x199
AD9516_DIVIDER_3_HIGH_CYCLES_1           = 1 << 0  # 4, 0x02 R/W
AD9516_DIVIDER_3_LOW_CYCLES_1            = 1 << 4  # 4, 0x02 R/W

AD9516_DIVIDER_3_1                       = 0x19a
AD9516_DIVIDER_3_PHASE_OFFSET_1          = 1 << 0  # 4, 0x00 R/W
AD9516_DIVIDER_3_PHASE_OFFSET_2          = 1 << 4  # 4, 0x00 R/W

AD9516_DIVIDER_3_2                       = 0x19b
AD9516_DIVIDER_3_HIGH_CYCLES_2           = 1 << 0  # 4, 0x01 R/W
AD9516_DIVIDER_3_LOW_CYCLES_2            = 1 << 4  # 4, 0x01 R/W

AD9516_DIVIDER_3_3                       = 0x19c
AD9516_DIVIDER_3_START_HIGH_1            = 1 << 0  # 1, 0x00 R/W
AD9516_DIVIDER_3_START_HIGH_2            = 1 << 1  # 1, 0x00 R/W
AD9516_DIVIDER_3_FORCE_HIGH              = 1 << 2  # 1, 0x00 R/W
AD9516_DIVIDER_3_NOSYNC                  = 1 << 3  # 1, 0x00 R/W
AD9516_DIVIDER_3_BYPASS_1                = 1 << 4  # 1, 0x00 R/W
AD9516_DIVIDER_3_BYPASS_2                = 1 << 5  # 1, 0x00 R/W

AD9516_DIVIDER_3_4                       = 0x19d
AD9516_DIVIDER_3_DCCOFF                  = 1 << 0  # 1, 0x00 R/W

AD9516_DIVIDER_4_0                       = 0x19e
AD9516_DIVIDER_4_HIGH_CYCLES_1           = 1 << 0  # 4, 0x02 R/W
AD9516_DIVIDER_4_LOW_CYCLES_1            = 1 << 4  # 4, 0x02 R/W

AD9516_DIVIDER_4_1                       = 0x19f
AD9516_DIVIDER_4_PHASE_OFFSET_1          = 1 << 0  # 4, 0x00 R/W
AD9516_DIVIDER_4_PHASE_OFFSET_2          = 1 << 4  # 4, 0x00 R/W

AD9516_DIVIDER_4_2                       = 0x1a0
AD9516_DIVIDER_4_HIGH_CYCLES_2           = 1 << 0  # 4, 0x01 R/W
AD9516_DIVIDER_4_LOW_CYCLES_2            = 1 << 4  # 4, 0x01 R/W

AD9516_DIVIDER_4_3                       = 0x1a1
AD9516_DIVIDER_4_START_HIGH_1            = 1 << 0  # 1, 0x00 R/W
AD9516_DIVIDER_4_START_HIGH_2            = 1 << 1  # 1, 0x00 R/W
AD9516_DIVIDER_4_FORCE_HIGH              = 1 << 2  # 1, 0x00 R/W
AD9516_DIVIDER_4_NOSYNC                  = 1 << 3  # 1, 0x00 R/W
AD9516_DIVIDER_4_BYPASS_1                = 1 << 4  # 1, 0x00 R/W
AD9516_DIVIDER_4_BYPASS_2                = 1 << 5  # 1, 0x00 R/W

AD9516_DIVIDER_4_4                       = 0x1a2
AD9516_DIVIDER_4_DCCOFF                  = 1 << 0  # 1, 0x00 R/W

AD9516_VCO_DIVIDER                       = 0x1e0

AD9516_INPUT_CLKS                        = 0x1e1
AD9516_BYPASS_VCO_DIVIDER                = 1 << 0  # 1, 0x00 R/W
AD9516_SELECT_VCO_OR_CLK                 = 1 << 1  # 1, 0x00 R/W
AD9516_POWER_DOWN_VCO_AND_CLK            = 1 << 2  # 1, 0x00 R/W
AD9516_POWER_DOWN_VCO_CLOCK_INTERFACE    = 1 << 3  # 1, 0x00 R/W
AD9516_POWER_DOWN_CLOCK_INPUT_SECTION    = 1 << 4  # 1, 0x00 R/W

AD9516_POWER_DOWN_AND_SYNC               = 0x230
AD9516_SOFT_SYNC                         = 1 << 0  # 1, 0x00 R/W
AD9516_POWER_DOWN_DISTRIBUTION_REFERENCE = 1 << 1  # 1, 0x00 R/W
AD9516_POWER_DOWN_SYNC                   = 1 << 2  # 1, 0x00 R/W

AD9516_UPDATE_ALL_REGISTERS              = 0x232
