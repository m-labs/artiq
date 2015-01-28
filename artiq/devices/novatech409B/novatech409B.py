#!/usr/bin/python3

# Copyright (c) 2015 Joe Britton

import serial
import sys
import time
import math
import platform
import logging
import inspect


class Novatech409B:
    """controller for Novatech 409B 4-channel DDS

    This class is an interface with the Novatech Model 409B 4-
    channel DDS box. The interface is a serial interface.
    """

    def __init__(self, comport=1, debug=1, simulate_hw=False):
        """
        :param int comport: COM port number on Windows
        :param int debug: debug level
        :param bool simulate_hw: if true operate without hardware connected
        """
        # some private members
        self.__comport = comport
        self.__debug = debug
        self.__className = self.__class__.__name__
        self.simulate_hw = simulate_hw  # true if disconnected from hw
        self.serial_rw_delay = 0.001  # is time between reads and writes
        self.__ser_is_configured = False

        # setup logging
        FORMAT = "%(asctime)-15s %(message)s"
        logging.basicConfig(format=FORMAT)
        self.logger = logging.getLogger("artiq.driver.novatech409B")
        self.logger.setLevel(logging.DEBUG)
        self.debug_message("__init__", "", level=3)

        # establish serial connection --- platform dependent
        if not self.simulate_hw:
            self.__platform = platform.system()
            if self.__platform == "Windows":
                # note that pySerial starts counting serial ports at 0
                serial_port_id = int(self.__comport)-1
            elif self.__platform == "Linux":
                # just use the device string as
                # passed (e.g. "/dev/ttyUSB0")
                serial_port_id = self.__comport
            else:
                self.debug_message("__init__", "unknown platform", level=0)
                sys.exit()
            self.__ser = serial.Serial(
                serial_port_id,
                baudrate=19200,
                bytesize=8,
                parity="N",
                stopbits=1,
                xonxoff=0,
                timeout=0.05)
            self.__ser_is_configured = True
        self.setup()

    def __del__(self):
        if ((not self.simulate_hw) and self.__ser_is_configured):
            self.__ser.close()

    def echo(self, s):
        ss = "novatech409B.echo() :: " + s
        self.debug_message("echo", ss)
        return ss

    def debug_message(self, func_name, msg, level=2):
        """generate debug message

        :param str func_name: the calling function"s name
        :param str msg: is a message
        :param int level: is the debug level
            ** 2 information helpful in typical use scenario
            ** 3 full-on debug info (annoying)
        :returns: None
        """
        if 1:  # (level <= self.__debug) :
            # try a trick to automatically infer caller name
            inferred_func_name = inspect.stack()[2][3]
            s = inferred_func_name + "() :: " + msg
            # here"s what a typical warnning message looks like:
            # WARNING:ARTIQ.driver.novatech409B:
            #      set_phase_continuous() :: M n
            self.logger.warning(s)

    def ser_send(self, myStr, ignore_unusual_response=False):
        """send a string to the serial port

        Routine for sending serial commands to device. It sends strings
        and listens for a response terminated by a carriage return.

        example:
        ser_send("F0 1.0") #sets the freq of channel 0 to 1.0 MHz

        :param str myStr: a character string to send to device
        :returns: None
        """
        self.debug_message("ser_send", myStr, level=3)
        s = myStr + "\r\n"
        expected_response = b"OK\r\n"
        result = b""
        if self.simulate_hw is False:
            try:
                self.__ser.flush()
                # after convert to python3 needed to cast between
                # Python3x string and the expected bytes type
                self.__ser.write(bytes(s, "UTF-8"))
                time.sleep(self.serial_rw_delay)
                result = self.__ser.read(1028)
            except serial.SerialException as e:
                self.debug_message("ser_send", e, level=0)

            # check for error from device
            # expected response (no error) is myStr\r\nOK\r\n
            # after convert to python3 need to specify type of return
            # to be bytes
            if not ignore_unusual_response:
                if result != expected_response:
                    print("ERROR :: novatech409B.ser_send() "
                        "response was {}".format(result))
                    return (result, expected_response)
                    sys.exit()
            return (result, expected_response)
        else:
            # in simulation mode
            return (expected_response, expected_response)

    def reset(self):
        """command hardware reset of 409B

        returns: None
        """
        self.debug_message("reset", "", level=3)
        self.ser_send("R", ignore_unusual_response=True)
        time.sleep(1)
        self.setup()

    def setup(self):
        """initial setup of 409B

        Setup the Novatech 409B with the following defaults.
        * command echo off ("E d")
        * external clock ("") 10 MHz sinusoid -1 to +7 dBm

        :returns: None
        """
        self.debug_message("setup", "", level=2)
        #disable command echo
        self.ser_send("E d", ignore_unusual_response=True)
        self.set_phase_continuous(True)
        self.set_simultaneous_update(False)

    def save_state_to_eeprom(self):
        """save current state to EEPROM

        Saves current state into EEPROM and sets valid flag.
        State used as default upon next power up or reset. """
        self.debug_message("save_state_to_eeprom", "", level=2)
        self.ser_send("S")

    def set_phase_continuous(self, is_continuous):
        """toggle phase continuous mode

        Sends the “M n” command. This turns off the automatic
        clearing of the phase register. In this mode, the phase
        register is left intact when a command is performed.
        Use this mode if you want frequency changes to remain
        phase synchronous, with no phase discontinuities.

        :param bool is_continuous: True or False
        """

        self.debug_message("set_phase_continuous", "", level=2)
        if is_continuous:
            self.ser_send("M n")
        else:
            self.ser_send("M a")

    def set_simultaneous_update(self, my_bool):
        """
        :param bool my_bool: True or False

        Sends the “I m” command. In this mode an update
        pulse will not be sent to the DDS chip until
        an “I p” command is sent. This is useful when it is
        important to change all the outputs to new values
        simultaneously."""
        self.debug_message("set_simultaneous_update", "", level=2)
        if my_bool:
            self.ser_send("I m")
        else:
            self.ser_send("I a")

    def set_freq(self, ch_no, freq):
        """set_freq(ch_no,freq):
        Set ch_no to frequency freq MHz"""
        self.debug_message("set_freq", str(ch_no)+","+str(freq), level=3)
        if ch_no < 0 or ch_no > 3:
            print("ERROR :: novatech409B.set_freq() ch_no Error")
            sys.exit()
        if freq < 0.0 or freq > 171.1276031:
            print("ERROR :: novatech409B.set_freq() freq Error")
            sys.exit()
        # do this immediately, disable SimultaneousUpdate mode
        self.set_simultaneous_update(False)
        cmd = "F{:d} {:f}".format(ch_no, freq)
        self.ser_send(cmd)

    def set_phase(self, channel_num, phase):
        """set DDS phase

        :param int channel_num: 0 to 3
        :param float phase: phase angle in cycles [0,1]
        :returns: None
        """
        self.debug_message("set_phase",
                          str(channel_num) + "," + str(phase),
                          level=3)
        if channel_num < 0 or channel_num > 3:
            print("ERROR :: novatech409B.set_phase() channel_num Error")
        if phase < 0 or phase > 360:
            print("ERROR :: novatech409B.set_phase() phase Error")
        # do this immediately, disable SimultaneousUpdate mode
        self.set_simultaneous_update(False)
        # phase word is required by device
        # N is an integer from 0 to 16383. Phase is set to
        # N*360/16384 deg; in ARTIQ represent phase in cycles [0,1]
        phase_word = int(math.floor(phase*16384))
        cmd = "P{0:d} {0:d}".format(channel_num, phase_word)
        self.ser_send(cmd)

    def set_freq_all_phase_continuous(self, freq):
        """set frequency of all channels simultaneously

        Set frequency of all channels simultaneously.
        1) all DDSs are set to phase continuous mode
        2) all DDSs are simultaneously set to new frequency
        Together 1 and 2 ensure phase continuous frequency switching.

        :param float freq: frequency in MHz
        :returns: None
        """
        self.debug_message("set_freq_all_phase_continuous",
                          str(freq), level=2)
        self.set_simultaneous_update(True)
        self.set_phase_continuous(True)
        for channel_num in range(4):
            self.set_freq(channel_num, freq)
        # send command necessary to update all channels at the same time
        self.ser_send("I p")

    def set_phase_all(self, phase):
        """set phase of all DDS channels simultaneously

        Set phase of all DDS channels at the same time. For example,::
            set_phase_all([0,.25,0.5,0.75])

        :param float phase: vector of four  phases (in cycles [0,1])
        :returns: None
        """
        self.debug_message("set_phase_all", str(phase), level=2)
        self.set_simultaneous_update(True)
        # Note that this only works if the continuous
        # phase switching is turned off.
        self.set_phase_continuous(False)
        for ch_no in range(4):
            self.set_phase(ch_no, phase[ch_no])
        # send command necessary to update all channels at the same time
        self.ser_send("I p")

    def freq_sweep_all_phase_continuous(self, f0, f1, t):
        """ sweep phase of all DDSs, phase continuous

        Sweep frequency in a phase continuous fashion.

        :param float f0: starting frequency (MHz)
        :param float f1: ending frequency (MHz)
        :param float t: sweep duration (seconds)
        :returns: None
        """
        s = str(f0) + "," + str(f1) + "," + str(t)
        self.debug_message("freq_sweep_all_phase_continuous", s, level=2)
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
            if self.__debug > 0:
                print(".", end=" ")
        self.set_freq_all_phase_continuous(f1)

    def output_scale(self, ch_no, frac):
        """changes amplitude of a DDS

        :param int ch_no: DDS channel 0, 1, 2 or 3
        :param float frac: 0 to 1 (full attenuation to no attenuation)
        :returns: None
        """
        self.set_simultaneous_update(False)
        dac_ch_no = int(math.floor(frac*1024))
        s = "V{:d} {:d}".format(ch_no, dac_ch_no)
        self.debug_message("scaleOutput", s, level=3)
        self.ser_send(s)

    def output_scale_all(self, frac):
        """changes amplitude of all DDSs

        :param float frac: 0 to 1 (full attenuation to no attenuation)
        """
        self.debug_message("scaleOutput", str(frac), level=2)
        for ch_no in range(4):
            self.output_scale(ch_no, frac)
        # send command necessary to update all channels at the same time
        self.ser_send("I p")

    def output_on_off(self, ch_no, my_bool):
        """turns on or off the DDS

        :param int ch_no:DDS channel 0, 1, 2 or 3
        :param bool my_bool: True (if on) or False (if off)
        """
        self.debug_message("output_on_off", "", level=3)
        if my_bool:
            #turn on output
            self.output_scale(ch_no, 1.0)
        else:
            #turn off output
            self.output_scale(ch_no, 0.0)

    def output_on_off_all(self, my_bool):
        """:param bool my_bool: is True (on) or False (off)

        turns on or off the all the DDSs
        """
        self.debug_message("output_on_off_all", "", level=2)
        if my_bool:
            #turn on output
            self.output_scale_all(1.0)
        else:
            #turn off output
            self.output_scale_all(0.0)


