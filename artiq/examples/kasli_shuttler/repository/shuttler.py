from artiq.experiment import *
from artiq.coredevice.shuttler import shuttler_volt_to_mu

DAC_Fs_MHZ = 125
CORDIC_GAIN = 1.64676

@portable
def shuttler_phase_offset(offset_degree):
    return round(offset_degree / 360 * (2 ** 16))

@portable
def shuttler_freq_mu(freq_mhz):
    return round(float(2) ** 32 / DAC_Fs_MHZ * freq_mhz)

@portable
def shuttler_chirp_rate_mu(freq_mhz_per_us):
    return round(float(2) ** 32 * freq_mhz_per_us / (DAC_Fs_MHZ ** 2))

@portable
def shuttler_freq_sweep(start_f_MHz, end_f_MHz, time_us):
    return shuttler_chirp_rate_mu((end_f_MHz - start_f_MHz)/(time_us))

@portable
def shuttler_volt_amp_mu(volt):
    return shuttler_volt_to_mu(volt)

@portable
def shuttler_volt_damp_mu(volt_per_us):
    return round(float(2) ** 32 * (volt_per_us / 20) / DAC_Fs_MHZ)

@portable
def shuttler_volt_ddamp_mu(volt_per_us_square):
    return round(float(2) ** 48 * (volt_per_us_square / 20) * 2 / (DAC_Fs_MHZ ** 2))

@portable
def shuttler_volt_dddamp_mu(volt_per_us_cube):
    return round(float(2) ** 48 * (volt_per_us_cube / 20) * 6 / (DAC_Fs_MHZ ** 3))

@portable
def shuttler_dds_amp_mu(volt):
    return shuttler_volt_amp_mu(volt / CORDIC_GAIN)

@portable
def shuttler_dds_damp_mu(volt_per_us):
    return shuttler_volt_damp_mu(volt_per_us / CORDIC_GAIN)

@portable
def shuttler_dds_ddamp_mu(volt_per_us_square):
    return shuttler_volt_ddamp_mu(volt_per_us_square / CORDIC_GAIN)

@portable
def shuttler_dds_dddamp_mu(volt_per_us_cube):
    return shuttler_volt_dddamp_mu(volt_per_us_cube / CORDIC_GAIN)

