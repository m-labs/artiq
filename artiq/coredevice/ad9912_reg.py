# auto-generated, do not edit
from artiq.language.core import portable
from artiq.language.types import TInt32

AD9912_SER_CONF =                       0x000
# default: 0x00, access: R/W
@portable
def AD9912_SDOACTIVE_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 0

@portable
def AD9912_SDOACTIVE_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_LSBFIRST_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 1

@portable
def AD9912_LSBFIRST_GET(x: TInt32) -> TInt32:
    return (x >> 1) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_SOFTRESET_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 2

@portable
def AD9912_SOFTRESET_GET(x: TInt32) -> TInt32:
    return (x >> 2) & 0x1

# default: 0x01, access: R/W
@portable
def AD9912_LONGINSN_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 3

@portable
def AD9912_LONGINSN_GET(x: TInt32) -> TInt32:
    return (x >> 3) & 0x1

# default: 0x01, access: R/W
@portable
def AD9912_LONGINSN_M_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 4

@portable
def AD9912_LONGINSN_M_GET(x: TInt32) -> TInt32:
    return (x >> 4) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_SOFTRESET_M_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 5

@portable
def AD9912_SOFTRESET_M_GET(x: TInt32) -> TInt32:
    return (x >> 5) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_LSBFIRST_M_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 6

@portable
def AD9912_LSBFIRST_M_GET(x: TInt32) -> TInt32:
    return (x >> 6) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_SDOACTIVE_M_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 7

@portable
def AD9912_SDOACTIVE_M_GET(x: TInt32) -> TInt32:
    return (x >> 7) & 0x1


AD9912_PRODIDL =                        0x002

AD9912_PRODIDH =                        0x003

AD9912_SER_OPT1 =                       0x004
# default: 0x00, access: R/W
@portable
def AD9912_READ_BUF_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 0

@portable
def AD9912_READ_BUF_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x1


AD9912_SER_OPT2 =                       0x005
# default: 0x00, access: R/W
@portable
def AD9912_RED_UPDATE_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 0

@portable
def AD9912_RED_UPDATE_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x1


AD9912_PWRCNTRL1 =                      0x010
# default: 0x00, access: R/W
@portable
def AD9912_PD_DIGITAL_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 0

@portable
def AD9912_PD_DIGITAL_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_PD_FULL_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 1

@portable
def AD9912_PD_FULL_GET(x: TInt32) -> TInt32:
    return (x >> 1) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_PD_SYSCLK_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 4

@portable
def AD9912_PD_SYSCLK_GET(x: TInt32) -> TInt32:
    return (x >> 4) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_EN_DOUBLER_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 5

@portable
def AD9912_EN_DOUBLER_GET(x: TInt32) -> TInt32:
    return (x >> 5) & 0x1

# default: 0x01, access: R/W
@portable
def AD9912_EN_CMOS_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 6

@portable
def AD9912_EN_CMOS_GET(x: TInt32) -> TInt32:
    return (x >> 6) & 0x1

# default: 0x01, access: R/W
@portable
def AD9912_PD_HSTL_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 7

@portable
def AD9912_PD_HSTL_GET(x: TInt32) -> TInt32:
    return (x >> 7) & 0x1


AD9912_PWRCNTRL2 =                      0x012
# default: 0x00, access: R/W
@portable
def AD9912_DDS_RESET_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 0

@portable
def AD9912_DDS_RESET_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x1


AD9912_PWRCNTRL3 =                      0x013
# default: 0x00, access: R/W
@portable
def AD9912_S_DIV_RESET_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 1

@portable
def AD9912_S_DIV_RESET_GET(x: TInt32) -> TInt32:
    return (x >> 1) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_S_DIV2_RESET_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 3

@portable
def AD9912_S_DIV2_RESET_GET(x: TInt32) -> TInt32:
    return (x >> 3) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_PD_FUND_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 7

@portable
def AD9912_PD_FUND_GET(x: TInt32) -> TInt32:
    return (x >> 7) & 0x1


AD9912_N_DIV =                          0x020

AD9912_PLLCFG =                         0x022
# default: 0x00, access: R/W
@portable
def AD9912_PLL_ICP_SET(x: TInt32) -> TInt32:
    return (x & 0x3) << 0

