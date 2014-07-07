import os, termios, struct
from enum import Enum

class _MsgType(Enum):
	KERNEL_FINISHED		= 0x01
	RPC_REQUEST			= 0x02

def _write_exactly(f, data):
	remaining = len(data)
	pos = 0
	while remaining:
		written = f.write(data[pos:])
		remaining -= written
		pos += written

def _read_exactly(f, n):
	r = bytes()
	while(len(r) < n):
		r += f.read(n - len(r))
	return r

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
		_write_exactly(self.port, struct.pack(">ll", 0x5a5a5a5a, len(kcode)))
		_write_exactly(self.port, kcode)
		# FIXME: when loading immediately after a board reset, we erroneously get some zeros back.
		# Ignore them with a warning for now.
		spurious_zero_count = 0
		while True:
			(reply, ) = struct.unpack("b", _read_exactly(self.port, 1))
			if reply == 0:
				spurious_zero_count += 1
			elif reply == 0x4f:
				break
			else:
				raise IOError("Incorrect reply from device: "+hex(reply))
		if spurious_zero_count:
			print("Warning: received {} spurious zeros".format(spurious_zero_count))

	def _wait_sync(self):
		recognized = 0
		while recognized < 4:
			(c, ) = struct.unpack("b", _read_exactly(self.port, 1))
			if c == 0x5a:
				recognized += 1
			else:
				recognized = 0

	def serve(self, rpc_map):
		while True:
			self._wait_sync()
			msg = _MsgType(*struct.unpack("b", _read_exactly(self.port, 1)))
			if msg == _MsgType.KERNEL_FINISHED:
				return
			elif msg == _MsgType.RPC_REQUEST:
				rpc_num, n_args = struct.unpack(">hb", _read_exactly(self.port, 3))
				args = []
				for i in range(n_args):
					args.append(*struct.unpack(">l", _read_exactly(self.port, 4)))
				r = rpc_map[rpc_num](*args)
				if r is None:
					r = 0
				_write_exactly(self.port, struct.pack(">l", r))
