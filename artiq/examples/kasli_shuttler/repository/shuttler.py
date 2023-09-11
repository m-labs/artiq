from artiq.experiment import *
from artiq.coredevice.shuttler import shuttler_volt_to_mu

DAC_Fs_MHZ = 125
CORDIC_GAIN = 1.64676

@portable
def pdq_phase_offset(offset_degree):
    return round(offset_degree / 360 * (2 ** 16))

@portable
def pdq_freq_mu(freq_mhz):
    return round(float(2) ** 32 / DAC_Fs_MHZ * freq_mhz)

@portable
def pdq_chirp_rate_mu(freq_mhz_per_us):
    return round(float(2) ** 32 * freq_mhz_per_us / (DAC_Fs_MHZ ** 2))

@portable
def pdq_freq_sweep(start_f_MHz, end_f_MHz, time_us):
    return pdq_chirp_rate_mu((end_f_MHz - start_f_MHz)/(time_us))

@portable
def pdq_volt_amp_mu(volt):
    return shuttler_volt_to_mu(volt)

@portable
def pdq_volt_damp_mu(volt_per_us):
    return round(float(2) ** 30 * (volt_per_us / 20) / DAC_Fs_MHZ)

@portable
def pdq_volt_ddamp_mu(volt_per_us_square):
    return round(float(2) ** 46 * (volt_per_us_square / 20) * 2 / (DAC_Fs_MHZ ** 2))

@portable
def pdq_volt_dddamp_mu(volt_per_us_cube):
    return round(float(2) ** 46 * (volt_per_us_cube / 20) * 6 / (DAC_Fs_MHZ ** 3))

@portable
def pdq_dds_amp_mu(volt):
    return pdq_volt_amp_mu(volt / CORDIC_GAIN)

@portable
def pdq_dds_damp_mu(volt_per_us):
    return pdq_volt_damp_mu(volt_per_us / CORDIC_GAIN)

@portable
def pdq_dds_ddamp_mu(volt_per_us_square):
    return pdq_volt_ddamp_mu(volt_per_us_square / CORDIC_GAIN)

@portable
def pdq_dds_dddamp_mu(volt_per_us_cube):
    return pdq_volt_dddamp_mu(volt_per_us_cube / CORDIC_GAIN)

