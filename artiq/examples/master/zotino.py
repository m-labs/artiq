from artiq.experiment import *

class ZotinoTestDAC(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("dac_zotino")
        self.setattr_device("latch_config")
        self.setattr_device("clk_config")
        self.setattr_device("ser_config")
		
    @kernel
    def dir_config(self, rclk, srclk, ser, data): 
        dt = 10*us
        srclk.off()
        rclk.off()
        delay(dt)
        x = 0x80000000
        for i in range(32):  
            if data & x == 0:
                ser.off()
            else:
                ser.on()
            srclk.off()
            delay(dt)
            srclk.on()
            delay(dt)
            x = x >> 1
        srclk.off()
        rclk.on()
        delay(dt)
        rclk.off()
        delay(dt)

    @kernel
    def run(self):
        self.core.reset()
        self.dir_config(self.latch_config, self.clk_config, self.ser_config, 0x00008888) ## set lvds direction on fmc
        self.dac_zotino.setup_bus(write_div=30, read_div=40)  
        self.dac_zotino.write_offsets()
        delay(400*us)
        self.dac_zotino.set([0x00ff for i in range(32)])
