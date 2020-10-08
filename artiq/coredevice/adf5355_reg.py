# auto-generated, do not edit
from artiq.language.core import portable
from artiq.language.types import TInt32
from numpy import int32


@portable
def ADF5355_REG0_AUTOCAL_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 21) & 0x1)


@portable
def ADF5355_REG0_AUTOCAL(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 21)


@portable
def ADF5355_REG0_AUTOCAL_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 21)) | ((x & 0x1) << 21))


@portable
def ADF5355_REG0_INT_VALUE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0xFFFF)


@portable
def ADF5355_REG0_INT_VALUE(x: TInt32) -> TInt32:
    return int32((x & 0xFFFF) << 4)


@portable
def ADF5355_REG0_INT_VALUE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0xFFFF << 4)) | ((x & 0xFFFF) << 4))


@portable
def ADF5355_REG0_PRESCALER_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 20) & 0x1)


@portable
def ADF5355_REG0_PRESCALER(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 20)


@portable
def ADF5355_REG0_PRESCALER_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 20)) | ((x & 0x1) << 20))


@portable
def ADF5355_REG1_MAIN_FRAC_VALUE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0xFFFFFF)


@portable
def ADF5355_REG1_MAIN_FRAC_VALUE(x: TInt32) -> TInt32:
    return int32((x & 0xFFFFFF) << 4)


@portable
def ADF5355_REG1_MAIN_FRAC_VALUE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0xFFFFFF << 4)) | ((x & 0xFFFFFF) << 4))


@portable
def ADF5355_REG2_AUX_FRAC_LSB_VALUE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 18) & 0x3FFF)


@portable
def ADF5355_REG2_AUX_FRAC_LSB_VALUE(x: TInt32) -> TInt32:
    return int32((x & 0x3FFF) << 18)


@portable
def ADF5355_REG2_AUX_FRAC_LSB_VALUE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3FFF << 18)) | ((x & 0x3FFF) << 18))


@portable
def ADF5355_REG2_AUX_MOD_LSB_VALUE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0x3FFF)


@portable
def ADF5355_REG2_AUX_MOD_LSB_VALUE(x: TInt32) -> TInt32:
    return int32((x & 0x3FFF) << 4)


@portable
def ADF5355_REG2_AUX_MOD_LSB_VALUE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3FFF << 4)) | ((x & 0x3FFF) << 4))


@portable
def ADF5355_REG3_PHASE_ADJUST_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 28) & 0x1)


@portable
def ADF5355_REG3_PHASE_ADJUST(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 28)


@portable
def ADF5355_REG3_PHASE_ADJUST_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 28)) | ((x & 0x1) << 28))


@portable
def ADF5355_REG3_PHASE_RESYNC_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 29) & 0x1)


@portable
def ADF5355_REG3_PHASE_RESYNC(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 29)


@portable
def ADF5355_REG3_PHASE_RESYNC_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 29)) | ((x & 0x1) << 29))


@portable
def ADF5355_REG3_PHASE_VALUE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0xFFFFFF)


@portable
def ADF5355_REG3_PHASE_VALUE(x: TInt32) -> TInt32:
    return int32((x & 0xFFFFFF) << 4)


@portable
def ADF5355_REG3_PHASE_VALUE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0xFFFFFF << 4)) | ((x & 0xFFFFFF) << 4))


@portable
def ADF5355_REG3_SD_LOAD_RESET_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 30) & 0x1)


@portable
def ADF5355_REG3_SD_LOAD_RESET(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 30)


@portable
def ADF5355_REG3_SD_LOAD_RESET_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 30)) | ((x & 0x1) << 30))


@portable
def ADF5355_REG4_COUNTER_RESET_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0x1)


@portable
def ADF5355_REG4_COUNTER_RESET(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 4)


@portable
def ADF5355_REG4_COUNTER_RESET_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 4)) | ((x & 0x1) << 4))


@portable
def ADF5355_REG4_CP_THREE_STATE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 5) & 0x1)


@portable
def ADF5355_REG4_CP_THREE_STATE(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 5)


@portable
def ADF5355_REG4_CP_THREE_STATE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 5)) | ((x & 0x1) << 5))


