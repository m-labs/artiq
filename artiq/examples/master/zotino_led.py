from artiq.experiment import *

class ZotinoTestLED(EnvExperiment):
    def build(self):
        print(self.__doc__)
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
        for i in range(n):
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
        rclk.off()
        delay(dt)
        rclk.on()
        delay(dt)
        rclk.off()


    @kernel
    def run(self):
        self.core.reset()
        delay(1*ms)
		self.put_data(latch_config, clk_config, ser_config, 0x0042, 32)   # 0000 0000 0100 0010
		self.put_data(rclk, srclk, ser_in, 0xAA, 8)
		
		
        # while True:
            # self.SN74LV595A_putData(self.lpc_eem0_0, self.lpc_eem0_4, self.lpc_eem0_1, 0xAA)
            # delay(500*ms)
            # self.SN74LV595A_putData(self.lpc_eem0_0, self.lpc_eem0_4, self.lpc_eem0_1, 0x55)
            # delay(500*ms)