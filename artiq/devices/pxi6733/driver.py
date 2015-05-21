# Yann Sionneau <ys@m-labs.hk>, 2015

from ctypes import byref
import numpy as np


class DAQmxSim:
    def load_sample_values(self, values):
        pass

    def close(self):
        pass


def done_callback_py(taskhandle, status, callback_data):
    callback_data.daq.DAQmxClearTask(taskhandle)
    callback_data.tasks.remove(taskhandle)


class DAQmx:
    """NI PXI6733 DAQ interface."""

    def __init__(self, device, analog_output, clock):
        import PyDAQmx as daq

        self.device = device
        self.analog_output = analog_output
        self.clock = clock
        self.tasks = []
        self.daq = daq

    def load_sample_values(self, values):
        """Load sample values into PXI 6733 device.

        This loads sample values into the PXI 6733 device and then
        configures a task to output those samples at each clock rising
        edge.

        A callback is registered to clear the task (deallocate resources)
        when the task has completed.

        :param values: A numpy array of sample values to load in the device.
        """

        t = self.daq.Task()
        t.CreateAOVoltageChan(self.device+b"/"+self.analog_output, b"",
                              min(values), max(values),
                              self.daq.DAQmx_Val_Volts, None)
        t.CfgSampClkTiming(self.clock, 1000.0, self.daq.DAQmx_Val_Rising,
                           self.daq.DAQmx_Val_FiniteSamps, len(values))
        num_samps_written = self.daq.int32()
        values = np.require(values, dtype=float,
                            requirements=["C_CONTIGUOUS", "WRITEABLE"])
        ret = t.WriteAnalogF64(len(values), False, 0,
                               self.daq.DAQmx_Val_GroupByChannel, values,
                               byref(num_samps_written), None)
        if num_samps_written.value != len(values):
            raise IOError("Error: only {} sample values were written"
                          .format(num_samps_written.value))
        if ret:
            raise IOError("Error while writing samples to the channel buffer")

        done_callback = self.daq.DAQmxDoneEventCallbackPtr(done_callback_py)
        self.tasks.append(t.taskHandle)
        self.daq.DAQmxRegisterDoneEvent(t.taskHandle, 0, done_callback, self)
        t.StartTask()

    def close(self):
        """Clear all pending tasks."""

        for t in self.tasks:
            self.daq.DAQmxClearTask(t)
