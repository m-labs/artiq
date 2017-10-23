from artiq.experiment import *

class ZotinoTestLED(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("latch_config")
        self.setattr_device("clk_config")
        self.setattr_device("ser_config")
        self.setattr_device("rclk")
        self.setattr_device("srclk")
        self.setattr_device("ser_in")

    @kernel
    def put_data(self, rclk, srclk, ser, data, n): ## dir config or led control
	## for io_config, ser.off() = output, ser.on() = input
        dt = 1*ms
        srclk.off()
        rclk.off()
        delay(dt)
        x = 0x8000
        if n == 32: 
            x = 0x8000
        else:
            x = 0x80   
        for i in range(n):
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
        delay(1*ms)
        self.put_data(self.latch_config, self.clk_config, self.ser_config, 0x0042, 32)   # 0000 0000 0100 0010
        self.put_data(self.rclk, self.srclk, self.ser_in, 0xAA, 8)
		