@portable
def AD9912_PLL_ICP_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x3

# default: 0x01, access: R/W
@portable
def AD9912_VCO_RANGE_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 2

@portable
def AD9912_VCO_RANGE_GET(x: TInt32) -> TInt32:
    return (x >> 2) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_PLL_REF2X_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 3

@portable
def AD9912_PLL_REF2X_GET(x: TInt32) -> TInt32:
    return (x >> 3) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_VCO_AUTO_RANGE_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 7

@portable
def AD9912_VCO_AUTO_RANGE_GET(x: TInt32) -> TInt32:
    return (x >> 7) & 0x1


AD9912_S_DIVL =                         0x104

AD9912_S_DIVH =                         0x105

AD9912_S_DIV_CFG =                      0x106
# default: 0x01, access: R/W
@portable
def AD9912_S_DIV2_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 0

@portable
def AD9912_S_DIV2_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_S_DIV_FALL_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 7

@portable
def AD9912_S_DIV_FALL_GET(x: TInt32) -> TInt32:
    return (x >> 7) & 0x1


AD9912_FTW0 =                           0x1a6

AD9912_FTW1 =                           0x1a7

AD9912_FTW2 =                           0x1a8

AD9912_FTW3 =                           0x1a9

AD9912_FTW4 =                           0x1aa

AD9912_FTW5 =                           0x1ab

AD9912_POW0 =                           0x1ac

AD9912_POW1 =                           0x1ad

AD9912_HSTL =                           0x200
# default: 0x01, access: R/W
@portable
def AD9912_HSTL_CFG_SET(x: TInt32) -> TInt32:
    return (x & 0x3) << 0

@portable
def AD9912_HSTL_CFG_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x3

# default: 0x01, access: R/W
@portable
def AD9912_HSTL_OPOL_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 4

@portable
def AD9912_HSTL_OPOL_GET(x: TInt32) -> TInt32:
    return (x >> 4) & 0x1


AD9912_CMOS =                           0x201
# default: 0x00, access: R/W
@portable
def AD9912_CMOS_MUX_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 0

@portable
def AD9912_CMOS_MUX_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0x1


AD9912_FSC0 =                           0x40b

AD9912_FSC1 =                           0x40c

AD9912_HSR_A_CFG =                      0x500
# default: 0x00, access: R/W
@portable
def AD9912_HSR_A_HARMONIC_SET(x: TInt32) -> TInt32:
    return (x & 0xf) << 0

@portable
def AD9912_HSR_A_HARMONIC_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0xf

# default: 0x00, access: R/W
@portable
def AD9912_HSR_A_MAG2X_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 6

@portable
def AD9912_HSR_A_MAG2X_GET(x: TInt32) -> TInt32:
    return (x >> 6) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_HSR_A_EN_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 7

@portable
def AD9912_HSR_A_EN_GET(x: TInt32) -> TInt32:
    return (x >> 7) & 0x1


AD9912_HSR_A_MAG =                      0x501

AD9912_HSR_A_POW0 =                     0x503

AD9912_HSR_A_POW1 =                     0x504

AD9912_HSR_B_CFG =                      0x505
# default: 0x00, access: R/W
@portable
def AD9912_HSR_B_HARMONIC_SET(x: TInt32) -> TInt32:
    return (x & 0xf) << 0

@portable
def AD9912_HSR_B_HARMONIC_GET(x: TInt32) -> TInt32:
    return (x >> 0) & 0xf

# default: 0x00, access: R/W
@portable
def AD9912_HSR_B_MAG2X_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 6

@portable
def AD9912_HSR_B_MAG2X_GET(x: TInt32) -> TInt32:
    return (x >> 6) & 0x1

# default: 0x00, access: R/W
@portable
def AD9912_HSR_B_EN_SET(x: TInt32) -> TInt32:
    return (x & 0x1) << 7

@portable
def AD9912_HSR_B_EN_GET(x: TInt32) -> TInt32:
    return (x >> 7) & 0x1


AD9912_HSR_B_MAG =                      0x506

AD9912_HSR_B_POW0 =                     0x508

AD9912_HSR_B_POW1 =                     0x509
