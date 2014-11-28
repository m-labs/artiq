#!/usr/bin/env python3
import argparse
import os
import logging
import atexit
import ctypes
import ctypes.util
import struct

from artiq.management.pc_rpc import simple_server_loop


logger = logging.getLogger(__name__)

if "." not in os.environ["PATH"].split(";"):
    os.environ["PATH"] += ";."
dir = os.path.split(__file__)[0]
if dir not in os.environ["PATH"].split(";"):
    os.environ["PATH"] += ";%s" % dir

for n in "hidapi-libusb hidapi-hidraw hidapi".split():
    path = ctypes.util.find_library(n)
    if path:
        break
if not path:
    raise ImportError("no hidapi library found")
hidapi = ctypes.CDLL(path)


class HidDeviceInfo(ctypes.Structure):
    pass


HidDeviceInfo._fields_ = [
    ("path", ctypes.c_char_p),
    ("vendor_id", ctypes.c_ushort),
    ("product_id", ctypes.c_ushort),
    ("serial", ctypes.c_wchar_p),
    ("release", ctypes.c_ushort),
    ("manufacturer", ctypes.c_wchar_p),
    ("product", ctypes.c_wchar_p),
    ("usage_page", ctypes.c_ushort),
    ("usage", ctypes.c_ushort),
    ("interface", ctypes.c_int),
    ("next", ctypes.POINTER(HidDeviceInfo)),
]


hidapi.hid_enumerate.argtypes = [ctypes.c_ushort, ctypes.c_ushort]
hidapi.hid_enumerate.restype = ctypes.POINTER(HidDeviceInfo)
hidapi.hid_free_enumeration.argtypes = [ctypes.POINTER(HidDeviceInfo)]
hidapi.hid_open.argtypes = [ctypes.c_ushort, ctypes.c_ushort,
                            ctypes.c_wchar_p]
hidapi.hid_open.restype = ctypes.c_void_p
hidapi.hid_read_timeout.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                    ctypes.c_size_t, ctypes.c_int]
hidapi.hid_read.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
hidapi.hid_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
hidapi.hid_send_feature_report.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                           ctypes.c_size_t]
hidapi.hid_get_feature_report.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                          ctypes.c_size_t]
hidapi.hid_error.argtypes = [ctypes.c_void_p]
hidapi.hid_error.restype = ctypes.c_wchar_p

atexit.register(hidapi.hid_exit)


class HidError(Exception):
    pass


class Ldasim:
    """Lab Brick Digital Attenuator simulation controller.
    """

    def __init__(self):
        self._attenuation = None

    def get_attenuation(self):
        """Reads last attenuation value set to the simulated device.

        :return: Returns the attenuation value in dB, or None if it was
                 never set.
        :rtype: float

        """
        return self._attenuation

    def set_attenuation(self, attenuation):
        """Stores the new attenuation value and prints it to console.

        :param attenuation: The attenuation value in dB.
        :type attenuation: int, float or Fraction

        """
        attenuation = round(attenuation*4)/4.
        print("[LDA-sim] setting attenuation to {}".format(attenuation))
        self._attenuation = attenuation


class Lda:
    """Lab Brick Digital Attenuator controller.

    This controller depends on the hidapi library.

    On Linux you should install hidapi-libusb shared library in a directory
    listed in your LD_LIBRARY_PATH or in the conventional places (/usr/lib,
    /lib, /usr/local/lib). This can be done either from hidapi sources
    or by installing the libhidapi-libusb0 binary package on Debian-like OS.

    On Windows you should put hidapi.dll shared library in the same directory
    as the controller.

    """
    _vendor_id = 0x041f
    _product_ids = {
        "LDA-102": 0x1207,
        "LDA-602": 0x1208,
    }

    def __init__(self, serial=None, product="LDA-102"):
        """
        :param serial: The serial number.
        :param product: The product identifier string: LDA-102, LDA-602 or sim.

        """

        self.product = product
        if serial is None:
            serial = next(self.enumerate(product))
        self._dev = hidapi.hid_open(self._vendor_id,
                                    self._product_ids[product], serial)
        assert self._dev

    @classmethod
    def enumerate(cls, product):
        devs = hidapi.hid_enumerate(cls._vendor_id,
                                    cls._product_ids[product])
        dev = devs
        while dev:
            yield dev[0].serial
            dev = dev[0].next
        yield None
        hidapi.hid_free_enumeration(devs)

    def _check_error(self, ret):
        if ret < 0:
            err = hidapi.hid_error(self._dev)
            raise HidError("%s: %s" % (ret, err))
        return ret

    def write(self, command, length, data=bytes()):
        """Writes a command to the Lab Brick device.

        :param command: command ID.
        :param length: number of meaningful bytes in the data array.
        :param data: a byte array containing the payload of the command.

        """
        # 0 is report id/padding
        buf = struct.pack("BBB6s", 0, command, length, data)
        res = self._check_error(hidapi.hid_write(self._dev, buf, len(buf)))
        assert res == len(buf), res

    def set(self, command, data):
        """Sends a SET command to the Lab Brick device.

        :param command: command ID, must have most significant bit set.
        :param data: payload of the command.

        """
        assert command & 0x80
        assert data
        self.write(command, len(data), data)

    def get(self, command, length, timeout=1000):
        # FIXME: this can collide with the status reports that the
        # device sends out by itself
        """Sends a GET command to read back some value of the Lab Brick device.

        :param int command: Command ID, most significant bit must be cleared.
        :param int length: Length of the command, "count" in the datasheet.
        :param int timeout: Timeout of the HID read in ms.
        :return: Returns the value read from the device.
        :rtype: bytes

        """
        assert not command & 0x80
        self.write(command, length)
        buf = ctypes.create_string_buffer(8)
        res = self._check_error(hidapi.hid_read_timeout(self._dev,
                                buf, len(buf), timeout))
        assert res == len(buf), res
        command, length, data = struct.unpack("BB6s", buf.raw)
        data = data[:length]
        logger.info("%s %s %r", command, length, data)
        return data

    def get_attenuation(self):
        """Reads attenuation value from Lab Brick device.

        :return: Returns the attenuation value in dB.
        :rtype: float

        """
        return ord(self.get(0x0d, 1))/4.

    def set_attenuation(self, attenuation):
        """Sets attenuation value of the Lab Brick device.

        :param attenuation: Attenuation value in dB.
        :type attenuation: int, float or Fraction

        """
        self.set(0x8d, bytes(chr(int(round(attenuation*4))), 'ascii'))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--device', default="LDA-102",
                        choices=["LDA-102", "LDA-602", "sim"])
    parser.add_argument('--bind', default="::1",
                        help="hostname or IP address to bind to")
    parser.add_argument('-p', '--port', default=8890, type=int,
                        help="TCP port to listen to")
    parser.add_argument('-s', '--serial', default=None,
                        help="USB serial number of the device")
    args = parser.parse_args()

    if args.device == "sim":
        lda = Ldasim()
    else:
        lda = Lda(args.serial, args.device)

    simple_server_loop(lda, "lda",
                       args.bind, args.port)