class Shuttler(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("scheduler")
        self.leds = [ self.get_device("efc_led{}".format(i)) for i in range(2) ]
        self.setattr_device("pdq_config")
        self.setattr_device("pdq_trigger")
        self.pdq_volt = [ self.get_device("pdq{}_volt".format(i)) for i in range(16) ]
        self.pdq_dds = [ self.get_device("pdq{}_dds".format(i)) for i in range(16) ]
        self.setattr_device("afe_relay")
        self.setattr_device("afe_adc")
        

    @kernel
    def record(self):
        with self.core_dma.record("example_waveform"):
            self.example_waveform()

    @kernel
    def init(self):
        self.led()
        self.relay_init()
        self.adc_init()
        self.pdq_reset()

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
    def pdq_reset(self):
        for i in range(16):
            self.pdq_channel_reset(i)
            # To avoid RTIO Underflow
            delay(50*us)

    @kernel
    def pdq_channel_reset(self, ch):
        self.pdq_volt[ch].set_waveform(
            a0=0,
            a1=0,
            a2=0,
            a3=0,
        )
        self.pdq_dds[ch].set_waveform(
            b0=0,
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=0,
            c2=0,
        )
        self.pdq_trigger.trigger(1 << ch)

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
        self.afe_relay.enable(0b11)

        ## Step 2 ##
        start_f_MHz = 0.01
        end_f_MHz = 0.05
        duration_us = 500
        # OUT0 and OUT1 have their frequency and phase aligned at 500us
        self.pdq_dds[0].set_waveform(
            b0=pdq_dds_amp_mu(1.0),
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=pdq_freq_mu(start_f_MHz),
            c2=pdq_freq_sweep(start_f_MHz, end_f_MHz, duration_us),
        )
        self.pdq_dds[1].set_waveform(
            b0=pdq_dds_amp_mu(1.0),
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=pdq_freq_mu(end_f_MHz),
            c2=0,
        )
        self.pdq_trigger.trigger(0b11)
        delay(500*us)

        ## Step 3 ##
        # OUT0 and OUT1 has 180 degree phase difference
        self.pdq_dds[0].set_waveform(
            b0=pdq_dds_amp_mu(1.0),
            b1=0,
            b2=0,
            b3=0,
            c0=pdq_phase_offset(180.0),
            c1=pdq_freq_mu(end_f_MHz),
            c2=0,
        )
        # Phase and Output Setting of OUT1 is retained 
        #   if the channel is not triggered or config is not cleared
        self.pdq_trigger.trigger(0b1)
        delay(500*us)

        ## Step 4 ##
        #     b(0) = 0, b(250) = 8.545, b(500) = 0
        self.pdq_dds[0].set_waveform(
            b0=0,
            b1=pdq_dds_damp_mu(0.06835937),
            b2=pdq_dds_ddamp_mu(-0.0001367187),
            b3=0,
            c0=0,
            c1=pdq_freq_mu(end_f_MHz),
            c2=0,
        )
        self.pdq_dds[1].set_waveform(
            b0=0,
            b1=pdq_dds_damp_mu(0.06835937),
            b2=pdq_dds_ddamp_mu(-0.0001367187),
            b3=0,
            c0=0,
            c1=0,
            c2=0,
        )
        self.pdq_trigger.trigger(0b11)
        delay(500*us)

        ## Step 5 ##
        self.pdq_volt[0].set_waveform(
            a0=pdq_volt_amp_mu(-5.0),
            a1=int32(pdq_volt_damp_mu(0.01)),
            a2=0,
            a3=0,
        )
        self.pdq_dds[0].set_waveform(
            b0=pdq_dds_amp_mu(1.0),
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=pdq_freq_mu(end_f_MHz),
            c2=0,
        )
        self.pdq_volt[1].set_waveform(
            a0=pdq_volt_amp_mu(-5.0),
            a1=int32(pdq_volt_damp_mu(0.01)),
            a2=0,
            a3=0,
        )
        self.pdq_dds[1].set_waveform(
            b0=0,
            b1=0,
            b2=0,
            b3=0,
            c0=0,
            c1=0,
            c2=0,
        )
        self.pdq_trigger.trigger(0b11)
        delay(1000*us)
        
        ## Step 6 ##
        self.pdq_volt[0].set_waveform(
            a0=pdq_volt_amp_mu(-2.5),
            a1=int32(pdq_volt_damp_mu(0.01)),
            a2=0,
            a3=0,
        )
        self.pdq_dds[0].set_waveform(
            b0=0,
            b1=pdq_dds_damp_mu(0.06835937),
            b2=pdq_dds_ddamp_mu(-0.0001367187),
            b3=0,
            c0=0,
            c1=pdq_freq_mu(start_f_MHz),
            c2=pdq_freq_sweep(start_f_MHz, end_f_MHz, duration_us),
        )
        self.pdq_trigger.trigger(0b1)
        self.pdq_channel_reset(1)
        delay(500*us)

        ## Step 7 ##
        self.pdq_volt[0].set_waveform(
            a0=pdq_volt_amp_mu(2.5),
            a1=int32(pdq_volt_damp_mu(-0.01)),
            a2=0,
            a3=0,
        )
        self.pdq_dds[0].set_waveform(
            b0=0,
            b1=pdq_dds_damp_mu(-0.06835937),
            b2=pdq_dds_ddamp_mu(0.0001367187),
            b3=0,
            c0=pdq_phase_offset(180.0),
            c1=pdq_freq_mu(end_f_MHz),
            c2=pdq_freq_sweep(end_f_MHz, start_f_MHz, duration_us),
        )
        self.pdq_trigger.trigger(0b1)
        delay(500*us)

        ## Step 8 ##
        self.afe_relay.enable(0)
        self.pdq_channel_reset(0)
        self.pdq_channel_reset(1)

    @kernel
    def led(self):
        for i in range(2):
            for j in range(3):
                self.leds[i].pulse(.1*s)
                delay(.1*s)

    @kernel
    def relay_init(self):
        self.afe_relay.init()
        self.afe_relay.enable(0x0000)

    @kernel
    def adc_init(self):
        delay_mu(int64(self.core.ref_multiplier))
        self.afe_adc.power_up()

        delay_mu(int64(self.core.ref_multiplier))
        assert self.afe_adc.read_id() >> 4 == 0x038d

        delay_mu(int64(self.core.ref_multiplier))
        # The actual output voltage is limited by the hardware, the calculated calibration gain and offset.
        # For example, if the system has a calibration gain of 1.06, then the max output voltage = 10 / 1.06 = 9.43V.
        # Setting a value larger than 9.43V will result in overflow.
        self.afe_adc.calibrate(self.pdq_volt, self.pdq_trigger, self.pdq_config)