class Shuttler(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("scheduler")
        self.shuttler0_leds = [ self.get_device("shuttler0_led{}".format(i)) for i in range(2) ]
        self.setattr_device("shuttler0_config")
        self.setattr_device("shuttler0_trigger")
        self.shuttler0_dcbias = [ self.get_device("shuttler0_dcbias{}".format(i)) for i in range(16) ]
        self.shuttler0_dds = [ self.get_device("shuttler0_dds{}".format(i)) for i in range(16) ]
        self.setattr_device("shuttler0_relay")
        self.setattr_device("shuttler0_adc")
        

    @kernel
    def record(self):
        with self.core_dma.record("example_waveform"):
            self.example_waveform()

    @kernel
    def init(self):
        self.led()
        self.relay_init()
        self.adc_init()
        self.shuttler_reset()

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        self.init()

        self.record()
        example_waveform_handle = self.core_dma.get_handle("example_waveform")

        print("Example Waveforms are on OUT0 and OUT1")
        self.core.break_realtime()
        while not(self.scheduler.check_termination()):
            delay(1*s)
            self.core_dma.playback_handle(example_waveform_handle)

    @kernel
    def shuttler_reset(self):
        for i in range(16):
            self.shuttler_channel_reset(i)
            # To avoid RTIO Underflow
            delay(50*us)

    @kernel
    def shuttler_channel_reset(self, ch):
        self.shuttler0_dcbias[ch].set_waveform(
            a0=0,
            a1=0,
            a2=0,
            a3=0,
        )
        self.shuttler0_dds[ch].set_waveform(
            b0=0,
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=0,
            c2=0,
        )
        self.shuttler0_trigger.trigger(1 << ch)

    @kernel
    def example_waveform(self):
        # Equation of Output Waveform
        #   w(t_us) = a(t_us) + b(t_us) * cos(c(t_us))
        # Step 1:
        #   Enable the Output Relay of OUT0 and OUT1
        # Step 2: Cosine Wave Frequency Sweep from 10kHz to 50kHz in 500us
        #   OUT0: b(t_us) = 1
        #         c(t_us) = 2 * pi * (0.08 * t_us ^ 2 + 0.01 * t_us)
        #   OUT1: b(t_us) = 1
        #         c(t_us) = 2 * pi * (0.05 * t_us)
        # Step 3(after 500us): Cosine Wave with 180 Degree Phase Offset
        #   OUT0: b(t_us) = 1
        #         c(t_us) = 2 * pi * (0.05 * t_us) + pi
        #   OUT1: b(t_us) = 1
        #         c(t_us) = 2 * pi * (0.05 * t_us)
        # Step 4(after 500us): Cosine Wave with Amplitude Envelop
        #   OUT0: b(t_us) = -0.0001367187 * t_us ^ 2 + 0.06835937 * t_us
        #         c(t_us) = 2 * pi * (0.05 * t_us)
        #   OUT1: b(t_us) = -0.0001367187 * t_us ^ 2 + 0.06835937 * t_us
        #         c(t_us) = 0
        # Step 5(after 500us): Sawtooth Wave Modulated with 50kHz Cosine Wave 
        #   OUT0: a(t_us) = 0.01 * t_us - 5
        #         b(t_us) = 1
        #         c(t_us) = 2 * pi * (0.05 * t_us)
        #   OUT1: a(t_us) = 0.01 * t_us - 5
        # Step 6(after 1000us): A Combination of Previous Waveforms
        #   OUT0: a(t_us) = 0.01 * t_us - 5
        #         b(t_us) = -0.0001367187 * t_us ^ 2 + 0.06835937 * t_us
        #         c(t_us) = 2 * pi * (0.08 * t_us ^ 2 + 0.01 * t_us)
        # Step 7(after 500us): Mirrored Waveform in Step 6
        #   OUT0: a(t_us) = 2.5 + -0.01 * (1000 ^ 2) * t_us
        #         b(t_us) = 0.0001367187 * t_us ^ 2 - 0.06835937 * t_us
        #         c(t_us) = 2 * pi * (-0.08 * t_us ^ 2 + 0.05 * t_us) + pi
        # Step 8(after 500us):
        #   Disable Output Relay of OUT0 and OUT1
        #   Reset OUT0 and OUT1
    
        ## Step 1 ##
        self.shuttler0_relay.enable(0b11)

        ## Step 2 ##
        start_f_MHz = 0.01
        end_f_MHz = 0.05
        duration_us = 500
        # OUT0 and OUT1 have their frequency and phase aligned at 500us
        self.shuttler0_dds[0].set_waveform(
            b0=shuttler_dds_amp_mu(1.0),
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=shuttler_freq_mu(start_f_MHz),
            c2=shuttler_freq_sweep(start_f_MHz, end_f_MHz, duration_us),
        )
        self.shuttler0_dds[1].set_waveform(
            b0=shuttler_dds_amp_mu(1.0),
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=shuttler_freq_mu(end_f_MHz),
            c2=0,
        )
        self.shuttler0_trigger.trigger(0b11)
        delay(500*us)

        ## Step 3 ##
        # OUT0 and OUT1 has 180 degree phase difference
        self.shuttler0_dds[0].set_waveform(
            b0=shuttler_dds_amp_mu(1.0),
            b1=0,
            b2=0,
            b3=0,
            c0=shuttler_phase_offset(180.0),
            c1=shuttler_freq_mu(end_f_MHz),
            c2=0,
        )
        # Phase and Output Setting of OUT1 is retained 
        #   if the channel is not triggered or config is not cleared
        self.shuttler0_trigger.trigger(0b1)
        delay(500*us)

        ## Step 4 ##
        #     b(0) = 0, b(250) = 8.545, b(500) = 0
        self.shuttler0_dds[0].set_waveform(
            b0=0,
            b1=shuttler_dds_damp_mu(0.06835937),
            b2=shuttler_dds_ddamp_mu(-0.0001367187),
            b3=0,
            c0=0,
            c1=shuttler_freq_mu(end_f_MHz),
            c2=0,
        )
        self.shuttler0_dds[1].set_waveform(
            b0=0,
            b1=shuttler_dds_damp_mu(0.06835937),
            b2=shuttler_dds_ddamp_mu(-0.0001367187),
            b3=0,
            c0=0,
            c1=0,
            c2=0,
        )
        self.shuttler0_trigger.trigger(0b11)
        delay(500*us)

        ## Step 5 ##
        self.shuttler0_dcbias[0].set_waveform(
            a0=shuttler_volt_amp_mu(-5.0),
            a1=int32(shuttler_volt_damp_mu(0.01)),
            a2=0,
            a3=0,
        )
        self.shuttler0_dds[0].set_waveform(
            b0=shuttler_dds_amp_mu(1.0),
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=shuttler_freq_mu(end_f_MHz),
            c2=0,
        )
        self.shuttler0_dcbias[1].set_waveform(
            a0=shuttler_volt_amp_mu(-5.0),
            a1=int32(shuttler_volt_damp_mu(0.01)),
            a2=0,
            a3=0,
        )
        self.shuttler0_dds[1].set_waveform(
            b0=0,
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=0,
            c2=0,
        )
        self.shuttler0_trigger.trigger(0b11)
        delay(1000*us)
        
        ## Step 6 ##
        self.shuttler0_dcbias[0].set_waveform(
            a0=shuttler_volt_amp_mu(-2.5),
            a1=int32(shuttler_volt_damp_mu(0.01)),
            a2=0,
            a3=0,
        )
        self.shuttler0_dds[0].set_waveform(
            b0=0,
            b1=shuttler_dds_damp_mu(0.06835937),
            b2=shuttler_dds_ddamp_mu(-0.0001367187),
            b3=0,
            c0=0,
            c1=shuttler_freq_mu(start_f_MHz),
            c2=shuttler_freq_sweep(start_f_MHz, end_f_MHz, duration_us),
        )
        self.shuttler0_trigger.trigger(0b1)
        self.shuttler_channel_reset(1)
        delay(500*us)

        ## Step 7 ##
        self.shuttler0_dcbias[0].set_waveform(
            a0=shuttler_volt_amp_mu(2.5),
            a1=int32(shuttler_volt_damp_mu(-0.01)),
            a2=0,
            a3=0,
        )
        self.shuttler0_dds[0].set_waveform(
            b0=0,
            b1=shuttler_dds_damp_mu(-0.06835937),
            b2=shuttler_dds_ddamp_mu(0.0001367187),
            b3=0,
            c0=shuttler_phase_offset(180.0),
            c1=shuttler_freq_mu(end_f_MHz),
            c2=shuttler_freq_sweep(end_f_MHz, start_f_MHz, duration_us),
        )
        self.shuttler0_trigger.trigger(0b1)
        delay(500*us)

        ## Step 8 ##
        self.shuttler0_relay.enable(0)
        self.shuttler_channel_reset(0)
        self.shuttler_channel_reset(1)

    @kernel
    def led(self):
        for i in range(2):
            for j in range(3):
                self.shuttler0_leds[i].pulse(.1*s)
                delay(.1*s)

    @kernel
    def relay_init(self):
        self.shuttler0_relay.init()
        self.shuttler0_relay.enable(0x0000)

    @kernel
    def adc_init(self):
        delay_mu(int64(self.core.ref_multiplier))
        self.shuttler0_adc.power_up()

        delay_mu(int64(self.core.ref_multiplier))
        assert self.shuttler0_adc.read_id() >> 4 == 0x038d

        delay_mu(int64(self.core.ref_multiplier))
        # The actual output voltage is limited by the hardware, the calculated calibration gain and offset.
        # For example, if the system has a calibration gain of 1.06, then the max output voltage = 10 / 1.06 = 9.43V.
        # Setting a value larger than 9.43V will result in overflow.
        self.shuttler0_adc.calibrate(self.shuttler0_dcbias, self.shuttler0_trigger, self.shuttler0_config)
