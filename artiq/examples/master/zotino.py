from artiq.experiment import *

class ZotinoTestDAC(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("dac1")
        self.setattr_device("latch_config")
        self.setattr_device("clk_config")
        self.setattr_device("ser_config")
		
    @kernel
    def dir_config(self, rclk, srclk, ser, data): ## dir config
	## for io_config, ser.off() = output, ser.on() = input
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
        ## set dir on fmc: ....0010 0010 0010 0010
	## first falling !(sync) starts write mode
        ## !(sync) high after 24 clock edges
        ## !(sync) low again for next transfer
	### mode bit == 00 to choose whether to write to X1A or X1B? then write data to register?
        self.dir_config(self.latch_config, self.clk_config, self.ser_config, 0x00008888) 
        self.dac1.setup_bus(write_div=30, read_div=40)  #50MHz for write frequency, 20MHz for read frequency
        self.dac1.write_offsets()
        delay(400*us)
        self.dac1.set([0x00ff for i in range(32)])
