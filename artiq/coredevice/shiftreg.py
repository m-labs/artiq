from artiq.language.core import kernel, delay
from artiq.language.units import us


class ShiftReg:
    """Driver for shift registers/latch combos connected to TTLs"""
    kernel_invariants = {"dt", "n"}
    
    def __init__(self, dmgr, clk, ser, latch, n=32, dt=10*us, ser_in=None):
        self.core = dmgr.get("core")
        self.clk = dmgr.get(clk)
        self.ser = dmgr.get(ser)
        self.latch = dmgr.get(latch)
        self.n = n
        self.dt = dt
        if ser_in is not None:
            self.ser_in = dmgr.get(ser_in)

    @kernel
    def set(self, data):
        """Sets the values of the latch outputs. This does not
        advance the timeline and the waveform is generated before
        `now`."""
        delay(-2*(self.n + 1)*self.dt)
        for i in range(self.n):
            if (data >> (self.n-i-1)) & 1 == 0:
                self.ser.off()
            else:
                self.ser.on()
            self.clk.off()
            delay(self.dt)
            self.clk.on()
            delay(self.dt)
        self.clk.off()
        self.latch.on()
        delay(self.dt)
        self.latch.off()
        delay(self.dt)

    @kernel
    def get(self):
        delay(-2*(self.n + 1)*self.dt)
        data = 0
        for i in range(self.n):
            data <<= 1
            self.ser_in.sample_input()
            if self.ser_in.sample_get():
                data |= 1
            delay(self.dt)
            self.clk.on()
            delay(self.dt)
            self.clk.off()
        delay(self.dt)
        return data
