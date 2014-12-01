import os
import atexit
import ctypes
import ctypes.util

if "." not in os.environ["PATH"].split(";"):
    os.environ["PATH"] += ";."
dir = os.path.split(__file__)[0]
if dir not in os.environ["PATH"].split(";"):
    os.environ["PATH"] += ";{}".format(dir)

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
