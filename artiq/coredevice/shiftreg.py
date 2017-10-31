from artiq.language.core import (kernel, delay)
from artiq.language.units import us

class ShiftReg:
    kernel_invariants = {"dt"}
    
    def __init__(self, dmgr, clk, ser, latch, n=32, dt=10*us):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(latch)
        self.srclk = dmgr.get(clk)
        self.ser = dmgr.get(ser)
        self.n = n
        self.dt = dt

    @kernel
    def shiftreg_config(self, data):
        self.srclk.off()
        self.bus.off()
        delay(self.dt)
        for i in range(self.n):
            if data >>(self.n-i-1) & 1 == 0:
                self.ser.off()
            else:
                self.ser.on()
            self.srclk.off()
            delay(self.dt)
            self.srclk.on()
            delay(self.dt)
        self.srclk.off()
        self.bus.on()
        delay(self.dt)
        self.bus.off()
        delay(self.dt)
