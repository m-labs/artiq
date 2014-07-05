import os
import struct
import termios

class CoreCom:
	def __init__(self, dev="/dev/ttyUSB1", baud=115200):
		self._fd = os.open(dev, os.O_RDWR | os.O_NOCTTY)
		self.port = os.fdopen(self._fd, "r+b", buffering=0)
		iflag, oflag, cflag, lflag, ispeed, ospeed, cc = \
				termios.tcgetattr(self._fd)
		iflag = termios.IGNBRK | termios.IGNPAR
		oflag = 0
		cflag |= termios.CLOCAL | termios.CREAD | termios.CS8
		lflag = 0
		ispeed = ospeed = getattr(termios, "B"+str(baud))
		cc[termios.VMIN] = 1
		cc[termios.VTIME] = 0
		termios.tcsetattr(self._fd, termios.TCSANOW, [
			iflag, oflag, cflag, lflag, ispeed, ospeed, cc])
		termios.tcdrain(self._fd)
		termios.tcflush(self._fd, termios.TCOFLUSH)
		termios.tcflush(self._fd, termios.TCIFLUSH)

	def close(self):
		self.port.close()

	def __enter__(self):
		return self

	def __exit__(self, type, value, traceback):
		self.close()

	def run(self, kcode):
		self.port.write(struct.pack(">LL", 0x5a5a5a5a, len(kcode)))
		self.port.write(kcode)
