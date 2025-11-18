from artiq.experiment import *


class PhaseTrack(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("suservo0")
        for i in range(4):
            self.setattr_device("suservo0_ch{}".format(i))

    @kernel
    def run(self):
        self.core.break_realtime()
        self.core.reset()

        self.suservo0.init()
        delay(1*us)

        # enable RF, IIR updates, phase tracking, and profile 0
        self.suservo0_ch0.set(en_out=1, en_iir=1, en_pt=1, profile=0)
        self.suservo0_ch1.set(en_out=1, en_iir=1, en_pt=1, profile=0)
        self.suservo0_ch2.set(en_out=1, en_iir=1, en_pt=1, profile=0)

        # preconfigure CH1 reference time
        self.suservo0_ch1.set_reference_time(0, 11)

        # enable global servo iterations
        self.suservo0.set_config(enable=1)
        origin = now_mu()   # Internal time stamp accumulator = 0
                            # It increments on its own afterwards

        # Set reference time of CH2 according to the time cursor
        # It is the time from the origin (See the origin variable.)
        delay(29*ns)
        self.suservo0_ch2.copy_reference_time(0)

        delay(100*ns)
        references = [
            self.suservo0_ch0.get_reference_time(0),
            self.suservo0_ch1.get_reference_time(0),
            self.suservo0_ch2.get_reference_time(0),
        ]

        print(references)
