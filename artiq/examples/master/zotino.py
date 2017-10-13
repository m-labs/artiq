from artiq.experiment import *

class ZotinoTestDAC(EnvExperiment):
    def build(self):
        print(self.__doc__)
        self.setattr_device("core")
        self.setattr_device("dac1")
		self.setattr_device("latch_config")
        self.setattr_device("clk_config")
        self.setattr_device("ser_config")
		
	@kernel
    def put_data(self, rclk, srclk, ser, data, n): ## dir config or led control
	## for io_config, ser.off() = output, ser.on() = input
        dt = 1*ms
        srclk.off()
        rclk.off()
        delay(dt)
        for i in range(n-1):  
            if data & 1 == 0:
                ser.off()
            else:
                ser.on()
            srclk.off()
            delay(dt)
            srclk.on()
            delay(dt)
            data = data >> 1
        srclk.off()
        rclk.on()
        delay(dt)
        rclk.off()
        delay(dt)

    @kernel
    def run(self):
        self.core.reset()
        delay(1*ms)
	put_data(latch_config, clk_config, ser_config, 0x0042, 32)  # set direction on fmc
	## first falling !(sync) start writing mode
	## !(sync) high after 24 clock edges
	## !(sync) low again for next transfer
	
	### mode bit == 00 to choose whether to write to X1A or X1B?, then write data to register?
        self.dac1.setup_bus(write_div=30, read_div=40)  #50MHz for write frequency, 20MHz for read frequency
        self.dac1.write_offsets()
	self.dac1.set([0x00ff for i in range(32)])
        # self.zotino_dac.set([i << 10 for i in range(40)])
        # while(True):
            # self.zotino_dac.set([0x7fff for i in range(40)])
            # delay(1*ms)
            # self.zotino_dac.set([0x0000 for i in range(40)])
            # delay(1*ms)
