from artiq.experiment import *
from artiq.coredevice.ad9516_reg import *


class StartupKernel(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")
        self.setattr_device("ad9154")

    @kernel
    def run(self):
        self.core.reset()
        self.ad9154.jesd_enable(0)
        self.ad9154.init()
        self.clock_setup()

    @kernel
    def clock_setup(self):
        # reset
        self.ad9154.clock_write(AD9516_SERIAL_PORT_CONFIGURATION,
                AD9516_SOFT_RESET | AD9516_SOFT_RESET_MIRRORED |
                AD9516_LONG_INSTRUCTION | AD9516_LONG_INSTRUCTION_MIRRORED |
                AD9516_SDO_ACTIVE | AD9516_SDO_ACTIVE_MIRRORED)
        self.ad9154.clock_write(AD9516_SERIAL_PORT_CONFIGURATION,
                AD9516_LONG_INSTRUCTION | AD9516_LONG_INSTRUCTION_MIRRORED |
                AD9516_SDO_ACTIVE | AD9516_SDO_ACTIVE_MIRRORED)
        if self.ad9154.clock_read(AD9516_PART_ID) != 0x41:
            raise ValueError("AD9516 not found")

        # use clk input, dclk=clk/4
        self.ad9154.clock_write(AD9516_PFD_AND_CHARGE_PUMP, 1*AD9516_PLL_POWER_DOWN |
                0*AD9516_CHARGE_PUMP_MODE)
        self.ad9154.clock_write(AD9516_VCO_DIVIDER, 2)
        self.ad9154.clock_write(AD9516_INPUT_CLKS, 0*AD9516_SELECT_VCO_OR_CLK |
                0*AD9516_BYPASS_VCO_DIVIDER)

        self.ad9154.clock_write(AD9516_OUT0, 2*AD9516_OUT0_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT2, 2*AD9516_OUT2_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT3, 2*AD9516_OUT3_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT4, 2*AD9516_OUT4_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT5, 2*AD9516_OUT5_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT8, 1*AD9516_OUT8_POWER_DOWN)

        # DAC deviceclk, clk/1
        self.ad9154.clock_write(AD9516_DIVIDER_0_2, AD9516_DIVIDER_0_DIRECT_TO_OUTPUT)
        self.ad9154.clock_write(AD9516_OUT1, 0*AD9516_OUT1_POWER_DOWN |
                2*AD9516_OUT1_LVPECLDIFFERENTIAL_VOLTAGE)

        # FPGA deviceclk, dclk/4
        self.ad9154.clock_write(AD9516_DIVIDER_4_3, AD9516_DIVIDER_4_BYPASS_2)
        self.ad9154.clock_write(AD9516_DIVIDER_4_0,
            (4//2-1)*AD9516_DIVIDER_0_HIGH_CYCLES |
            (4//2-1)*AD9516_DIVIDER_0_LOW_CYCLES)
        self.ad9154.clock_write(AD9516_DIVIDER_4_4, 1*AD9516_DIVIDER_4_DCCOFF)
        self.ad9154.clock_write(AD9516_OUT9, 1*AD9516_OUT9_LVDS_OUTPUT_CURRENT |
                2*AD9516_OUT9_LVDS_CMOS_OUTPUT_POLARITY |
                0*AD9516_OUT9_SELECT_LVDS_CMOS)

        # sysref f_data*S/(K*F), dclk/64
        self.ad9154.clock_write(AD9516_DIVIDER_3_0, (32//2-1)*AD9516_DIVIDER_3_HIGH_CYCLES_1 |
                (32//2-1)*AD9516_DIVIDER_3_LOW_CYCLES_1)
        self.ad9154.clock_write(AD9516_DIVIDER_3_1, 0*AD9516_DIVIDER_3_PHASE_OFFSET_1 |
                0*AD9516_DIVIDER_3_PHASE_OFFSET_2)
        self.ad9154.clock_write(AD9516_DIVIDER_3_2, (2//2-1)*AD9516_DIVIDER_3_HIGH_CYCLES_2 |
                (2//2-1)*AD9516_DIVIDER_3_LOW_CYCLES_2)
        self.ad9154.clock_write(AD9516_DIVIDER_3_3, 0*AD9516_DIVIDER_3_NOSYNC |
                0*AD9516_DIVIDER_3_BYPASS_1 | 0*AD9516_DIVIDER_3_BYPASS_2)
        self.ad9154.clock_write(AD9516_DIVIDER_3_4, 1*AD9516_DIVIDER_3_DCCOFF)
        self.ad9154.clock_write(AD9516_OUT6, 1*AD9516_OUT6_LVDS_OUTPUT_CURRENT |
                2*AD9516_OUT6_LVDS_CMOS_OUTPUT_POLARITY |
                0*AD9516_OUT6_SELECT_LVDS_CMOS)
        self.ad9154.clock_write(AD9516_OUT7, 1*AD9516_OUT7_LVDS_OUTPUT_CURRENT |
                2*AD9516_OUT7_LVDS_CMOS_OUTPUT_POLARITY |
                0*AD9516_OUT7_SELECT_LVDS_CMOS)

        self.ad9154.clock_write(AD9516_UPDATE_ALL_REGISTERS, 1)
