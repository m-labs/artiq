import builtins
import linecache
import re
import os
import sys

from artiq import __artiq_dir__ as artiq_dir
from artiq.coredevice.runtime import source_loader

ZeroDivisionError = builtins.ZeroDivisionError
ValueError = builtins.ValueError
IndexError = builtins.IndexError
RuntimeError = builtins.RuntimeError
AssertionError = builtins.AssertionError


class CoreException:
    """Information about an exception raised or passed through the core device."""

    def __init__(self, exceptions, exception_info, traceback, stack_pointers, embedding_map, device_mgr):
        self.exceptions = exceptions
        self.exception_info = exception_info
        self.traceback = list(traceback)
        self.stack_pointers = stack_pointers

        first_exception = exceptions[0]
        name = first_exception[0]
        if ':' in name:
            exn_id, self.name = name.split(':', 2)
            self.id = int(exn_id)
        else:
            self.id, self.name = 0, name
        self.message = first_exception[1]
        self.params = first_exception[2]
        self.device_mgr = device_mgr
        if self.id == 0:
            self.exn_type = getattr(sys.modules[__name__], self.name.split('.')[-1])
        else:
            self.exn_type = embedding_map.retrieve_object(self.id)
        self.fmtd_message = self.format_first_exception_message()

    def append_backtrace(self, record, inlined=False):
        filename, line, column, function, address = record
        stub_globals = {"__name__": filename, "__loader__": source_loader}
        source_line = linecache.getline(filename, line, stub_globals)
        indentation = re.search(r"^\s*", source_line).end()

        if address is None:
            formatted_address = ""
        elif inlined:
            formatted_address = " (inlined)"
        else:
            formatted_address = " (RA=+0x{:x})".format(address)

        filename = filename.replace(artiq_dir, "<artiq>")
        lines = []
        if column == -1:
            lines.append("    {}".format(source_line.strip() if source_line else "<unknown>"))
            lines.append("  File \"{file}\", line {line}, in {function}{address}".
                         format(file=filename, line=line, function=function,
                                address=formatted_address))
        else:
            lines.append("    {}^".format(" " * (column - indentation)))
            lines.append("    {}".format(source_line.strip() if source_line else "<unknown>"))
            lines.append("  File \"{file}\", line {line}, column {column},"
                         " in {function}{address}".
                         format(file=filename, line=line, column=column + 1,
                                function=function, address=formatted_address))
        return lines

    def single_traceback(self, exception_index):
        # note that we insert in reversed order
        lines = []
        last_sp = 0
        start_backtrace_index = self.exception_info[exception_index][1]
        zipped = list(zip(self.traceback[start_backtrace_index:],
                          self.stack_pointers[start_backtrace_index:]))
        exception = self.exceptions[exception_index]
        name = exception[0]
        message = exception[1]
        params = exception[2]
        if ':' in name:
            exn_id, name = name.split(':', 2)
            exn_id = int(exn_id)
        else:
            exn_id = 0
        lines.append("{}({}): {}"
                     .format(name, exn_id,
                             message.format(*params) if exception_index else self.fmtd_message))
        zipped.append(((exception[3], exception[4], exception[5], exception[6],
                       None, []), None))

        for ((filename, line, column, function, address, inlined), sp) in zipped:
            # backtrace of nested exceptions may be discontinuous
            # but the stack pointer must increase monotonically
            if sp is not None and sp <= last_sp:
                continue
            last_sp = sp

            for record in reversed(inlined):
                lines += self.append_backtrace(record, True)
            lines += self.append_backtrace((filename, line, column, function,
                                            address))

        lines.append("Traceback (most recent call first):")

        return "\n".join(reversed(lines))

    def format_first_exception_message(self):
        if self.device_mgr and issubclass(self.exn_type, RTIOException):
            channel = self.params[0]
            true_params = [format_channel(channel, self.device_mgr)] + list(self.params[1:])
        else:
            true_params = self.params
        return self.message.format(*true_params)

    def __str__(self):
        tracebacks = [self.single_traceback(i) for i in range(len(self.exceptions))]
        traceback_str = ('\n\nDuring handling of the above exception, ' +
                        'another exception occurred:\n\n').join(tracebacks)
        return 'Core Device Traceback:\n' +\
                traceback_str +\
                '\n\nEnd of Core Device Traceback\n'


def format_channel(channel, device_mgr):
    def formatter(x, y):
        return "{}:{}".format(x, y)

    dev_map = device_mgr.get_device_db()
    for dev_name, device in dev_map.items():
        if dev_name == 'Grabber':
            chan = device["arguments"]["channel_base"]
            if channel == chan:
                return formatter(dev_name + " RIO coordinates", channel)
            elif channel == chan + 1:
                return formatter(dev_name + " RIO mask", channel)
        elif dev_name == 'Phaser':
            chan = device["arguments"]["channel_base"]
            if chan <= channel <= chan + 4:
                return formatter(dev_name, channel)
        elif ("arguments" in device
              and "channel" in device["arguments"]
              and device["type"] == "local"
              and device["module"].startswith("artiq.coredevice.")):
            chan = device["arguments"]["channel"]
            if channel == chan:
                return formatter(dev_name, channel)

    return str(channel)


class RTIOException(Exception):
    """Generic type for RTIO exceptions"""
    pass


class InternalError(Exception):
    """Raised when the runtime encounters an internal error condition."""
    artiq_builtin = True


class CacheError(Exception):
    """Raised when putting a value into a cache row would violate memory safety."""
    artiq_builtin = True


class RTIOUnderflow(RTIOException):
    """Raised when the CPU or DMA core fails to submit a RTIO event early
    enough (with respect to the event's timestamp).

    The offending event is discarded and the RTIO core keeps operating.
    """
    artiq_builtin = True


class RTIOOverflow(RTIOException):
    """Raised when at least one event could not be registered into the RTIO
    input FIFO because it was full (CPU not reading fast enough).

    This does not interrupt operations further than cancelling the current
    read attempt and discarding some events. Reading can be reattempted after
    the exception is caught, and events will be partially retrieved.
    """
    artiq_builtin = True


class RTIODestinationUnreachable(RTIOException):
    """Raised with a RTIO operation could not be completed due to a DRTIO link
    being down.
    """
    artiq_builtin = True


class DMAError(Exception):
    """Raised when performing an invalid DMA operation."""
    artiq_builtin = True


class ClockFailure(Exception):
    """Raised when RTIO PLL has lost lock."""


class I2CError(Exception):
    """Raised when a I2C transaction fails."""
    pass


class SPIError(Exception):
    """Raised when a SPI transaction fails."""
    pass
