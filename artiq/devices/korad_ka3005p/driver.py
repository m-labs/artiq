# Written by Joe Britton, 2016

import logging
import asyncio
import asyncserial

logger = logging.getLogger(__name__)


class UnexpectedResponse(Exception):
    pass


class KoradKA3005P:
    """The Korad KA3005P is a 1-channel programmable power supply
    (0-30V/0-5A) with both USB/serial and RS232 connectivity.

    All amplitudes are in volts.
    All currents are in amperes.
    """

    # Serial interface gleaned from the following.
    # https://github.com/starforgelabs/py-korad-serial
    # https://sigrok.org/wiki/Korad_KAxxxxP_series

    def __init__(self, serial_dev):
        if serial_dev is None:
            self.simulation = True
        else:
            self.simulation = False
            self.port = asyncserial.AsyncSerial(serial_dev, baudrate=9600)

    def close(self):
        """Close the serial port."""
        if not self.simulation:
            self.port.close()

    async def _ser_read(self, fixed_length=None):
        """ strings returned by firmware are zero-terminated or fixed length
        """
        r = ""
        if self.simulation:
            logger.info("simulation _ser_read()")
        else:
            c = (await self.port.read(1)).decode()
            r = c
            while len(c) > 0 and ord(c) != 0 and not len(r) == fixed_length:
                c = (await self.port.read(1)).decode().rstrip('\0')
                r += c
            logger.debug("_read %s: ", r)
        return r

    async def _ser_write(self, cmd):
        if self.simulation:
            logger.info("simulation _ser_write(\"%s\")", cmd)
        else:
            logger.debug("_ser_write(\"%s\")", cmd)
            await asyncio.sleep(0.1)
            await self.port.write(cmd.encode("ascii"))

    async def setup(self):
        """Configure in known state."""
        await self.set_output(False)
        await self.set_v(0)
        await self.set_ovp(False)
        await self.set_i(0)
        await self.set_ocp(False)

    async def get_id(self):
        """Request identification from device.
        """
        if self.simulation:
            return "KORADKA3005PV2.0"
        await self._ser_write("*IDN?")
        return await self._ser_read()

    async def set_output(self, b):
        """Enable/disable the power output.
        """
        if b:
            await self._ser_write("OUT1")
        else:
            await self._ser_write("OUT0")

    async def set_v(self, v):
        """Set the maximum output voltage."""
        await self._ser_write("VSET1:{0:05.2f}".format(v))

    async def get_v(self):
        """Request the voltage as set by the user."""
        await self._ser_write("VSET1?")
        return float(await self._ser_read(fixed_length=5))

    async def measure_v(self):
        """Request the actual voltage output."""
        await self._ser_write("VOUT1?")
        return float(await self._ser_read(fixed_length=5))

    async def set_ovp(self, b):
        """Enable/disable the "Over Voltage Protection", the PS will switch off the
        output when the voltage rises above the actual level."""
        if b:
            await self._ser_write("OVP1")
        else:
            await self._ser_write("OVP0")

    async def set_i(self, v):
        """Set the maximum output current."""
        await self._ser_write("ISET1:{0:05.3f}".format(v))

    async def get_i(self):
        """Request the current as set by the user. """
        # Expected behavior of ISET1? is to return 5 bytes.
        # However, if *IDN? has been previously called, ISET1? replies
        # with a sixth byte 'K' which should be discarded. For consistency,
        # always call *IDN? before calling ISET1?.
        self.get_id()
        await self._ser_write("ISET1?")
        r = (await self._ser_read(fixed_length=6)).rstrip('K')
        return float(r)

    async def measure_i(self):
        """Request the actual output current."""
        await self._ser_write("IOUT1?")
        r = await self._ser_read(fixed_length=5)
        if r[0] == "K":
            r = r[1:-1]
        return float(r)

    async def set_ocp(self, b):
        """Enable/disable the "Over Current Protection", the PS will switch off
        the output when the current rises above the actual level."""
        if b:
            await self._ser_write("OCP1")
        else:
            await self._ser_write("OCP0")

    async def ping(self):
        """Check if device is responding."""
        if self.simulation:
            return True
        try:
            id = await self.get_id()
        except asyncio.CancelledError:
            raise
        except:
            return False
        if id == "KORADKA3005PV2.0":
            logger.debug("ping successful")
            return True
        else:
            return False
