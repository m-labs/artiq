#!/usr/bin/env python3

# Copyright (c) 2015 Joe Britton (NIST)
# 11/16/2014 :: JWB port to python3, add logging
# 11/16/2014 :: JWB add wrapper to behave like artiq Controller
# 1/21/2015 :: JWB PEP8 fixes

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

    :param int comport: COM port number on Windows
    :param int debug: debug level
    """
    #NOTE: the in-line documentation is in Sphinx format
    #http://sphinx-doc.org/domains.html
    def __init__(self, comport=1, debug=1, simulate_hw=False):
        #some private members
        self.__comport = comport
        self.__debug = debug
        self.__className = "Novatech409B"
        self.simulate_hw = simulate_hw  # true if disconnected from hw
        self.serialRwDelay = 0.001  # is time between reads and writes

        #setup logging
        FORMAT = "%(asctime)-15s %(message)s"
        logging.basicConfig(format=FORMAT)
        self.logger = logging.getLogger("artiq.driver.novatech409B")
        self.logger.setLevel(logging.DEBUG)
        self.debugMessage("__init__", "", level=3)

        #establish serial connection --- platform dependent
        if self.simulate_hw is False:
            self.__platform = platform.system()
            if self.__platform == "Windows":
                #note that pySerial starts counting serial ports at 0
                serial_port_id = int(self.__comport)-1
            elif self.__platform is "Linux":
                #just use the device string as
                #passed (e.g. "/dev/ttyUSB0")
                serial_port_id = "/dev/ttyUSB0"
            else:
                self.debugMessage("__init__", "unknown platform", level=0)
                sys.exit()
            self.__ser = serial.Serial(
                serial_port_id,
                baudrate=19200,
                bytesize=8,
                parity="N",
                stopbits=1,
                xonxoff=0,
                timeout=0.05)
        self.setup()

    def __del__(self):
        if self.simulate_hw is False:
            self.__ser.close()
            time.sleep(1)

    def echo(self, s):
        ss = "novatech409B.echo() :: " + s
        self.debugMessage("echo", ss)
        return ss

    def debugMessage(self, funcName, msg, level=2):
        """generate debug message

        :param str funcName: the calling function"s name
        :param str msg: is a message
        :param int level: is the debug level
            ** 2 information helpful in typical use scenario
            ** 3 full-on debug info (annoying)
        :returns: None
        """
        if 1:  # (level <= self.__debug) :
            # try a trick to automatically infer caller name
            inferredFuncName = inspect.stack()[2][3]
            s = inferredFuncName + "() :: " + msg
            #here"s what a typical warnning message looks like:
            #WARNING:artiq.driver.novatech409B:
            #      setPhaseContinuous() :: M n
            self.logger.warning(s)

    def serSend(self, myStr, ignoreUnusualResponse=False):
        """send a string to the serial port

        Routine for sending serial commands to device. It sends strings
        and listens for a response terminated by a carriage return.

        example:
        serSend("F0 1.0") #sets the freq of channel 0 to 1.0 MHz

        :param str myStr: a character string to send to device
        :returns: None
        """
        self.debugMessage("serSend", myStr, level=3)
        s = myStr + "\r\n"
        expectedResponse = b"OK\r\n"
        result = b""
        if self.simulate_hw is False:
            try:
                self.__ser.flush()
                #after convert to python3 needed to cast between
                #Python3x string and the expected bytes type
                self.__ser.write(bytes(s, "UTF-8"))
                time.sleep(self.serialRwDelay)
                result = self.__ser.read(1028)
            except serial.SerialException as e:
                self.debugMessage("serSend", e, level=0)

            # check for error from device
            # expected response (no error) is myStr\r\nOK\r\n
            # after convert to python3 need to specify type of return
            # to be bytes
            if(ignoreUnusualResponse is False):
                if(result is not expectedResponse):
                    print("ERROR :: novatech409B.serSend() "
                        "response was {}".format(result))
                    return (result, expectedResponse)
                    sys.exit()
            return (result, expectedResponse)
        else:
            #in simulation mode
            return (expectedResponse, expectedResponse)

    def reset(self):
        """command hardware reset of 409B

        returns: None
        """
        self.debugMessage("reset", "", level=3)
        self.serSend("R", ignoreUnusualResponse=True)
        time.sleep(1)
        self.setup()

    def setup(self):
        """initial setup of 409B

        Setup the Novatech 409B with the following defaults.
        * command echo off ("E d")
        * external clock ("") 10 MHz sinusoid -1 to +7 dBm

        :returns: None
        """
        self.debugMessage("setup", "", level=2)
        #disable command echo
        self.serSend("E d", ignoreUnusualResponse=True)
        self.setPhaseContinuous(True)
        self.setSimultaneousUpdate(False)

    def saveStateToEEPROM(self):
        """save current state to EEPROM

        Saves current state into EEPROM and sets valid flag.
        State used as default upon next power up or reset. """
        self.debugMessage("saveStateToEEPROM", "", level=2)
        self.serSend("S")

    def setPhaseContinuous(self, isContinuous):
        """toggle phase continuous mode

        Sends the “M n” command. This turns off the automatic
        clearing of the phase register. In this mode, the phase
        register is left intact when a command is performed.
        Use this mode if you want frequency changes to remain
        phase synchronous, with no phase discontinuities.

        :param bool myBool: True or False
        """

        self.debugMessage("setPhaseContinuous", "", level=2)
        if isContinuous is True:
            self.serSend("M n")
        else:
            self.serSend("M a")

    def setSimultaneousUpdate(self, myBool):
        """
        :param bool myBool: True or False

        Sends the “I m” command. In this mode an update
        pulse will not be sent to the DDS chip until
        an “I p” command is sent. This is useful when it is
        important to change all the outputs to new values
        simultaneously."""
        self.debugMessage("setSimultaneousUpdate", "", level=2)
        if myBool is True:
            self.serSend("I m")
        else:
            self.serSend("I a")

    def setFreq(self, chNo, freq):
        """setFreq(chNo,freq):
        Set chNo to frequency freq MHz"""
        self.debugMessage("setFreq", str(chNo)+","+str(freq), level=3)
        if chNo < 0 or chNo > 3:
            print("ERROR :: novatech409B.setFreq() chNo Error")
            sys.exit()
        if freq < 0.0 or freq > 171.1276031:
            print("ERROR :: novatech409B.setFreq() freq Error")
            sys.exit()
        #do this immediately, disable SimultaneousUpdate mode
        self.setSimultaneousUpdate(False)
        cmd = "F{:d} {:f}".format(chNo, freq)
        self.serSend(cmd)

    def setPhase(self, chNo, phase):
        """set DDS phase

        :param int chNo: 0 to 3
        :param float phase: phase angle in cycles [0,1]
        :returns: None
        """
        self.debugMessage("setPhase",
                          str(chNo) + "," + str(phase),
                          level=3)
        if chNo < 0 or chNo > 3:
            print("ERROR :: novatech409B.setPhase() chNo Error")
        if phase < 0 or phase > 360:
            print("ERROR :: novatech409B.setPhase() phase Error")
        #do this immediately, disable SimultaneousUpdate mode
        self.setSimultaneousUpdate(False)
        #phase word is required by device
        #N is an integer from 0 to 16383. Phase is set to
        #N*360/16384 deg; in artiq represent phase in cycles [0,1]
        phaseWord = int(math.floor(phase*16384))
        cmd = "P{0:d} {0:d}".format(chNo, phaseWord)
        self.serSend(cmd)

    def setFreqAllPhaseContinuous(self, freq):
        """set frequency of all channels simultaneously

        Set frequency of all channels simultaneously.
        1) all DDSs are set to phase continuous mode
        2) all DDSs are simultaneously set to new frequency
        Together 1 and 2 ensure phase continuous frequency switching.

        :param float freq: frequency in MHz
        :returns: None
        """
        self.debugMessage("setFreqAllPhaseContinuous",
                          str(freq), level=2)
        self.setSimultaneousUpdate(True)
        self.setPhaseContinuous(True)
        for chNo in range(4):
            self.setFreq(chNo, freq)
        #send command necessary to update all channels at the same time
        self.serSend("I p")

    def setPhaseAll(self, phase):
        """set phase of all DDS channels simultaneously

        Set phase of all DDS channels at the same time. For example,::
            setPhaseAll([0,.25,0.5,0.75])

        :param float phase: vector of four  phases (in cycles [0,1])
        :returns: None
        """
        self.debugMessage("setPhaseAll", str(phase), level=2)
        self.setSimultaneousUpdate(True)
        #Note that this only works if the continuous
        #phase switching is turned off.
        self.setPhaseContinuous(False)
        for chNo in range(4):
            self.setPhase(chNo, phase[chNo])
        #send command necessary to update all channels at the same time
        self.serSend("I p")

    def freqSweepAllPhaseContinuous(self, f0, f1, t):
        """ sweep phase of all DDSs, phase continuous

        Sweep frequency in a phase continuous fashion.

        :param float f0: starting frequency (MHz)
        :param float f1: ending frequency (MHz)
        :param float t: sweep duration (seconds)
        :returns: None
        """
        s = str(f0) + "," + str(f1) + "," + str(t)
        self.debugMessage("freqSweepAllPhaseContinuous", s, level=2)
        if f0 == f1:
            return
        #get sign of sweep
        if f1 > f0:
            dfSign = 1
        else:
            dfSign = -1

        self.setPhaseContinuous(True)
        self.setSimultaneousUpdate(True)
        # calculate delay
        # note that a single call to self.setFreqAllPhaseContinuous()
        # takes time tForOneFreqSet; fix duration empirically
        tForOneFreqSet = 0.264
        dt = tForOneFreqSet
        nSteps = int(math.ceil(t/dt))
        df = abs(f0-f1)/nSteps
        for n in range(nSteps):
            fnow = f0+n*dfSign*df
            self.setFreqAllPhaseContinuous(fnow)
            if self.__debug > 0:
                print(".", end=" ")
        self.setFreqAllPhaseContinuous(f1)

    def outputScale(self, chNo, frac):
        """changes amplitude of a DDS

        :param int chNo: DDS channel 0, 1, 2 or 3
        :param float frac: 0 to 1 (full attenuation to no attenuation)
        :returns: None
        """
        self.setSimultaneousUpdate(False)
        dacChNo = int(math.floor(frac*1024))
        s = "V{:d} {:d}".format(chNo, dacChNo)
        self.debugMessage("scaleOutput", s, level=3)
        self.serSend(s)

    def outputScaleAll(self, frac):
        """changes amplitude of all DDSs

        :param float frac: 0 to 1 (full attenuation to no attenuation)
        """
        self.debugMessage("scaleOutput", str(frac), level=2)
        for chNo in range(4):
            self.outputScale(chNo, frac)
        #send command necessary to update all channels at the same time
        self.serSend("I p")

    def outputOnOff(self, chNo, myBool):
        """turns on or off the DDS

        :param int chNo:DDS channel 0, 1, 2 or 3
        :param bool myBool: True (if on) or False (if off)
        """
        self.debugMessage("outputOnOff", "", level=3)
        if myBool is True:
            #turn on output
            self.outputScale(chNo, 1.0)
        else:
            #turn off output
            self.outputScale(chNo, 0.0)

    def outputOnOffAll(self, myBool):
        """:param bool myBool: is True (on) or False (off)

        turns on or off the all the DDSs
        """
        self.debugMessage("outputOnOffAll", "", level=2)
        if myBool is True:
            #turn on output
            self.outputScaleAll(1.0)
        else:
            #turn off output
            self.outputScaleAll(0.0)
