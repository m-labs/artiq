from numpy import array, int32, int64, uint8, uint16, iinfo


from artiq.language.core import syscall, kernel
from artiq.language.types import TInt32, TNone, TList
from artiq.coredevice.rtio import rtio_output, rtio_input_timestamped_data
from artiq.experiment import *


class OutOfSyncException(Exception):
    """Raised when an incorrect number of ROI engine outputs has been
    retrieved from the RTIO input FIFO."""
    pass


class CXPGrabberTimeoutException(Exception):
    """Raised when a timeout occurs while attempting to read CoaXPress Grabber RTIO input events."""
    pass


@syscall(flags={"nounwind"})
def cxp_download_xml_file(buffer: TList(TInt32)) -> TInt32:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind"})
def cxp_read32(addr: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind"})
def cxp_write32(addr: TInt32, val: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind"})
def cxp_start_roi_viewer(x0: TInt32, y0: TInt32, x1: TInt32, y1: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind"})
def cxp_download_roi_viewer_frame(
    buffer: TList(TInt64),
) -> TTuple([TInt32, TInt32, TInt32]):
    raise NotImplementedError("syscall not simulated")


class CXPGrabber:
    """Driver for the CoaXPress Grabber camera interface."""

    kernel_invariants = {
        "core",
        "channel",
        "trigger_ch",
        "roi_config_ch",
        "roi_gating_ch",
        "sentinel",
    }

    def __init__(self, dmgr, channel, core_device="core", count_width=31):
        self.core = dmgr.get(core_device)

        self.channel = channel
        self.trigger_ch = channel
        self.roi_config_ch = channel + 1
        self.roi_gating_ch = channel + 2

        # This value is inserted by the gateware to mark the start of a series of
        # ROI engine outputs for one video frame.
        self.sentinel = int32(int64(2**count_width))

    @staticmethod
    def get_rtio_channels(channel, **kwargs):
        return [
            (channel, "Trigger"),
            (channel + 1, "ROI coordinates"),
            (channel + 2, "ROI mask"),
        ]

    @kernel
    def send_cxp_linktrigger(self, linktrigger, extra_linktrigger=False):
        """
        Send CoaXpress fixed-latency linktrigger to camera

        :param linktrigger: Set linktrigger type:
                            0-1 is available, when extra_linktrigger is False
                            0-3 is available, when extra_linktrigger is True
                            In CXP v1.x, linktrigger0 was called `rising edge` and linktrigger1 `falling edge`

        :param extra_linktrigger: Boolean, set to True when ExtraLsTriggerEnable is set to 1 on camera

        """
        extra_linktrigger_mask = 1 if extra_linktrigger else 0
        rtio_output(self.trigger_ch << 8, linktrigger << 1 | extra_linktrigger_mask)

    @kernel
    def setup_roi(self, n, x0, y0, x1, y1):
        """
        Defines the coordinates of a ROI.

        The coordinates are set around the current position of the RTIO time
        cursor.

        The user must keep the ROI engine disabled for a duration of more
        than one video frame after calling this function, as the output
        generated for that video frame is undefined.

        Advances the timeline by 4 coarse RTIO cycles.
        """
        c = int64(self.core.ref_multiplier)
        rtio_output(self.roi_config_ch << 8 | (4 * n + 0), x0)
        delay_mu(c)
        rtio_output(self.roi_config_ch << 8 | (4 * n + 1), y0)
        delay_mu(c)
        rtio_output(self.roi_config_ch << 8 | (4 * n + 2), x1)
        delay_mu(c)
        rtio_output(self.roi_config_ch << 8 | (4 * n + 3), y1)
        delay_mu(c)

    @kernel
    def gate_roi(self, mask):
        """
        Defines which ROI engines produce input events.

        At the end of each video frame, the output from each ROI engine that
        has been enabled by the mask is enqueued into the RTIO input FIFO.

        This function sets the mask at the current position of the RTIO time
        cursor.

        Setting the mask using this function is atomic; in other words,
        if the system is in the middle of processing a frame and the mask
        is changed, the processing will complete using the value of the mask
        that it started with.

        :param mask: bitmask enabling or disabling each ROI engine.
        """
        rtio_output(self.roi_gating_ch << 8, mask)

    @kernel
    def gate_roi_pulse(self, mask, dt):
        """
        Sets a temporary mask for the specified duration (in seconds), then
        disables all ROI engines.
        """
        self.gate_roi(mask)
        delay(dt)
        self.gate_roi(0)

    @kernel
    def input_mu(self, data, timeout_mu=-1):
        """
        Retrieves the accumulated values for one frame from the ROI engines.
        Blocks until values are available or timeout is reached.

        The input list must be a list of integers of the same length as there
        are enabled ROI engines. This method replaces the elements of the
        input list with the outputs of the enabled ROI engines, sorted by
        number.

        If the number of elements in the list does not match the number of
        ROI engines that produced output, an exception will be raised during
        this call or the next.

        If the timeout is reached before data is available, the exception
        :exc:`CXPGrabberTimeoutException` is raised.

        :param timeout_mu: Timestamp at which a timeout will occur. Set to -1
                           (default) to disable timeout.
        """
        timestamp, sentinel = rtio_input_timestamped_data(
            timeout_mu, self.roi_gating_ch
        )
        if timestamp == -1:
            raise CXPGrabberTimeoutException("Timeout before CoaXPress Grabber frame available")
        if sentinel != self.sentinel:
            raise OutOfSyncException

        for i in range(len(data)):
            timestamp, roi_output = rtio_input_timestamped_data(
                timeout_mu, self.roi_gating_ch
            )
            if roi_output == self.sentinel:
                raise OutOfSyncException
            if timestamp == -1:
                raise CXPGrabberTimeoutException(
                    "Timeout retrieving ROIs (attempting to read more ROIs than enabled?)"
                )
            data[i] = roi_output

    @kernel
    def read32(self, address: TInt32) -> TInt32:
        """
        Read a 32-bit value from camera register

        .. warning:: This is NOT a real-time operation.

        :param address: 32-bit register address to read from
        :returns: 32-bit value from register
        """
        return cxp_read32(address)

    @kernel
    def write32(self, address: TInt32, value: TInt32):
        """
        Write a 32-bit value to camera register

        .. warning:: This is NOT a real-time operation.

        :param address: 32-bit register address to write to
        :param value: 32-bit value to be written
        """
        cxp_write32(address, value)

    @kernel
    def download_local_xml(self, file_path, buffer_size=102400):
        """
        Downloads the XML setting file to PC from the camera if available.
        The file format may be .zip or .xml depending on the camera model.

        .. warning:: This is NOT a real-time operation.

        :param file_path: a relative path on PC
        :param buffer_size: size of read buffer expressed in bytes; must be a multiple of 4
        """
        buffer = [0] * (buffer_size // 4)
        size_read = cxp_download_xml_file(buffer)
        self._write_file(buffer[:size_read], file_path)

    @rpc
    def _write_file(self, data, file_path):
        """
        Write big endian encoded data into a file

        :param data: a list of 32-bit integers
        :param file_path: a relative path on PC
        """
        byte_arr = bytearray()
        for d in data:
            byte_arr += d.to_bytes(4, "big", signed=True)
        with open(file_path, "wb") as binary_file:
            binary_file.write(byte_arr)

    @kernel
    def start_roi_viewer(self, x0, y0, x1, y1):
        """
        Defines the coordinates of ROI viewer and start the capture.

        Unlike :exc:`setup_roi`, ROI viewer has a maximum size limit of 4096 pixels.

        .. warning:: This is NOT a real-time operation.
        """
        cxp_start_roi_viewer(x0, y0, x1, y1)

    @kernel
    def download_roi_viewer_frame(self, file_path):
        """
        Downloads the ROI viewer frame as a PGM file to PC.

        The user must :exc:`start_roi_viewer` and trigger the camera before the frame is avaiable.

        .. warning:: This is NOT a real-time operation.

        :param file_path: a relative path on PC
        """
        buffer = [0] * 1024
        width, height, pixel_width = cxp_download_roi_viewer_frame(buffer)
        self._write_pgm(buffer, width, height, pixel_width, file_path)

    @rpc
    def _write_pgm(self, data, width, height, pixel_width, file_path):
        """
        Write pixel data into a PGM file.

        :param data: a list of 64-bit integers
        :param file_path: a relative path on PC
        """
        if ".pgm" not in file_path.lower():
            raise ValueError("The file extension must be .pgm")

        pixels = []
        width_aligned = (width + 3) & (~3)
        for d in data[: width_aligned * height // 4]:
            pixels += [
                d & 0xFFFF,
                (d >> 16) & 0xFFFF,
                (d >> 32) & 0xFFFF,
                (d >> 48) & 0xFFFF,
            ]

        if pixel_width == 8:
            dtype = uint8
        else:
            dtype = uint16
            # pad to 16-bit for compatibility, as most software can only read 8, 16-bit PGM
            pixels = [p << (16 - pixel_width) for p in pixels]

        # trim the frame if the width is not multiple of 4
        frame = array([pixels], dtype).reshape((height, width_aligned))[:, :width]

        # save as PGM binary variant
        # https://en.wikipedia.org/wiki/Netpbm#Description
        with open(file_path, "wb") as file:
            file.write(f"P5\n{width} {height}\n{iinfo(dtype).max}\n".encode("ASCII"))
            if dtype == uint8:
                file.write(frame.tobytes())
            else:
                # PGM use big endian
                file.write(frame.astype(">u2").tobytes())
