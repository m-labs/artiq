import numpy

from artiq.language.core import *
from artiq.language.types import *
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.coredevice import spi2 as spi
from artiq.language.units import us


@portable
def shuttler_volt_to_mu(volt):
    # TODO: Check arg, raise exception if exceeds shuttler limit
    return int(round((1 << 14) * (volt / 20.0))) & 0x3fff


class Config:
    kernel_invariants = {
        "core", "channel", "target_base", "target_read",
        "target_gain", "target_offset", "target_clr"
    }

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_base   = channel << 8
        self.target_read   = 1 << 6
        self.target_gain   = 0 * (1 << 4)
        self.target_offset = 1 * (1 << 4)
        self.target_clr    = 1 * (1 << 5)

    @kernel
    def set_clr(self, clr):
        rtio_output(self.target_base | self.target_clr, clr)
    
    @kernel
    def set_gain(self, channel, gain):
        rtio_output(self.target_base | self.target_gain | channel, gain)
    
    @kernel
    def get_gain(self, channel):
        rtio_output(self.target_base | self.target_gain |
            self.target_read | channel, 0)
        return rtio_input_data(self.channel)
    
    @kernel
    def set_offset(self, channel, offset):
        rtio_output(self.target_base | self.target_offset | channel, offset)

    @kernel
    def get_offset(self, channel):
        rtio_output(self.target_base | self.target_offset |
            self.target_read | channel, 0)
        return rtio_input_data(self.channel)


class Volt:
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def set_waveform(self, a0: TInt32, a1: TInt32, a2: TInt64, a3: TInt64):
        pdq_words = [
            a0,
            a1,
            a1 >> 16,
            a2 & 0xFFFF,
            (a2 >> 16) & 0xFFFF,
            (a2 >> 32) & 0xFFFF,
            a3 & 0xFFFF,
            (a3 >> 16) & 0xFFFF,
            (a3 >> 32) & 0xFFFF,
        ]

        for i in range(len(pdq_words)):
            rtio_output(self.target_o | i, pdq_words[i])
            delay_mu(int64(self.core.ref_multiplier))


class Dds:
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def set_waveform(self, b0: TInt32, b1: TInt32, b2: TInt64, b3: TInt64,
            c0: TInt32, c1: TInt32, c2: TInt32):
        pdq_words = [
            b0,
            b1,
            b1 >> 16,
            b2 & 0xFFFF,
            (b2 >> 16) & 0xFFFF,
            (b2 >> 32) & 0xFFFF,
            b3 & 0xFFFF,
            (b3 >> 16) & 0xFFFF,
            (b3 >> 32) & 0xFFFF,
            c0,
            c1,
            c1 >> 16,
            c2,
            c2 >> 16,
        ]

        for i in range(len(pdq_words)):
            rtio_output(self.target_o | i, pdq_words[i])
            delay_mu(int64(self.core.ref_multiplier))


class Trigger:
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def trigger(self, trig_out):
        rtio_output(self.target_o, trig_out)


RELAY_SPI_CONFIG = (0*spi.SPI_OFFLINE | 1*spi.SPI_END |
                    0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
                    0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
                    0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

ADC_SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
                  0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
                  1*spi.SPI_CLK_POLARITY | 1*spi.SPI_CLK_PHASE |
                  0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

# SPI clock write and read dividers
# CS should assert at least 9.5 ns after clk pulse
SPIT_RELAY_WR = 4
# 25 ns high/low pulse hold (limiting for write)
SPIT_ADC_WR = 4
SPIT_ADC_RD = 16

# SPI CS line
CS_RELAY = 1 << 0
CS_LED = 1 << 1
CS_ADC = 1 << 0

# Referenced AD4115 registers
_AD4115_REG_STATUS = 0x00
_AD4115_REG_ADCMODE = 0x01
_AD4115_REG_DATA = 0x04
_AD4115_REG_ID = 0x07
_AD4115_REG_CH0 = 0x10
_AD4115_REG_SETUPCON0 = 0x20


class Relay:
    kernel_invariant = {"core", "bus"}

    def __init__(self, dmgr, spi_device, core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)
    
    @kernel
    def init(self):
        self.bus.set_config_mu(
            RELAY_SPI_CONFIG, 16, SPIT_RELAY_WR, CS_RELAY | CS_LED)

    @kernel
    def set_led(self, leds: TInt32):
        self.bus.write(leds << 16)


class ADC:
    kernel_invariant = {"core", "bus"}

    def __init__(self, dmgr, spi_device, core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)

    @kernel
    def read_id(self) -> TInt32:
    @kernel
    def read8(self, addr: TInt32) -> TInt32:
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT,
            16, SPIT_ADC_RD, CS_ADC)
        self.bus.write((addr | 0x40) << 24)
        return self.bus.read() & 0xff

    @kernel
    def read16(self, addr: TInt32) -> TInt32:
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT,
            24, SPIT_ADC_RD, CS_ADC)
        self.bus.write((addr | 0x40) << 24)
        return self.bus.read() & 0xffff

    @kernel
    def read24(self, addr: TInt32) -> TInt32:
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT,
            32, SPIT_ADC_RD, CS_ADC)
        self.bus.write((addr | 0x40) << 24)
        return self.bus.read() & 0xffffff

    @kernel
    def write8(self, addr: TInt32, data: TInt32):
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END, 16, SPIT_ADC_WR, CS_ADC)
        self.bus.write(addr << 24 | (data & 0xff) << 16)

    @kernel
    def write16(self, addr: TInt32, data: TInt32):
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END, 24, SPIT_ADC_WR, CS_ADC)
        self.bus.write(addr << 24 | (data & 0xffff) << 8)

    @kernel
    def write24(self, addr: TInt32, data: TInt32):
        self.bus.set_config_mu(
            ADC_SPI_CONFIG | spi.SPI_END, 32, SPIT_ADC_WR, CS_ADC)
        self.bus.write(addr << 24 | (data & 0xffffff))

        delay(100*us)
        adc_code = self.read24(_AD4115_REG_DATA)
        return ((adc_code / (1 << 23)) - 1) * 2.5 / 0.1
    
    @kernel
    def calibrate(self, volts, trigger, config, samples=[-5.0, 0.0, 5.0]):
        assert len(volts) == 16
        assert len(samples) > 1

        measurements = [0.0] * len(samples)

        for ch in range(16):
            # Find the average slope rate and offset
            for i in range(len(samples)):
                self.core.break_realtime()
                volts[ch].set_waveform(
                    shuttler_volt_to_mu(samples[i]), 0, 0, 0)
                trigger.trigger(1 << ch)
                measurements[i] = self.read_ch(ch)

            # Find the average output slope
            slope_sum = 0.0
            for i in range(len(samples) - 1):
                slope_sum += (measurements[i+1] - measurements[i])/(samples[i+1] - samples[i])
            slope_avg = slope_sum / (len(samples) - 1)

            gain_code = int32(1 / slope_avg * (2 ** 16)) & 0xffff

            # Scale the measurements by 1/slope, find average offset
            offset_sum = 0.0
            for i in range(len(samples)):
                offset_sum += (measurements[i] / slope_avg) - samples[i]
            offset_avg = offset_sum / len(samples)

            offset_code = shuttler_volt_to_mu(-offset_avg)

            self.core.break_realtime()
            config.set_gain(ch, gain_code)

            delay_mu(int64(self.core.ref_multiplier))
            config.set_offset(ch, offset_code)
