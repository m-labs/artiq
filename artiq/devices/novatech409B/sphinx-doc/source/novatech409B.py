# -*- coding: utf-8 -*-
"""
Created on 9/2/2014

@author: Joe Britton

novatech409B.py is a script designed to interface with the Novatech
Model 409B 4-channel DDS box. 
"""


import os.path
import serial, sys, time, math, timeit

import struct
import numpy as np
#import matplotlib.pyplot as plt
from datetime import datetime as dt

class Novatech409B:
	'''
	py:class:: Novatech(self,[comport=4,debug=1])
	
	This class is an interface with the Novatech Model 409B 
	4-channel DDS box. The interface is a serial interface. 
	
	:param int comport: The COM port for the serial interface
	:param int debug: debug level'''

	def __init__(self,comport=4,debug=1):

		#some private members
		self.__comport = comport
		self.__debug = debug
		self.__className='Novatech409B'
		self.serialRwDelay = 0.001 #is time between reads and writes
		self.__simultaneousUpdateModeActive = False
		self.__phaseContinuousModeActive = False
		
		#establish serial connection 
		#note that pySerial starts counting serial ports at 0
		self.__ser = serial.Serial( 
			self.__comport-1, 
			baudrate=19200, 
			bytesize = 8,
			parity = 'N',
			stopbits = 1,
			xonxoff=0,
			timeout=0.05 )
		self.debugMessage('__init__','',level=3)
			
		self.setup()
		
	def __del__(self):
		self.__ser.close()
		time.sleep(1)
	def debugMessage(self, funcName, msg, level=2):
		'''debugMesssage(funcName, msg, level=2)
		funcName is the calling function's name (string)
		msg is a string message
		level is the debug level
			2 information helpful in typical use scenario
			3 full-on debug info (annoying) '''
		if level <= self.__debug : 
			print(self.__className + '.' + funcName + '() :: ' + msg)
			
	def serSend(self,myStr):
		'''sendSer(myStr)
		Routine for sending serial commands to device. It sends strings
		and listens for a response terminated by a carriage return.
		Example:
		serSend('F0 1.0') sets the freq of channel 0 to 1.0 MHz
		'''
		self.debugMessage('sendSer',myStr,level=3)
		s = myStr + '\r\n'
		
		try:
			self.__ser.flush()
			self.__ser.write(s)
			time.sleep(self.serialRwDelay)
			result = self.__ser.read(1028)
		except serial.SerialException as e:
			print(e)

		#check for error from device 
		#expected response (no error) is myStr\r\nOK\r\n
		expectedResponse = 'OK\r\n'
		if(result != expectedResponse):
			print('ERROR :: novatech409B.serSend() response was %s' % result)
			return (result, expectedResponse)
			#sys.exit()
		return (result, expectedResponse)
	def reset(self):
		'''reset()
		Reset 409B.'''
		self.debugMessage('reset','',level=3)
		self.serSend('R')
		
	def setup(self):
		'''setup()
		Setup the Novatech 409B with the following defaults.
		* command echo off ('E d')
		* optional: external clock ('') 10 MHz sinusoid -1 to +7 dBm
		'''
		self.debugMessage('setup','',level=2)
		#disable command echo
		self.serSend('E d') 
		self.setPhaseContinuous(True) 
		self.setSimultaneousUpdate(True) 
		
	def saveStateToEEPROM(self):
		'''saveStateToEEPROM()
		Saves current state into EEPROM and sets valid flag. 
		State used as default upon next power up or reset. '''
		self.debugMessage('saveStateToEEPROM','',level=2)
		self.serSend('S')
	def setPhaseContinuous(self,myBool):
		'''setPhaseContinuous(myBool)
		myBool = True or False
		Sends the “M n” command. This turns off the automatic 
		clearing of the phase register. In this mode, the phase 
		register is left intact when a command is performed. 
		Use this mode if you want frequency changes to remain 
		phase synchronous, with no phase discontinuities.'''
		self.debugMessage('setPhaseContinuous','',level=2)
		if myBool == True:
			self.serSend('M n')
			self.__phaseContinuousModeActive = True
		else:
			self.serSend('M a')
			self.__phaseContinuousModeActive = False
			
	def setSimultaneousUpdate(self,myBool):
		'''setSimultaneousUpdate()
		Sends the “I m” command. In this mode an update 
		pulse will not be sent to the DDS chip until 
		an “I p” command is sent. This is useful when it is 
		important to change all the outputs to new values 
		simultaneously.'''
		self.debugMessage('setSimultaneousUpdate','',level=2)
		if myBool == True:
			self.serSend('I m')
			self.__simultaneousUpdateModeActive = True
		else:
			self.serSend('I a')
			self.__simultaneousUpdateModeActive = False
			
	def setFreq(self,chNo,freq):
		'''setFreq(chNo,freq):
		Set chNo to frequency freq MHz'''
		self.debugMessage('setFreq',str(chNo)+','+str(freq),level=3)
		if chNo < 0 or chNo > 3:
			print('ERROR :: novatech409B.setFreq() chNo Error')
			sys.exit()
		if freq < 0.0 or freq > 171.1276031:
			print('ERROR :: novatech409B.setFreq() freq Error')
			sys.exit()
		cmd = 'F%d %f' %(chNo,freq*self.__extClockCompensationMultiplier)
		self.serSend(cmd)
	def setPhase(self,chNo,phase):
		'''setPhase(chNo,freq):
		Set chNo to phase phase (in degrees)'''
		self.debugMessage('setPhase',str(chNo) + ',' +str(phase),level=3)
		if chNo < 0 or chNo > 3:
			print('ERROR :: novatech409B.setPhase() chNo Error')
		if phase < 0 or phase > 360:
			print('ERROR :: novatech409B.setPhase() phase Error')
		#phase word is required by device
		#N is an integer from 0 to 16383. Phase is set to 
		#N*360/16384. 
		phaseWord = int(math.floor(phase*16384/360.0))
		cmd = 'P%d %d' %(chNo,phaseWord)
		self.serSend(cmd)
	def setFreqAllPhaseContinuous(self,freq):
		'''setFreqAllPhaseContinuous(freq):
		Set frequency of all channels to freq MHz. 
		1) all DDSs are set to phase continuous mode
		2) all DDSs are simultaneously set to new frequency
		Together 1 and 2 ensure phase continuous frequency switching.
		'''
		self.debugMessage('setFreqAllPhaseContinuous',str(freq),level=2)
		if self.__simultaneousUpdateModeActive == False:
			self.setSimultaneousUpdate(True)
		if self.__phaseContinuousModeActive == False:
			self.setPhaseContinuous(True)
		for chNo in range(4):
			self.setFreq(chNo,freq)
		#send command necessary to update all channels at the same time
		self.serSend('I p') 
	def setPhaseAll(self,phase):
		'''setPhaseAllSimultaneous(phase)
		phase is a vector of four  phases (in degrees)
			e.g. setPhaseAll([0,90,120,180])
		Set phase of all DDS channels at the same time. '''
		self.debugMessage('setPhaseAll',str(phase),level=2)
		if self.__simultaneousUpdateModeActive == False:
			self.setSimultaneousUpdate(True)
		#Note that this only works if the continuous phase switching is turned
		#off. 
		pcMode = self.__phaseContinuousModeActive
		if pcMode == True:
			self.setPhaseContinuous(False)
		for chNo in range(4):
			self.setPhase(chNo,phase[chNo])
		#send command necessary to update all channels at the same time
		self.serSend('I p') 
		#turn back on pcMode if it was previously on
		if pcMode == True:
			self.setPhaseContinuous(True)
			
	def freqSweepAllPhaseContinuous(self,f0,f1,t):
		'''freqSweepAllPhaseContinuous(f0,f1,df,t)
		Sweep frequency in a phase continuous fashion.
			f0 		starting frequency (MHz)
			f1 		ending frequency (MHz)
			t 		sweep duration (seconds)'''
		s = str(f0) + ',' + str(f1) + ',' + str(t) 
		self.debugMessage('freqSweepAllPhaseContinuous',s,level=2)
		if f0 == f1:
			return 
		#get sign of sweep
		if f1 > f0:
			dfSign = 1
		else:
			dfSign = -1

		#calculate delay 
		#note that a single call to self.setFreqAllPhaseContinuous()
		#takes time tForOneFreqSet; fix duration empirically
		tForOneFreqSet = 0.264
		dt = tForOneFreqSet
		nSteps = int( math.ceil(t/dt) ) 
		df = abs(f0-f1)/nSteps
		for n in range(nSteps):
			fnow = f0+n*dfSign*df
			self.setFreqAllPhaseContinuous(fnow)
			if self.__debug > 0:
				print('.', end=' ')
		self.setFreqAllPhaseContinuous(f1)

	def outputScale(self,chNo,frac):
		'''outputScale(chNo,frac) - changes amplitude of a DDS
		chNo is DDS channel 0, 1, 2 or 3
		frac is 0 to 1 (full attenuation to no attenuation)
		'''
		dacChNo = int(math.floor(frac*1024))
		s = 'V%d %d' %(chNo, dacChNo)
		self.debugMessage('scaleOutput',s,level=3)
		self.serSend(s)
	def outputScaleAll(self,frac):
		'''outputScaleAll(frac) - changes amplitude of all DDSs
		frac is 0 to 1 (full attenuation to no attenuation)
		'''
		self.debugMessage('scaleOutput',str(frac),level=2)
		for chNo in range(4):
			self.outputScale(chNo,frac)
		if self.__simultaneousUpdateModeActive == True:
			#send command necessary to update all channels at the same time
			self.serSend('I p') 
		
	def outputOnOff(self,chNo, myBool):
		'''outputOnOff(myBool) - turns on or off the DDS
		chNo is DDS channel 0, 1, 2 or 3
		myBool is True (if on) or False (if off)'''
		self.debugMessage('outputOnOff','',level=3)
		if myBool == True:
			#turn on output
			self.outputScale(chNo,1.0)
		else:
			#turn off output
			self.outputScale(chNo,0.0)
		
	def outputOnOffAll(self,myBool):
		'''outputOnOffAll(myBool) - turns on or off the all the DDSs
		myBool is True (on) or False (off)'''
		self.debugMessage('outputOnOffAll','',level=2)
		if myBool == True:
			#turn on output
			self.outputScaleAll(1.0)
		else:
			#turn off output
			self.outputScaleAll(0.0)

#JWB: to support sphinx-doc it's necessary to protect a main routine 
#http://sphinx-doc.org/ext/autodoc.html#module-sphinx.ext.autodoc	
if __name__ == '__main__':
	#Typical use is illustrated below.
	#create an instance of the class.
	if(False):
		try: 
			del(nova) #in case it already exists
		except NameError:
			pass
		nova = Novatech409B(comport=4,debug=1)
		nova.setFreqAllPhaseContinuous(1.0)
		nova.setPhaseAll([0.0,60.0,120.0,180.0])
		nova.freqSweepAllPhaseContinuous(1.0, 2.0, 10.0)
	
	#optionally do some code profiling
	if(False):				
		nova = Novatech409B(comport=4,debug=1)
		nova.setFreqAllPhaseContinuous(1.0)
		nova.setPhaseAll([0.0,60.0,120.0,180.0])
		def testFunc():
			nova.freqSweepAllPhaseContinuous(1.0, 2.0, 10.0)
	print(timeit.timeit( testFunc,number=1))
