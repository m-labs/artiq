import sys

from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core


@compile
class Mandelbrot(EnvExperiment):
    """Mandelbrot set demo"""

    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")

    @rpc
    def col(self, i: int32):
        sys.stdout.write(" .,-:;i+hHM$*#@ "[i])

    @rpc
    def row(self):
        print("")

    # based on: http://warp.povusers.org/MandScripts/python.html
    @kernel
    def run(self):
        minX = -2.0
        maxX = 1.0
        width = 78
        height = 36
        aspectRatio = 2.0

        yScale = (maxX-minX)*(float(height)/float(width))*aspectRatio

        for y in range(height):
            for x in range(width):
                c_r = minX+float(x)*(maxX-minX)/float(width)
                c_i = float(y)*yScale/float(height)-yScale/2.0
                z_r = c_r
                z_i = c_i
                i = 0
                for i in range(16):
                    if z_r*z_r + z_i*z_i > 4.0:
                        break
                    new_z_r = (z_r*z_r)-(z_i*z_i) + c_r
                    z_i = 2.0*z_r*z_i + c_i
                    z_r = new_z_r
                self.col(i)
            self.row()