@portable
def ADF5355_REG4_CURRENT_SETTING_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 10) & 0xF)


@portable
def ADF5355_REG4_CURRENT_SETTING(x: TInt32) -> TInt32:
    return int32((x & 0xF) << 10)


@portable
def ADF5355_REG4_CURRENT_SETTING_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0xF << 10)) | ((x & 0xF) << 10))


@portable
def ADF5355_REG4_DOUBLE_BUFF_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 14) & 0x1)


@portable
def ADF5355_REG4_DOUBLE_BUFF(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 14)


@portable
def ADF5355_REG4_DOUBLE_BUFF_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 14)) | ((x & 0x1) << 14))


@portable
def ADF5355_REG4_MUX_LOGIC_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 8) & 0x1)


@portable
def ADF5355_REG4_MUX_LOGIC(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 8)


@portable
def ADF5355_REG4_MUX_LOGIC_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 8)) | ((x & 0x1) << 8))


@portable
def ADF5355_REG4_MUXOUT_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 27) & 0x7)


@portable
def ADF5355_REG4_MUXOUT(x: TInt32) -> TInt32:
    return int32((x & 0x7) << 27)


@portable
def ADF5355_REG4_MUXOUT_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x7 << 27)) | ((x & 0x7) << 27))


@portable
def ADF5355_REG4_PD_POLARITY_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 7) & 0x1)


@portable
def ADF5355_REG4_PD_POLARITY(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 7)


@portable
def ADF5355_REG4_PD_POLARITY_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 7)) | ((x & 0x1) << 7))


@portable
def ADF5355_REG4_POWER_DOWN_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 6) & 0x1)


@portable
def ADF5355_REG4_POWER_DOWN(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 6)


@portable
def ADF5355_REG4_POWER_DOWN_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 6)) | ((x & 0x1) << 6))


@portable
def ADF5355_REG4_R_COUNTER_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 15) & 0x3FF)


@portable
def ADF5355_REG4_R_COUNTER(x: TInt32) -> TInt32:
    return int32((x & 0x3FF) << 15)


@portable
def ADF5355_REG4_R_COUNTER_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3FF << 15)) | ((x & 0x3FF) << 15))


@portable
def ADF5355_REG4_R_DIVIDER_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 25) & 0x1)


@portable
def ADF5355_REG4_R_DIVIDER(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 25)


@portable
def ADF5355_REG4_R_DIVIDER_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 25)) | ((x & 0x1) << 25))


@portable
def ADF5355_REG4_R_DOUBLER_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 26) & 0x1)


@portable
def ADF5355_REG4_R_DOUBLER(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 26)


@portable
def ADF5355_REG4_R_DOUBLER_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 26)) | ((x & 0x1) << 26))


@portable
def ADF5355_REG4_REF_MODE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 9) & 0x1)


@portable
def ADF5355_REG4_REF_MODE(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 9)


@portable
def ADF5355_REG4_REF_MODE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 9)) | ((x & 0x1) << 9))


@portable
def ADF5355_REG6_BLEED_POLARITY_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 31) & 0x1)


@portable
def ADF5355_REG6_BLEED_POLARITY(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 31)


@portable
def ADF5355_REG6_BLEED_POLARITY_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 31)) | ((x & 0x1) << 31))


@portable
def ADF5355_REG6_CP_BLEED_CURRENT_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 13) & 0xFF)


@portable
def ADF5355_REG6_CP_BLEED_CURRENT(x: TInt32) -> TInt32:
    return int32((x & 0xFF) << 13)


@portable
def ADF5355_REG6_CP_BLEED_CURRENT_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0xFF << 13)) | ((x & 0xFF) << 13))


@portable
def ADF5355_REG6_FB_SELECT_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 24) & 0x1)


@portable
def ADF5355_REG6_FB_SELECT(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 24)


@portable
def ADF5355_REG6_FB_SELECT_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 24)) | ((x & 0x1) << 24))


@portable
def ADF5355_REG6_GATE_BLEED_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 30) & 0x1)


@portable
def ADF5355_REG6_GATE_BLEED(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 30)


@portable
def ADF5355_REG6_GATE_BLEED_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 30)) | ((x & 0x1) << 30))


