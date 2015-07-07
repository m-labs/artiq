# Yann Sionneau <ys@m-labs.hk>, 2015

from ctypes import byref, c_ulong
import logging

import numpy as np


logger = logging.getLogger(__name__)


class DAQmxSim:
    def load_sample_values(self, values):
        pass

    def close(self):
        pass

    def ping(self):
        return True


class DAQmx:
    """NI PXI6733 DAQ interface."""

    def __init__(self, channels, clock):
        """
        :param channels: List of channels as a string, following
            the physical channels lists and ranges NI-DAQmx syntax.

            Example: Dev1/ao0, Dev1/ao1:ao3
        :param clock: Clock source terminal as a string, following
            NI-DAQmx terminal names syntax.

            Example: PFI5
        """

        import PyDAQmx as daq

        self.channels = channels.encode()
        self.clock = clock.encode()
        self.task = None
        self.daq = daq

    def _done_callback(self, taskhandle, status, callback_data):
        if taskhandle != self.task:
            logger.warning("done callback called with unexpected task")
        else:
            self.clear_pending_task()

    def ping(self):
        try:
            data = (c_ulong*1)()
            self.daq.DAQmxGetDevSerialNum(self.device, data)
        except:
            return False
        return True

    def load_sample_values(self, sampling_freq, values):
        """Load sample values into PXI 6733 device.

        This loads sample values into the PXI 6733 device.
        The device will output samples at each clock rising edge.
        The device waits for a clock rising edge to output the first sample.

        When using several channels simultaneously, you can either concatenate
        the values for the different channels in a 1-dimensional ``values``
        numpy ndarray.

        Example:

        >>> values = np.array([ch0_samp0, ch0_samp1, ch1_samp0, ch1_samp1],
                              dtype=float)

        In this example the first two samples will be output via the first
        channel and the two following samples will be output via the second
        channel.

        Or you can use a 2-dimensional numpy ndarray like this:

        >>> values = np.array([[ch0_samp0, ch0_samp1],[ch1_samp0, ch1_samp1]],
                              dtype=float)

        Any call to this method will cancel any previous task even if it has
        not yet completed.

        :param sampling_freq: The sampling frequency in samples per second.
        :param values: A numpy ndarray of sample values (in volts) to load in
            the device.
        """

        self.clear_pending_task()
        values = values.flatten()
        t = self.daq.Task()
        t.CreateAOVoltageChan(self.channels, b"",
                              min(values), max(values),
                              self.daq.DAQmx_Val_Volts, None)

        channel_number = (c_ulong*1)()
        t.GetTaskNumChans(channel_number)
        nb_values = len(values)
        if nb_values % channel_number[0]:
            self.daq.DAQmxClearTask(t.taskHandle)
            raise ValueError("The size of the values array must be a multiple "
                             "of the number of channels ({})"
                             .format(channel_number[0]))
        samps_per_channel = nb_values // channel_number[0]

        t.CfgSampClkTiming(self.clock, sampling_freq,
                           self.daq.DAQmx_Val_Rising,
                           self.daq.DAQmx_Val_FiniteSamps, samps_per_channel)
        num_samps_written = self.daq.int32()
        values = np.require(values, dtype=float,
                            requirements=["C_CONTIGUOUS", "WRITEABLE"])
        ret = t.WriteAnalogF64(samps_per_channel, False, 0,
                               self.daq.DAQmx_Val_GroupByChannel, values,
                               byref(num_samps_written), None)
        if num_samps_written.value != nb_values:
            raise IOError("Error: only {} sample values were written"
                          .format(num_samps_written.value))
        if ret:
            raise IOError("Error while writing samples to the channel buffer")

        done_cb = self.daq.DAQmxDoneEventCallbackPtr(self._done_callback)
        self.task = t.taskHandle
        self.daq.DAQmxRegisterDoneEvent(t.taskHandle, 0, done_cb, None)
        t.StartTask()

    def clear_pending_task(self):
        """Clear any pending task."""

        if self.task is not None:
            self.daq.DAQmxClearTask(self.task)
            self.task = None

    def close(self):
        """Free any allocated resources."""

        self.clear_pending_task()
