#!/usr/bin/python3

# Written by Joe Britton, 2015

import time
import math
import logging

import serial


logger = logging.getLogger(__name__)


class UnexpectedResponse(Exception):
    pass


class Novatech409B:
    """Driver for Novatech 409B 4-channel DDS"""

    # maximum frequency of Novatech 409B when using PLL and external reference
    max_freq_with_pll = 171.1276031

    def __init__(self, serial_dev):
        if serial_dev is None:
            self.simulation = True
        else:
            self.simulation = False
            self.port = serial.serial_for_url(
                serial_dev,
                baudrate=19200,
                bytesize=8,
                parity="N",
                stopbits=1,
                xonxoff=0,
                timeout=0.2)
        self.setup()

    def close(self):
        """Close the serial port"""
        if not self.simulation:
            self.port.close()

    def _ser_send(self, cmd, get_response=True):
        """send a string to the serial port

        Routine for sending serial commands to device. It sends strings
        and listens for a response terminated by a carriage return.

        example:
        ser_send("F0 1.0") # sets the freq of channel 0 to 1.0 MHz

        :param cmd: a character string to send to device
        :returns: None
        """
        if self.simulation:
            print(cmd)
        else:
            self.port.flush()
            self.port.write((cmd + "\r\n").encode())
            if get_response:
                result = self.port.readline().rstrip().decode()
                if result != "OK":
                    raise UnexpectedResponse(result)

    def reset(self):
        """command hardware reset of 409B

        returns: None
        """
        self._ser_send("R", get_response=False)
        time.sleep(1)
        self.setup()

    def setup(self):
        """initial setup of 409B

        Setup the Novatech 409B with the following defaults.
        * command echo off ("E d")
        * external clock ("") 10 MHz sinusoid -1 to +7 dBm

        :returns: None
        """
        # disable command echo
        self._ser_send("E d", get_response=False)
        self.set_phase_continuous(True)
        self.set_simultaneous_update(False)

    def save_state_to_eeprom(self):
        """save current state to EEPROM

        Saves current state into EEPROM and sets valid flag.
        State used as default upon next power up or reset. """
        self._ser_send("S")

    def set_phase_continuous(self, is_continuous):
        """toggle phase continuous mode

        Sends the "M n" command. This turns off the automatic
        clearing of the phase register. In this mode, the phase
        register is left intact when a command is performed.
        Use this mode if you want frequency changes to remain
        phase synchronous, with no phase discontinuities.

        :param is_continuous: True or False
        """
        if is_continuous:
            self._ser_send("M n")
        else:
            self._ser_send("M a")

    def set_simultaneous_update(self, simultaneous):
        """Sends the "I m" command. In this mode an update
        pulse will not be sent to the DDS chip until
        an "I p" command is sent. This is useful when it is
        important to change all the outputs to new values
        simultaneously.
        """
        if simultaneous:
            self._ser_send("I m")
        else:
            self._ser_send("I a")

    def set_freq(self, ch_no, freq):
        """set_freq(ch_no,freq):
        Set ch_no to frequency freq MHz"""
        if ch_no < 0 or ch_no > 3:
            raise ValueError("Incorrect channel number {}".format(ch_no))
        if freq < 0.0 or freq > self.max_freq_with_pll:
            raise ValueError("Incorrect frequency {}".format(freq))
        # do this immediately, disable SimultaneousUpdate mode
        self.set_simultaneous_update(False)
        self._ser_send("F{:d} {:f}".format(ch_no, freq))

    def set_phase(self, ch_no, phase):
        """set DDS phase

        :param ch_no: 0 to 3
        :param phase: phase angle in cycles [0, 1]
        :returns: None
        """
        if ch_no < 0 or ch_no > 3:
            raise ValueError("Incorrect channel number {}".format(ch_no))
        if phase < 0 or phase > 1:
            raise ValueError("Incorrect phase {}".format(phase))
        # do this immediately, disable SimultaneousUpdate mode
        self.set_simultaneous_update(False)
        # phase word is required by device
        # N is an integer from 0 to 16383. Phase is set to
        # N*360/16384 deg; in ARTIQ represent phase in cycles [0, 1]
        phase_word = round(phase*16384)
        if phase_word >= 16384:
            phase_word -= 16384
        cmd = "P{:d} {:d}".format(ch_no, phase_word)
        self._ser_send(cmd)

    def set_freq_all_phase_continuous(self, freq):
        """set frequency of all channels simultaneously

        Set frequency of all channels simultaneously.
        1) all DDSs are set to phase continuous mode
        2) all DDSs are simultaneously set to new frequency
        Together 1 and 2 ensure phase continuous frequency switching.

        :param freq: frequency in MHz
        :returns: None
        """
        self.set_simultaneous_update(True)
        self.set_phase_continuous(True)
        for channel_num in range(4):
            self.set_freq(channel_num, freq)
        # send command necessary to update all channels at the same time
        self._ser_send("I p")

    def set_phase_all(self, phase):
        """set phase of all DDS channels simultaneously

        Set phase of all DDS channels at the same time. For example,::
            set_phase_all([0, .25, 0.5, 0.75])

        :param phase: vector of four phases (in cycles [0, 1])
        :returns: None
        """
        self.set_simultaneous_update(True)
        # Note that this only works if the continuous
        # phase switching is turned off.
        self.set_phase_continuous(False)
        for ch_no in range(4):
            self.set_phase(ch_no, phase[ch_no])
        # send command necessary to update all channels at the same time
        self._ser_send("I p")

    def freq_sweep_all_phase_continuous(self, f0, f1, t):
        """ sweep phase of all DDSs, phase continuous

        Sweep frequency in a phase continuous fashion.

        :param f0: starting frequency (MHz)
        :param f1: ending frequency (MHz)
        :param t: sweep duration (seconds)
        :returns: None
        """
        # TODO: consider using artiq.language.units
        if f0 == f1:
            return
        # get sign of sweep
        if f1 > f0:
            df_sign = 1
        else:
            df_sign = -1

        self.set_phase_continuous(True)
        self.set_simultaneous_update(True)
        # calculate delay
        # note that a single call to self.set_freq_all_phase_continuous()
        # takes time t_for_one_freq_set; fix duration empirically
        t_for_one_freq_set = 0.264
        dt = t_for_one_freq_set
        n_steps = int(math.ceil(t/dt))
        df = abs(f0-f1)/n_steps
        for n in range(n_steps):
            fnow = f0+n*df_sign*df
            self.set_freq_all_phase_continuous(fnow)
        self.set_freq_all_phase_continuous(f1)

    def output_scale(self, ch_no, frac):
        """changes amplitude of a DDS

        :param ch_no: DDS channel 0, 1, 2 or 3
        :param frac: 0 to 1 (full attenuation to no attenuation)
        :returns: None
        """
        self.set_simultaneous_update(False)
        dac_ch_no = int(math.floor(frac*1024))
        s = "V{:d} {:d}".format(ch_no, dac_ch_no)
        self._ser_send(s)

    def output_scale_all(self, frac):
        """changes amplitude of all DDSs

        :param frac: 0 to 1 (full attenuation to no attenuation)
        """
        for ch_no in range(4):
            self.output_scale(ch_no, frac)

    def output_on_off(self, ch_no, on):
        """turns on or off the DDS

        :param ch_no: DDS channel 0, 1, 2 or 3
        """
        if on:
            self.output_scale(ch_no, 1.0)
        else:
            self.output_scale(ch_no, 0.0)

    def output_on_off_all(self, on):
        """turns on or off the all the DDSs"""
        if on:
            self.output_scale_all(1.0)
        else:
            self.output_scale_all(0.0)