@portable
def ADF5355_REG6_MUTE_TILL_LD_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 11) & 0x1)


@portable
def ADF5355_REG6_MUTE_TILL_LD(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 11)


@portable
def ADF5355_REG6_MUTE_TILL_LD_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 11)) | ((x & 0x1) << 11))


@portable
def ADF5355_REG6_NEGATIVE_BLEED_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 29) & 0x1)


@portable
def ADF5355_REG6_NEGATIVE_BLEED(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 29)


@portable
def ADF5355_REG6_NEGATIVE_BLEED_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 29)) | ((x & 0x1) << 29))


@portable
def ADF5355_REG6_RF_DIVIDER_SELECT_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 21) & 0x7)


@portable
def ADF5355_REG6_RF_DIVIDER_SELECT(x: TInt32) -> TInt32:
    return int32((x & 0x7) << 21)


@portable
def ADF5355_REG6_RF_DIVIDER_SELECT_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x7 << 21)) | ((x & 0x7) << 21))


@portable
def ADF5355_REG6_RF_OUTPUT_A_ENABLE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 6) & 0x1)


@portable
def ADF5355_REG6_RF_OUTPUT_A_ENABLE(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 6)


@portable
def ADF5355_REG6_RF_OUTPUT_A_ENABLE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 6)) | ((x & 0x1) << 6))


@portable
def ADF5355_REG6_RF_OUTPUT_A_POWER_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0x3)


@portable
def ADF5355_REG6_RF_OUTPUT_A_POWER(x: TInt32) -> TInt32:
    return int32((x & 0x3) << 4)


@portable
def ADF5355_REG6_RF_OUTPUT_A_POWER_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3 << 4)) | ((x & 0x3) << 4))


@portable
def ADF5355_REG6_RF_OUTPUT_B_ENABLE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 10) & 0x1)


@portable
def ADF5355_REG6_RF_OUTPUT_B_ENABLE(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 10)


@portable
def ADF5355_REG6_RF_OUTPUT_B_ENABLE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 10)) | ((x & 0x1) << 10))


@portable
def ADF5355_REG7_FRAC_N_LD_PRECISION_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 5) & 0x3)


@portable
def ADF5355_REG7_FRAC_N_LD_PRECISION(x: TInt32) -> TInt32:
    return int32((x & 0x3) << 5)


@portable
def ADF5355_REG7_FRAC_N_LD_PRECISION_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3 << 5)) | ((x & 0x3) << 5))


@portable
def ADF5355_REG7_LD_CYCLE_COUNT_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 8) & 0x3)


@portable
def ADF5355_REG7_LD_CYCLE_COUNT(x: TInt32) -> TInt32:
    return int32((x & 0x3) << 8)


@portable
def ADF5355_REG7_LD_CYCLE_COUNT_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3 << 8)) | ((x & 0x3) << 8))


@portable
def ADF5355_REG7_LD_MODE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0x1)


@portable
def ADF5355_REG7_LD_MODE(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 4)


@portable
def ADF5355_REG7_LD_MODE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 4)) | ((x & 0x1) << 4))


@portable
def ADF5355_REG7_LE_SEL_SYNC_EDGE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 27) & 0x1)


@portable
def ADF5355_REG7_LE_SEL_SYNC_EDGE(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 27)


@portable
def ADF5355_REG7_LE_SEL_SYNC_EDGE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 27)) | ((x & 0x1) << 27))


@portable
def ADF5355_REG7_LE_SYNC_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 25) & 0x1)


@portable
def ADF5355_REG7_LE_SYNC(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 25)


@portable
def ADF5355_REG7_LE_SYNC_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 25)) | ((x & 0x1) << 25))


@portable
def ADF5355_REG7_LOL_MODE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 7) & 0x1)


@portable
def ADF5355_REG7_LOL_MODE(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 7)


@portable
def ADF5355_REG7_LOL_MODE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 7)) | ((x & 0x1) << 7))


@portable
def ADF5355_REG9_AUTOCAL_TIMEOUT_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 9) & 0x1F)


@portable
def ADF5355_REG9_AUTOCAL_TIMEOUT(x: TInt32) -> TInt32:
    return int32((x & 0x1F) << 9)


