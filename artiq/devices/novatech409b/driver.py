# Written by Joe Britton, 2015

import math
import logging
import asyncio

import asyncserial


logger = logging.getLogger(__name__)


class UnexpectedResponse(Exception):
    pass


class Novatech409B:
    """Driver for Novatech 409B 4-channel DDS.

    All output channels are in range [0, 1, 2, 3].
    All frequencies are in Hz.
    All phases are in turns.
    All amplitudes are in volts.
    """

    error_codes = {
        "?0": "Unrecognized Command",
        "?1": "Bad Frequency",
        "?2": "Bad AM Command",
        "?3": "Input line too long",
        "?4": "Bad Phase",
        "?5": "Bad Time",
        "?6": "Bad Mode",
        "?7": "Bad Amp",
        "?8": "Bad Constant",
        "?f": "Bad Byte"
    }

    def __init__(self, serial_dev):
        if serial_dev is None:
            self.simulation = True
        else:
            self.simulation = False
            self.port = asyncserial.AsyncSerial(
                serial_dev,
                baudrate=19200,
                bytesize=8,
                parity="N",
                stopbits=1,
                xonxoff=0)

    def close(self):
        """Close the serial port."""
        if not self.simulation:
            self.port.close()

    async def _ser_readline(self):
        c = await self.port.read(1)
        r = c
        while c != b"\n":
            c = await self.port.read(1)
            r += c
        return r

    async def _ser_send(self, cmd, get_response=True):
        """Send a string to the serial port."""

        # Low-level routine for sending serial commands to device. It sends
        # strings and listens for a response terminated by a carriage return.
        # example:
        # ser_send("F0 1.0") # sets the freq of channel 0 to 1.0 MHz

        if self.simulation:
            logger.info("simulation _ser_send(\"%s\")", cmd)
        else:
            logger.debug("_ser_send(\"%s\")", cmd)
            self.port.ser.reset_input_buffer()
            await self.port.write((cmd + "\r\n").encode())
            if get_response:
                result = (await self._ser_readline()).rstrip().decode()
                logger.debug("got response from device: %s", result)
                if result != "OK":
                    errstr = self.error_codes.get(result, "Unrecognized reply")
                    s = "Erroneous reply from device: {ec}, {ecs}".format(
                        ec=result, ecs=errstr)
                    raise ValueError(s)
            else:
                pass

    async def reset(self):
        """Hardware reset of 409B."""
        await self._ser_send("R", get_response=False)
        await asyncio.sleep(1)
        await self.setup()

    async def setup(self):
        """Initial setup of 409B."""

        # Setup the Novatech 409B with the following defaults:
        # * command echo off ("E d")
        # * external clock ("") 10 MHz sinusoid -1 to +7 dBm

        await self._ser_send("E d", get_response=False)
        await self.set_phase_continuous(True)
        await self.set_simultaneous_update(False)

    async def save_state_to_eeprom(self):
        """Save current state to EEPROM."""
        await self._ser_send("S")

    async def set_phase_continuous(self, is_continuous):
        """Toggle phase continuous mode.

        Sends the "M n" command. This turns off the automatic
        clearing of the phase register. In this mode, the phase
        register is left intact when a command is performed.
        Use this mode if you want frequency changes to remain
        phase synchronous, with no phase discontinuities.

        :param is_continuous: True or False
        """
        if is_continuous:
            await self._ser_send("M n")
        else:
            await self._ser_send("M a")

    async def set_simultaneous_update(self, simultaneous):
        """Set simultaneous update mode.

        Sends the "I m" command. In this mode an update
        pulse will not be sent to the DDS chip until
        an "I p" command is sent. This is useful when it is
        important to change all the outputs to new values
        simultaneously.
        """
        if simultaneous:
            await self._ser_send("I m")
        else:
            await self._ser_send("I a")

    async def do_simultaneous_update(self):
        """Apply update in simultaneous update mode."""
        await self._ser_send("I p")

    async def set_freq(self, ch_no, freq):
        """Set frequency of one channel."""
        # Novatech expects MHz
        await self._ser_send("F{:d} {:f}".format(ch_no, freq/1e6))

    async def set_phase(self, ch_no, phase):
        """Set phase of one channel."""
        # phase word is required by device
        # N is an integer from 0 to 16383. Phase is set to
        # N*360/16384 deg; in ARTIQ represent phase in cycles [0, 1]
        phase_word = round(phase*16383)
        cmd = "P{:d} {:d}".format(ch_no, phase_word)
        await self._ser_send(cmd)

    async def set_gain(self, ch_no, volts):
        """Set amplitude of one channel."""

        # due to error in Novatech it doesn't generate an error for
        # dac_value>1024, so need to trap.
        dac_value = int(math.floor(volts/0.51*1024))
        if dac_value < 0 or dac_value > 1023:
            s = "Amplitude out of range {v}".format(v=volts)
            raise ValueError(s)

        s = "V{:d} {:d}".format(ch_no, dac_value)
        await self._ser_send(s)

    async def get_status(self):
        if self.simulation:
            return ["00989680 2000 01F5 0000 00000000 00000000 000301",
                    "00989680 2000 01F5 0000 00000000 00000000 000301",
                    "00989680 2000 01F5 0000 00000000 00000000 000301",
                    "00989680 2000 01F5 0000 00000000 00000000 000301",
                    "80 BC0000 0000 0102 21"]
        else:
            self.port.ser.reset_input_buffer()
            result = []
            await self.port.write(("QUE" + "\r\n").encode())
            for i in range(5):
                m = (await self._ser_readline()).rstrip().decode()
                result.append(m)
            logger.debug("got device status: %s", result)
            return result

    async def ping(self):
        try:
            stat = await self.get_status()
        except asyncio.CancelledError:
            raise
        except:
            return False
        # check that version number matches is "21"
        if stat[4][20:] == "21":
            logger.debug("ping successful")
            return True
        else:
            return False