@portable
def ADF5355_REG9_AUTOCAL_TIMEOUT_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1F << 9)) | ((x & 0x1F) << 9))


@portable
def ADF5355_REG9_SYNTH_LOCK_TIMEOUT_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0x1F)


@portable
def ADF5355_REG9_SYNTH_LOCK_TIMEOUT(x: TInt32) -> TInt32:
    return int32((x & 0x1F) << 4)


@portable
def ADF5355_REG9_SYNTH_LOCK_TIMEOUT_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1F << 4)) | ((x & 0x1F) << 4))


@portable
def ADF5355_REG9_TIMEOUT_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 14) & 0x3FF)


@portable
def ADF5355_REG9_TIMEOUT(x: TInt32) -> TInt32:
    return int32((x & 0x3FF) << 14)


@portable
def ADF5355_REG9_TIMEOUT_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3FF << 14)) | ((x & 0x3FF) << 14))


@portable
def ADF5355_REG9_VCO_BAND_DIVISION_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 24) & 0xFF)


@portable
def ADF5355_REG9_VCO_BAND_DIVISION(x: TInt32) -> TInt32:
    return int32((x & 0xFF) << 24)


@portable
def ADF5355_REG9_VCO_BAND_DIVISION_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0xFF << 24)) | ((x & 0xFF) << 24))


@portable
def ADF5355_REG10_ADC_CLK_DIV_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 6) & 0xFF)


@portable
def ADF5355_REG10_ADC_CLK_DIV(x: TInt32) -> TInt32:
    return int32((x & 0xFF) << 6)


@portable
def ADF5355_REG10_ADC_CLK_DIV_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0xFF << 6)) | ((x & 0xFF) << 6))


@portable
def ADF5355_REG10_ADC_CONV_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 5) & 0x1)


@portable
def ADF5355_REG10_ADC_CONV(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 5)


@portable
def ADF5355_REG10_ADC_CONV_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 5)) | ((x & 0x1) << 5))


@portable
def ADF5355_REG10_ADC_ENABLE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0x1)


@portable
def ADF5355_REG10_ADC_ENABLE(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 4)


@portable
def ADF5355_REG10_ADC_ENABLE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 4)) | ((x & 0x1) << 4))


@portable
def ADF5355_REG11_VCO_BAND_HOLD_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 24) & 0x1)


@portable
def ADF5355_REG11_VCO_BAND_HOLD(x: TInt32) -> TInt32:
    return int32((x & 0x1) << 24)


@portable
def ADF5355_REG11_VCO_BAND_HOLD_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x1 << 24)) | ((x & 0x1) << 24))


@portable
def ADF5355_REG12_PHASE_RESYNC_CLK_VALUE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 12) & 0xFFFFF)


@portable
def ADF5355_REG12_PHASE_RESYNC_CLK_VALUE(x: TInt32) -> TInt32:
    return int32((x & 0xFFFFF) << 12)


@portable
def ADF5355_REG12_PHASE_RESYNC_CLK_VALUE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0xFFFFF << 12)) | ((x & 0xFFFFF) << 12))


@portable
def ADF5355_REG13_AUX_FRAC_MSB_VALUE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 18) & 0x3FFF)


@portable
def ADF5355_REG13_AUX_FRAC_MSB_VALUE(x: TInt32) -> TInt32:
    return int32((x & 0x3FFF) << 18)


@portable
def ADF5355_REG13_AUX_FRAC_MSB_VALUE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3FFF << 18)) | ((x & 0x3FFF) << 18))


@portable
def ADF5355_REG13_AUX_MOD_MSB_VALUE_GET(reg: TInt32) -> TInt32:
    return int32((reg >> 4) & 0x3FFF)


@portable
def ADF5355_REG13_AUX_MOD_MSB_VALUE(x: TInt32) -> TInt32:
    return int32((x & 0x3FFF) << 4)


@portable
def ADF5355_REG13_AUX_MOD_MSB_VALUE_UPDATE(reg: TInt32, x: TInt32) -> TInt32:
    return int32((reg & ~(0x3FFF << 4)) | ((x & 0x3FFF) << 4))


ADF5355_NUM_REGS = 14
