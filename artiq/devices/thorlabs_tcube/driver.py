from enum import Enum
import logging
import struct as st
import asyncio

import asyncserial


logger = logging.getLogger(__name__)


class MGMSG(Enum):
    HW_DISCONNECT = 0x0002
    HW_REQ_INFO = 0x0005
    HW_GET_INFO = 0x0006
    HW_START_UPDATEMSGS = 0x0011
    HW_STOP_UPDATEMSGS = 0x0012
    HUB_REQ_BAYUSED = 0x0065
    HUB_GET_BAYUSED = 0x0066
    HW_RESPONSE = 0x0080
    HW_RICHRESPONSE = 0x0081
    MOD_SET_CHANENABLESTATE = 0x0210
    MOD_REQ_CHANENABLESTATE = 0x0211
    MOD_GET_CHANENABLESTATE = 0x0212
    MOD_IDENTIFY = 0x0223
    MOT_SET_ENCCOUNTER = 0x0409
    MOT_REQ_ENCCOUNTER = 0x040A
    MOT_GET_ENCCOUNTER = 0x040B
    MOT_SET_POSCOUNTER = 0x0410
    MOT_REQ_POSCOUNTER = 0x0411
    MOT_GET_POSCOUNTER = 0x0412
    MOT_SET_VELPARAMS = 0x0413
    MOT_REQ_VELPARAMS = 0x0414
    MOT_GET_VELPARAMS = 0x0415
    MOT_SET_JOGPARAMS = 0x0416
    MOT_REQ_JOGPARAMS = 0x0417
    MOT_GET_JOGPARAMS = 0x0418
    MOT_SET_LIMSWITCHPARAMS = 0x0423
    MOT_REQ_LIMSWITCHPARAMS = 0x0424
    MOT_GET_LIMSWITCHPARAMS = 0x0425
    MOT_REQ_STATUSBITS = 0x0429
    MOT_GET_STATUSBITS = 0x042A
    MOT_SET_GENMOVEPARAMS = 0x043A
    MOT_REQ_GENMOVEPARAMS = 0x043B
    MOT_GET_GENMOVEPARAMS = 0x043C
    MOT_SET_HOMEPARAMS = 0x0440
    MOT_REQ_HOMEPARAMS = 0x0441
    MOT_GET_HOMEPARAMS = 0x0442
    MOT_MOVE_HOME = 0x0443
    MOT_MOVE_HOMED = 0x0444
    MOT_SET_MOVERELPARAMS = 0x0445
    MOT_REQ_MOVERELPARAMS = 0x0446
    MOT_GET_MOVERELPARAMS = 0x0447
    MOT_MOVE_RELATIVE = 0x0448
    MOT_SET_MOVEABSPARAMS = 0x0450
    MOT_REQ_MOVEABSPARAMS = 0x0451
    MOT_GET_MOVEABSPARAMS = 0x0452
    MOT_MOVE_ABSOLUTE = 0x0453
    MOT_MOVE_VELOCITY = 0x0457
    MOT_MOVE_COMPLETED = 0x0464
    MOT_MOVE_STOP = 0x0465
    MOT_MOVE_STOPPED = 0x0466
    MOT_MOVE_JOG = 0x046A
    MOT_SUSPEND_ENDOFMOVEMSGS = 0x046B
    MOT_RESUME_ENDOFMOVEMSGS = 0x046C
    MOT_REQ_DCSTATUSUPDATE = 0x0490
    MOT_GET_DCSTATUSUPDATE = 0x0491
    MOT_ACK_DCSTATUSUPDATE = 0x0492
    MOT_SET_DCPIDPARAMS = 0x04A0
    MOT_REQ_DCPIDPARAMS = 0x04A1
    MOT_GET_DCPIDPARAMS = 0x04A2
    MOT_SET_POTPARAMS = 0x04B0
    MOT_REQ_POTPARAMS = 0x04B1
    MOT_GET_POTPARAMS = 0x04B2
    MOT_SET_AVMODES = 0x04B3
    MOT_REQ_AVMODES = 0x04B4
    MOT_GET_AVMODES = 0x04B5
    MOT_SET_BUTTONPARAMS = 0x04B6
    MOT_REQ_BUTTONPARAMS = 0x04B7
    MOT_GET_BUTTONPARAMS = 0x04B8
    MOT_SET_EEPROMPARAMS = 0x04B9
    PZ_SET_POSCONTROLMODE = 0x0640
    PZ_REQ_POSCONTROLMODE = 0x0641
    PZ_GET_POSCONTROLMODE = 0x0642
    PZ_SET_OUTPUTVOLTS = 0x0643
    PZ_REQ_OUTPUTVOLTS = 0x0644
    PZ_GET_OUTPUTVOLTS = 0x0645
    PZ_SET_OUTPUTPOS = 0x0646
    PZ_REQ_OUTPUTPOS = 0x0647
    PZ_GET_OUTPUTPOS = 0x0648
    PZ_SET_INPUTVOLTSSRC = 0x0652
    PZ_REQ_INPUTVOLTSSRC = 0x0653
    PZ_GET_INPUTVOLTSSRC = 0x0654
    PZ_SET_PICONSTS = 0x0655
    PZ_REQ_PICONSTS = 0x0656
    PZ_GET_PICONSTS = 0x0657
    PZ_GET_PZSTATUSUPDATE = 0x0661
    PZ_SET_OUTPUTLUT = 0x0700
    PZ_REQ_OUTPUTLUT = 0x0701
    PZ_GET_OUTPUTLUT = 0x0702
    PZ_SET_OUTPUTLUTPARAMS = 0x0703
    PZ_REQ_OUTPUTLUTPARAMS = 0x0704
    PZ_GET_OUTPUTLUTPARAMS = 0x0705
    PZ_START_LUTOUTPUT = 0x0706
    PZ_STOP_LUTOUTPUT = 0x0707
    PZ_SET_EEPROMPARAMS = 0x07D0
    PZ_SET_TPZ_DISPSETTINGS = 0x07D1
    PZ_REQ_TPZ_DISPSETTINGS = 0x07D2
    PZ_GET_TPZ_DISPSETTINGS = 0x07D3
    PZ_SET_TPZ_IOSETTINGS = 0x07D4
    PZ_REQ_TPZ_IOSETTINGS = 0x07D5
    PZ_GET_TPZ_IOSETTINGS = 0x07D6


class Direction:
    def __init__(self, direction):
        if direction not in (1, 2):
            raise ValueError("Direction must be either 1 or 2")
        self.direction = direction

    def __str__(self):
        if self.direction == 1:
            return "forward"
        else:
            return "backward"


class MsgError(Exception):
    pass


class Message:
    def __init__(self, id, param1=0, param2=0, dest=0x50, src=0x01,
                 data=None):
        if data is not None:
            dest |= 0x80
        self.id = id
        self.param1 = param1
        self.param2 = param2
        self.dest = dest
        self.src = src
        self.data = data

    def __str__(self):
        return ("<Message {} p1=0x{:02x} p2=0x{:02x} "
                "dest=0x{:02x} src=0x{:02x}>".format(
                    self.id, self.param1, self.param2,
                    self.dest, self.src))

    @staticmethod
    def unpack(data):
        id, param1, param2, dest, src = st.unpack("<HBBBB", data[:6])
        data = data[6:]
        if dest & 0x80:
                if data and len(data) != param1 | (param2 << 8):
                    raise ValueError("If data are provided, param1 and param2"
                                     " should contain the data length")
        else:
                data = None
        return Message(MGMSG(id), param1, param2, dest, src, data)

    def pack(self):
        if self.has_data:
            return st.pack("<HHBB", self.id.value, len(self.data),
                           self.dest | 0x80, self.src) + self.data
        else:
            return st.pack("<HBBBB", self.id.value,
                           self.param1, self.param2, self.dest, self.src)

    @property
    def has_data(self):
        return self.dest & 0x80

    @property
    def data_size(self):
        if self.has_data:
            return self.param1 | (self.param2 << 8)
        else:
            raise ValueError


class _Tcube:
    def __init__(self, serial_dev):
        self.port = asyncserial.AsyncSerial(serial_dev, baudrate=115200,
                                            rtscts=True)

    def close(self):
        """Close the device."""
        self.port.close()

    async def send(self, message):
        logger.debug("sending: %s", message)
        await self.port.write(message.pack())

    async def recv(self):
        header = await self.port.read_exactly(6)
        logger.debug("received header: %s", header)
        data = b""
        if header[4] & 0x80:
            (length, ) = st.unpack("<H", header[2:4])
            data = await self.port.read_exactly(length)
        r = Message.unpack(header + data)
        logger.debug("receiving: %s", r)
        return r

    async def handle_message(self, msg):
        # derived classes must implement this
        raise NotImplementedError

    async def send_request(self, msgreq_id, wait_for_msgs, param1=0, param2=0,
                           data=None):
        await self.send(Message(msgreq_id, param1, param2, data=data))
        msg = None
        while msg is None or msg.id not in wait_for_msgs:
            msg = await self.recv()
            await self.handle_message(msg)
        return msg

    async def set_channel_enable_state(self, activated):
        """Enable or Disable channel 1.

        :param activated: 1 to enable channel, 0 to disable it.
        """

        if activated:
            activated = 1
        else:
            activated = 2

        await self.send(Message(MGMSG.MOD_SET_CHANENABLESTATE, param1=1,
                        param2=activated))

    async def get_channel_enable_state(self):
        get_msg = await self.send_request(MGMSG.MOD_REQ_CHANENABLESTATE,
                                          [MGMSG.MOD_GET_CHANENABLESTATE], 1)
        self.chan_enabled = get_msg.param2
        if self.chan_enabled == 1:
            self.chan_enabled = True
        elif self.chan_enabled == 2:
            self.chan_enabled = False
        else:
            raise MsgError("Channel state response is invalid: neither "
                           "1 nor 2: {}".format(self.chan_enabled))
        return self.chan_enabled

    async def module_identify(self):
        """Ask device to flash its front panel led.

        Instruct hardware unit to identify itself by flashing its front panel
        led.
        """
        await self.send(Message(MGMSG.MOD_IDENTIFY))

    async def hardware_start_update_messages(self, update_rate):
        """Start status updates from the embedded controller.

        Status update messages contain information about the position and
        status of the controller.

        :param update_rate: Rate at which you will receive status updates
        """
        await self.send(Message(MGMSG.HW_START_UPDATEMSGS, param1=update_rate))

    async def hardware_stop_update_messages(self):
        """Stop status updates from the controller."""
        await self.send(Message(MGMSG.HW_STOP_UPDATEMSGS))

    async def hardware_request_information(self):
        return await self.send_request(MGMSG.HW_REQ_INFO,
                                       [MGMSG.HW_GET_INFO])

    def is_channel_enabled(self):
        return self.chan_enabled

    async def ping(self):
        try:
            await self.hardware_request_information()
        except asyncio.CancelledError:
            raise
        except:
            logger.warning("ping failed", exc_info=True)
            return False
        return True


class Tpz(_Tcube):
    """Either :py:meth:`set_tpz_io_settings()<Tpz.set_tpz_io_settings>`
    or :py:meth:`get_tpz_io_settings()<Tpz.get_tpz_io_settings>` must
    be completed to finish initialising the driver.
    """
    def __init__(self, serial_dev):
        _Tcube.__init__(self, serial_dev)
        self.voltage_limit = None

    async def handle_message(self, msg):
        msg_id = msg.id
        data = msg.data

        if msg_id == MGMSG.HW_DISCONNECT:
            raise MsgError("Error: Please disconnect the TPZ001")
        elif msg_id == MGMSG.HW_RESPONSE:
            raise MsgError("Hardware error, please disconnect "
                           "and reconnect the TPZ001")
        elif msg_id == MGMSG.HW_RICHRESPONSE:
            (code, ) = st.unpack("<H", data[2:4])
            raise MsgError("Hardware error {}: {}"
                           .format(code,
                                   data[4:].decode(encoding="ascii")))

    async def set_position_control_mode(self, control_mode):
        """Set the control loop mode.

        When in closed-loop mode, position is maintained by a feedback signal
        from the piezo actuator. This is only possible when using actuators
        equipped with position sensing.

        :param control_mode: 0x01 for Open Loop (no feedback).

            0x02 for Closed Loop (feedback employed).

            0x03 for Open Loop Smooth.

            0x04 for Closed Loop Smooth.
        """
        await self.send(Message(MGMSG.PZ_SET_POSCONTROLMODE, param1=1,
                                param2=control_mode))

    async def get_position_control_mode(self):
        """Get the control loop mode.

        :return: Returns the control mode.

            0x01 for Open Loop (no feedback).

            0x02 for Closed Loop (feedback employed).

            0x03 for Open Loop Smooth.

            0x04 for Closed Loop Smooth.

        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_POSCONTROLMODE,
                                          [MGMSG.PZ_GET_POSCONTROLMODE], 1)
        return get_msg.param2

    async def set_output_volts(self, voltage):
        """Set output voltage applied to the piezo actuator.

        This command is only applicable in Open Loop mode. If called when in
        Closed Loop mode it is ignored.

        :param voltage: The output voltage applied to the piezo when operating
            in open loop mode. The voltage value must be in range
            [0; voltage_limit]. Voltage_limit being set by the
            :py:meth:`set_tpz_io_settings()<Tpz.set_tpz_io_settings>`
            method between the three values 75 V, 100 V and 150 V.
        """
        if voltage < 0 or voltage > self.voltage_limit:
            raise ValueError("Voltage must be in range [0;{}]"
                             .format(self.voltage_limit))
        volt = int(voltage*32767/self.voltage_limit)
        payload = st.pack("<HH", 1, volt)
        await self.send(Message(MGMSG.PZ_SET_OUTPUTVOLTS, data=payload))

    async def get_output_volts(self):
        """Get the output voltage applied to the piezo actuator.

        :return: The output voltage.
        :rtype: float
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_OUTPUTVOLTS,
                                          [MGMSG.PZ_GET_OUTPUTVOLTS], 1)
        return st.unpack("<H", get_msg.data[2:])[0]*self.voltage_limit/32767

    async def set_output_position(self, position_sw):
        """Set output position of the piezo actuator.

        This command is only applicable in Closed Loop mode. If called when in
        Open Loop mode, it is ignored. The position of the actuator is relative
        to the datum set for the arrangement using the ZeroPosition method.

        :param position_sw: The output position of the piezo relative to the
            zero position. The voltage is set in the range [0; 32767] or
            [0; 65535] depending on the unit. This corresponds to 0 to 100% of
            the maximum piezo extension.
        """
        payload = st.pack("<HH", 1, position_sw)
        await self.send(Message(MGMSG.PZ_SET_OUTPUTPOS, data=payload))

    async def get_output_position(self):
        """Get output position of piezo actuator.

        :return: The output position of the piezo relative to the zero
            position.
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_OUTPUTPOS,
                                          [MGMSG.PZ_GET_OUTPUTPOS], 1)
        return st.unpack("<H", get_msg.data[2:])[0]

    async def set_input_volts_source(self, volt_src):
        """Set the input source(s) which controls the output from the HV
        amplifier circuit (i.e. the drive to the piezo actuators).

        :param volt_src: The following values are entered into the VoltSrc
            parameter to select the various analog sources:

            0x00 Software Only: Unit responds only to software inputs and the
            HV amp output is that set using the :py:meth:`set_output_volts()
            <Tpz.set_output_volts>` method.

            0x01 External Signal: Unit sums the differential signal on the rear
            panel EXT IN(+) and EXT IN(-) connectors with the voltage set
            using the set_outputvolts method.

            0x02 Potentiometer: The HV amp output is controlled by a
            potentiometer input (either on the control panel, or connected
            to the rear panel User I/O D-type connector) summed with the
            voltage set using the set_outputvolts method.

            The values can be bitwise or'ed to sum the software source with
            either or both of the other source options.
        """
        payload = st.pack("<HH", 1, volt_src)
        await self.send(Message(MGMSG.PZ_SET_INPUTVOLTSSRC, data=payload))

    async def get_input_volts_source(self):
        """Get the input source(s) which controls the output from the HV
        amplifier circuit.

        :return: Value which selects the various analog sources, cf.
            :py:meth:`set_input_volts_source()<Tpz.set_input_volts_source>`
            method docstring for meaning of bits.
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_INPUTVOLTSSRC,
                                          [MGMSG.PZ_GET_INPUTVOLTSSRC], 1)
        return st.unpack("<H", get_msg.data[2:])[0]

    async def set_pi_constants(self, prop_const, int_const):
        """Set the proportional and integration feedback loop constants.

        These parameters determine the response characteristics when operating
        in closed loop mode.
        The processors within the controller compare the required (demanded)
        position with the actual position to create an error, which is then
        passed through a digital PI-type filter. The filtered value is used to
        develop an output voltage to drive the pizeo.

        :param prop_const: Value of the proportional term in range [0; 255].
        :param int_const: Value of the integral term in range [0; 255].
        """
        payload = st.pack("<HHH", 1, prop_const, int_const)
        await self.send(Message(MGMSG.PZ_SET_PICONSTS, data=payload))

    async def get_pi_constants(self):
        """Get the proportional and integration feedback loop constants.

        :return: Returns a tuple whose first element is the proportional
            term and the second element is the integral term.
        :rtype: a 2 int elements tuple : (int, int)
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_PICONSTS,
                                          [MGMSG.PZ_GET_PICONSTS], 1)
        return st.unpack("<HH", get_msg.data[2:])

    async def set_output_lut(self, lut_index, output):
        """Set the ouput LUT values for WGM (Waveform Generator Mode).

        It is possible to use the controller in an arbitrary Waveform
        Generator Mode (WGM). Rather than the unit outputting an adjustable
        but static voltage or position, the WGM allows the user to define a
        voltage or position sequence to be output, either periodically or a
        fixed number of times, with a selectable interval between adjacent
        samples.

        This waveform generation function is particularly useful for
        operations such as scanning over a particular area, or in any other
        application that requires a predefined movement sequence. The waveform
        is stored as values in an array, with a maximum of 513 samples.

        The samples can have the meaning of voltage or position; if
        open loop operation is specified when the samples are output, then
        their meaning is voltage and vice versa, if the channel is set to
        closed loop operation, the samples are interpreted as position values.

        If the waveform to be output requires less than 513 samples, it is
        sufficient to download the desired number of samples. This function is
        used to load the LUT array with the required output waveform. The
        applicable channel is specified by the Chan Ident parameter If only a
        sub set of the array is being used (as specified by the cyclelength
        parameter of the :py:meth:`set_output_lut_parameters()
        <Tpz.set_output_lut_parameters>`
        function), then only the first cyclelength values need to be set. In
        this manner, any arbitrary voltage waveform can be programmed into the
        LUT. Note. The LUT values are output by the system at a maximum
        bandwidth of 7 KHz, e.g. 500 LUT values will take approximately 71 ms
        to be clocked out.

        :param lut_index: The position in the array of the value to be set (0
            to 512 for TPZ).
        :param output: The voltage value to be set. Values are in the range
            [0; voltage_limit]. Voltage_limit being set with the
            :py:meth:`set_tpz_io_settings<Tpz.set_tpz_io_settings>`
            method.
        """
        volt = round(output*32767/self.voltage_limit)
        payload = st.pack("<HHH", 1, lut_index, volt)
        await self.send(Message(MGMSG.PZ_SET_OUTPUTLUT, data=payload))

    async def get_output_lut(self):
        """Get the ouput LUT values for WGM (Waveform Generator Mode).

        :return: a tuple whose first element is the lut index and the second is
            the voltage output value.
        :rtype: a 2 elements tuple (int, float)
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_OUTPUTLUT,
                                          [MGMSG.PZ_GET_OUTPUTLUT], 1)
        index, output = st.unpack("<Hh", get_msg.data[2:])
        return index, output*self.voltage_limit/32767

    async def set_output_lut_parameters(self, mode, cycle_length, num_cycles,
                                        delay_time, precycle_rest,
                                        postcycle_rest):
        """Set Waveform Generator Mode parameters.

        It is possible to use the controller in an arbitrary Waveform
        Generator Mode (WGM). Rather than the unit outputting an adjustable
        but static voltage or position, the WGM allows the user to define a
        voltage or position sequence to be output, either periodically or a
        fixed number of times, with a selectable interval between adjacent
        samples.
        This waveform generation function is particularly useful for operations
        such as scanning over a particular area, or in any other application
        that requires a predefined movement sequence. This function is used to
        set parameters which control the output of the LUT array.

        :param mode: Specifies the ouput mode of the LUT waveform as follows:

            0x01 - Output Continuous - The waveform is output continuously
            (i.e. until a StopOPLut command is received.)

            0x02 - Output Fixed - A fixed number of waveform cycles are output
            (as specified in the num_cycles parameter).
        :param cycle_length: Specifies how many samples will be output in each
            cycle of the waveform. It can be set in the range [0; 512]
            (for TPZ). It must be less than or equal to the total number of
            samples that were loaded.
        :param num_cycles: Specifies the number of cycles (1 to 2147483648) to
            be output when the Mode parameter is set to fixed. If Mode is set
            to Continuous, the num_cycles parameter is ignored. In both cases,
            the waveform is not output until a StartOPLUT command is received.
        :param delay_time: Specifies the delay (in sample intervals) that the
            system waits after setting each LUT output value. By default, the
            time the system takes to output LUT values (sampling interval) is
            set at the maximum bandwidth possible, i.e. 4 kHz (0.25 ms) for TPZ
            units. The delay_time parameter specifies the time interval between
            neighbouring samples, i.e. for how long the sample will remain at
            its present value. To increase the time between samples, set the
            delay_time parameter to the required additional delay (1 to
            2147483648 sample intervals). In this way, the user can stretch or
            shrink the waveform without affecting its overall shape.
        :param precycle_rest: In some applications, during waveform generation
            the first and the last samples may need to be handled differently
            from the rest of the waveform. For example, in a positioning system
            it may be necessary to start the movement by staying at a certain
            position for a specified length of time, then perform a movement,
            then remain at the last position for another specified length of
            time. This is the purpose of precycle_rest and postcycle_rest
            parameters, i.e. they specify the length of time that the first and
            last samples are output for, independently of the delay_time
            parameter. The precycle_rest parameter allows a delay time to be
            set before the system starts to clock out the LUT values. The delay
            can be set between 0 and 2147483648 sample intervals. The system
            then outputs the first value in the LUT until the PreCycleRest time
            has expired.
        :param postcycle_rest: In a similar way to precycle_rest, the
            postcycle_rest parameter specifies the delay imposed by the system
            after a LUT table has been output. The delay can be set between 0
            and 2147483648 sample intervals. The system then outputs the last
            value in the cycle until the postcycle_rest time has expired.
        """
        # triggering is not supported by the TPZ device
        payload = st.pack("<HHHLLLLHLH", 1, mode, cycle_length, num_cycles,
                          delay_time, precycle_rest, postcycle_rest,
                          0, 0, 0)
        await self.send(Message(MGMSG.PZ_SET_OUTPUTLUTPARAMS, data=payload))

    async def get_output_lut_parameters(self):
        """Get Waveform Generator Mode parameters.

        :return: a 6 int elements tuple whose members are (mode, cycle_length,
            num_cycles, delay_time, precycle_rest, postcycle_rest).
        :rtype: 6 int elements tuple
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_OUTPUTLUTPARAMS,
                                          [MGMSG.PZ_GET_OUTPUTLUTPARAMS], 1)
        return st.unpack("<HHLLLL", get_msg.data[2:22])

    async def start_lut_output(self):
        """Start the voltage waveform (LUT) outputs."""
        await self.send(Message(MGMSG.PZ_START_LUTOUTPUT, param1=1))

    async def stop_lut_output(self):
        """Stop the voltage waveform (LUT) outputs."""
        await self.send(Message(MGMSG.PZ_STOP_LUTOUTPUT, param1=1))

    async def set_eeprom_parameters(self, msg_id):
        """Save the parameter settings for the specified message.

        :param msg_id: The message ID of the message containing the parameters
            to be saved.
        """
        payload = st.pack("<HH", 1, msg_id)
        await self.send(Message(MGMSG.PZ_SET_EEPROMPARAMS, data=payload))

    async def set_tpz_display_settings(self, intensity):
        """Set the intensity of the LED display on the front of the TPZ unit.

        :param intensity: The intensity is set as a value from 0 (Off) to 255
            (brightest).
        """
        payload = st.pack("<H", intensity)
        await self.send(Message(MGMSG.PZ_SET_TPZ_DISPSETTINGS, data=payload))

    async def get_tpz_display_settings(self):
        """Get the intensity of the LED display on the front of the TPZ unit.

        :return: The intensity as a value from 0 (Off) to 255 (brightest).
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_TPZ_DISPSETTINGS,
                                          [MGMSG.PZ_GET_TPZ_DISPSETTINGS], 1)
        return st.unpack("<H", get_msg.data)[0]

    async def set_tpz_io_settings(self, voltage_limit, hub_analog_input):
        """Set various I/O settings."

        :param voltage_limit: The piezo actuator connected to the T-Cube has a
            specific maximum operating voltage. This parameter sets the maximum
            output to the value among the following ones:

            75 V limit.

            100 V limit.

            150 V limit.
        :param hub_analog_input: When the T-Cube piezo driver unit is used in
            conjunction with the T-Cube Strain Gauge Reader (TSG001) on the
            T-Cube Controller Hub (TCH001), a feedback signal can be passed
            from the Strain Gauge Reader to the Piezo unit.
            High precision closed loop operation is then possible using the
            complete range of feedback-equipped piezo actuators.
            This parameter is routed to the Piezo unit as follows:

            0x01: the feedback signals run through all T-Cube bays.

            0x02: the feedback signals run between adjacent pairs of T-Cube
            bays (i.e. 1&2, 3&4, 5&6). This setting is useful when several
            pairs of Strain Gauge/Piezo Driver cubes are being used on the same
            hub.

            0x03: the feedback signals run through the read panel SMA
            connectors.
        """
        self.voltage_limit = voltage_limit

        if self.voltage_limit == 75:
            voltage_limit = 1
        elif self.voltage_limit == 100:
            voltage_limit = 2
        elif self.voltage_limit == 150:
            voltage_limit = 3
        else:
            raise ValueError("voltage_limit must be 75 V, 100 V or 150 V")

        payload = st.pack("<HHHHH", 1, voltage_limit, hub_analog_input, 0, 0)
        await self.send(Message(MGMSG.PZ_SET_TPZ_IOSETTINGS, data=payload))

    async def get_tpz_io_settings(self):
        """Get various I/O settings.

        :return: Returns a tuple whose elements are the voltage limit and the
            Hub analog input. Refer to :py:meth:`set_tpz_io_settings()
            <Tpz.set_tpz_io_settings>` for
            the meaning of those parameters.
        :rtype: a 2 elements tuple (int, int)
        """
        get_msg = await self.send_request(MGMSG.PZ_REQ_TPZ_IOSETTINGS,
                                          [MGMSG.PZ_GET_TPZ_IOSETTINGS], 1)
        voltage_limit, hub_analog_input = st.unpack("<HH", get_msg.data[2:6])
        if voltage_limit == 1:
            voltage_limit = 75
        elif voltage_limit == 2:
            voltage_limit = 100
        elif voltage_limit == 3:
            voltage_limit = 150
        else:
            raise ValueError("Voltage limit should be in range [1; 3]")
        self.voltage_limit = voltage_limit
        return voltage_limit, hub_analog_input


class Tdc(_Tcube):
    def __init__(self, *args, **kwargs):
        _Tcube.__init__(self, *args, **kwargs)
        self.status_report_counter = 0

    async def handle_message(self, msg):
        msg_id = msg.id
        data = msg.data

        if msg_id == MGMSG.HW_DISCONNECT:
            raise MsgError("Error: Please disconnect the TDC001")
        elif msg_id == MGMSG.HW_RESPONSE:
            raise MsgError("Hardware error, please disconnect "
                           "and reconnect the TDC001")
        elif msg_id == MGMSG.HW_RICHRESPONSE:
            (code, ) = st.unpack("<H", data[2:4])
            raise MsgError("Hardware error {}: {}"
                           .format(code,
                                   data[4:].decode(encoding="ascii")))
        elif (msg_id == MGMSG.MOT_MOVE_COMPLETED or
              msg_id == MGMSG.MOT_MOVE_STOPPED or
              msg_id == MGMSG.MOT_GET_DCSTATUSUPDATE):
            if self.status_report_counter == 25:
                self.status_report_counter = 0
                await self.send(Message(MGMSG.MOT_ACK_DCSTATUSUPDATE))
            else:
                self.status_report_counter += 1
            # 'r' is a currently unused and reserved field
            self.position, self.velocity, r, self.status = st.unpack(
                "<LHHL", data[2:])

    async def is_moving(self):
        status_bits = await self.get_status_bits()
        return (status_bits & 0x2F0) != 0

    async def set_pot_parameters(self, zero_wnd, vel1, wnd1, vel2, wnd2, vel3,
                                 wnd3, vel4):
        """Set pot parameters.

        :param zero_wnd: The deflection from the mid position (in ADC counts
            0 to 127) before motion can start.
        :param vel1: The velocity to move when between zero_wnd and wnd1.
        :param wnd1: The deflection from the mid position (in ADC counts
            zero_wnd to 127) to apply vel1.
        :param vel2: The velocity to move when between wnd1 and wnd2.
        :param wnd2: The deflection from the mid position (in ADC counts
            wnd1 to 127) to apply vel2.
        :param vel3: The velocity to move when between wnd2 and wnd3.
        :param wnd3: The deflection from the mid position (in ADC counts
            wnd2 to 127) to apply vel3.
        :param vel4: The velocity to move when beyond wnd3.
        """
        payload = st.pack("<HHLHLHLHL", 1, zero_wnd, vel1, wnd1, vel2, wnd2,
                          vel3, wnd3, vel4)
        await self.send(Message(MGMSG.MOT_SET_POTPARAMS, data=payload))

    async def get_pot_parameters(self):
        """Get pot parameters.

        :return: An 8 int tuple containing the following values: zero_wnd,
            vel1, wnd1, vel2, wnd2, vel3, wnd3, vel4. See
            :py:meth:`set_pot_parameters()<Tdc.set_pot_parameters>` for a
            description of each tuple element meaning.
        :rtype: An 8 int tuple
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_POTPARAMS,
                                          [MGMSG.MOT_GET_POTPARAMS], 1)
        return st.unpack("<HLHLHLHL", get_msg.data[2:])

    async def hub_get_bay_used(self):
        get_msg = await self.send_request(MGMSG.HUB_REQ_BAYUSED,
                                          [MGMSG.HUB_GET_BAYUSED])
        return get_msg.param1

    async def set_position_counter(self, position):
        """Set the "live" position count in the controller.

        In general, this command is not normally used. Instead, the stage is
        homed immediately after power-up; and after the homing process is
        completed, the position counter is automatically updated to show the
        actual position.

        :param position: The new value of the position counter.
        """
        payload = st.pack("<Hl", 1, position)
        await self.send(Message(MGMSG.MOT_SET_POSCOUNTER, data=payload))

    async def get_position_counter(self):
        """Get the "live" position count from the controller.

        :return: The value of the position counter.
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_POSCOUNTER,
                                          [MGMSG.MOT_GET_POSCOUNTER], 1)
        return st.unpack("<l", get_msg.data[2:])[0]

    async def set_encoder_counter(self, encoder_count):
        """Set encoder count in the controller.

        This is only applicable to stages and actuators fitted
        with an encoder. In general this command is not normally used.
        Instead the device is homed at power-up.

        :param encoder_count: The new value of the encoder counter.
        """
        payload = st.pack("<Hl", 1, encoder_count)
        await self.send(Message(MGMSG.MOT_SET_ENCCOUNTER, data=payload))

    async def get_encoder_counter(self):
        """Get encoder count from the controller.

        :return: The value of the encoder counter.
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_ENCCOUNTER,
                                          [MGMSG.MOT_GET_ENCCOUNTER], 1)
        return st.unpack("<l", get_msg.data[2:])[0]

    async def set_velocity_parameters(self, acceleration, max_velocity):
        """Set the trapezoidal velocity parameter.

        :param acceleration: The acceleration in encoder counts/sec/sec.
        :param max_velocity: The maximum (final) velocity in counts/sec.
        """
        payload = st.pack("<HLLL", 1, 0, acceleration, max_velocity)
        await self.send(Message(MGMSG.MOT_SET_VELPARAMS, data=payload))

    async def get_velocity_parameters(self):
        """Get the trapezoidal velocity parameters.

        :return: A 2 int tuple: (acceleration, max_velocity).
        :rtype: A 2 int tuple (int, int)
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_VELPARAMS,
                                          [MGMSG.MOT_GET_VELPARAMS], 1)
        return st.unpack("<LL", get_msg.data[6:])

    async def set_jog_parameters(self, mode, step_size, acceleration,
                                 max_velocity, stop_mode):
        """Set the velocity jog parameters.

        :param mode: 1 for continuous jogging, 2 for single step jogging.
        :param step_size: The jog step size in encoder counts.
        :param acceleration: The acceleration in encoder counts/sec/sec.
        :param max_velocity: The maximum (final) velocity in encoder
            counts/sec.
        :param stop_mode: 1 for immediate (abrupt) stop, 2 for profiled stop
            (with controlled deceleration).
        """
        payload = st.pack("<HHLLLLH", 1, mode, step_size, 0, acceleration,
                          max_velocity, stop_mode)
        await self.send(Message(MGMSG.MOT_SET_JOGPARAMS, data=payload))

    async def get_jog_parameters(self):
        """Get the velocity jog parameters.

        :return: A 5 int tuple containing in this order: jog_mode,
            step_size, acceleration, max_velocity, stop_mode
        :rtype: A 5 int tuple.
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_JOGPARAMS,
                                          [MGMSG.MOT_GET_JOGPARAMS], 1)
        (jog_mode, step_size, _, acceleration, max_velocity,
         stop_mode) = st.unpack("<HLLLLH", get_msg.data[2:])
        return jog_mode, step_size, acceleration, max_velocity, stop_mode

    async def set_gen_move_parameters(self, backlash_distance):
        """Set the backlash distance.

        :param backlash_distance: The value of the backlash distance,
            which specifies the relative distance in position counts.
        """
        payload = st.pack("<Hl", 1, backlash_distance)
        await self.send(Message(MGMSG.MOT_SET_GENMOVEPARAMS, data=payload))

    async def get_gen_move_parameters(self):
        """Get the backlash distance.

        :return: The value of the backlash distance.
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_GENMOVEPARAMS,
                                          [MGMSG.MOT_GET_GENMOVEPARAMS], 1)
        return st.unpack("<l", get_msg.data[2:])[0]

    async def set_move_relative_parameters(self, relative_distance):
        """Set the following relative move parameter: relative_distance.

        :param relative_distance: The distance to move. This is a signed
            integer that specifies the relative distance in position encoder
            counts.
        """
        payload = st.pack("<Hl", 1, relative_distance)
        await self.send(Message(MGMSG.MOT_SET_MOVERELPARAMS, data=payload))

    async def get_move_relative_parameters(self):
        """Get the relative distance move parameter.

        :return: The relative distance move parameter.
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_MOVERELPARAMS,
                                          [MGMSG.MOT_GET_MOVERELPARAMS], 1)
        return st.unpack("<l", get_msg.data[2:])[0]

    async def set_move_absolute_parameters(self, absolute_position):
        """Set the following absolute move parameter: absolute_position.

        :param absolute_position: The absolute position to move. This is a
            signed integer that specifies the absolute move position in encoder
            counts.
        """
        payload = st.pack("<Hl", 1, absolute_position)
        await self.send(Message(MGMSG.MOT_SET_MOVEABSPARAMS, data=payload))

    async def get_move_absolute_parameters(self):
        """Get the absolute position move parameter.

        :return: The absolute position to move.
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_MOVEABSPARAMS,
                                          [MGMSG.MOT_GET_MOVEABSPARAMS], 1)
        return st.unpack("<l", get_msg.data[2:])[0]

    async def set_home_parameters(self, home_velocity):
        """Set the homing velocity parameter.

        :param home_velocity: Homing velocity.
        """
        payload = st.pack("<HHHLL", 1, 0, 0, home_velocity, 0)
        await self.send(Message(MGMSG.MOT_SET_HOMEPARAMS, data=payload))

    async def get_home_parameters(self):
        """Get the homing velocity parameter.

        :return: The homing velocity.
        :rtype: int
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_HOMEPARAMS,
                                          [MGMSG.MOT_GET_HOMEPARAMS], 1)
        return st.unpack("<L", get_msg.data[6:10])[0]

    async def move_home(self):
        """Start a home move sequence.

        This call is blocking until device is homed or move is stopped.
        """
        await self.send_request(MGMSG.MOT_MOVE_HOME,
                                [MGMSG.MOT_MOVE_HOMED, MGMSG.MOT_MOVE_STOPPED],
                                1)

    async def set_limit_switch_parameters(self, cw_hw_limit, ccw_hw_limit):
        """Set the limit switch parameters.

        :param cw_hw_limit: The operation of clockwise hardware limit switch
            when contact is made.

            0x01 Ignore switch or switch not present.

            0x02 Switch makes on contact.

            0x03 Switch breaks on contact.

            0x04 Switch makes on contact - only used for homes (e.g. limit
            switched rotation stages).

            0x05 Switch breaks on contact - only used for homes (e.g. limit
            switched rotations stages).

            0x06 For PMD based brushless servo controllers only - uses index
            mark for homing.

            Note. Set upper bit to swap CW and CCW limit switches in code. Both
            CWHardLimit and CCWHardLimit structure members will have the upper
            bit set when limit switches have been physically swapped.
        :param ccw_hw_limit: The operation of counter clockwise hardware limit
            switch when contact is made.
        """
        payload = st.pack("<HHHLLH", 1, cw_hw_limit, ccw_hw_limit, 0, 0, 0)
        await self.send(Message(MGMSG.MOT_SET_LIMSWITCHPARAMS, data=payload))

    async def get_limit_switch_parameters(self):
        """Get the limit switch parameters.

        :return: A 2 int tuple containing the following in order: cw_hw_limit,
         ccw_hw_limit. Cf. description in
         :py:meth:`set_limit_switch_parameters()
         <Tdc.set_limit_switch_parameters>`
         method.
        :rtype: A 2 int tuple.
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_LIMSWITCHPARAMS,
                                          [MGMSG.MOT_GET_LIMSWITCHPARAMS], 1)
        return st.unpack("<HH", get_msg.data[2:6])

    async def move_relative_memory(self):
        """Start a relative move of distance in the controller's memory

        The relative distance parameter used for the move will be the parameter
        sent previously by a :py:meth:`set_move_relative_parameters()
        <Tdc.set_move_relative_parameters>`
        command.
        """
        await self.send_request(MGMSG.MOT_MOVE_RELATIVE,
                                [MGMSG.MOT_MOVE_COMPLETED,
                                 MGMSG.MOT_MOVE_STOPPED],
                                1)

    async def move_relative(self, relative_distance):
        """Start a relative move

        :param relative_distance: The distance to move in position encoder
            counts.
        """
        payload = st.pack("<Hl", 1, relative_distance)
        await self.send_request(MGMSG.MOT_MOVE_RELATIVE,
                                [MGMSG.MOT_MOVE_COMPLETED,
                                 MGMSG.MOT_MOVE_STOPPED],
                                data=payload)

    async def move_absolute_memory(self):
        """Start an absolute move of distance in the controller's memory.

        The absolute move position parameter used for the move will be the
        parameter sent previously by a :py:meth:`set_move_absolute_parameters()
        <Tdc.set_move_absolute_parameters>`
        command.
        """
        await self.send_request(MGMSG.MOT_MOVE_ABSOLUTE,
                                [MGMSG.MOT_MOVE_COMPLETED,
                                 MGMSG.MOT_MOVE_STOPPED],
                                param1=1)

    async def move_absolute(self, absolute_distance):
        """Start an absolute move.

        :param absolute_distance: The distance to move. This is a signed
            integer that specifies the absolute distance in position encoder
            counts.
        """
        payload = st.pack("<Hl", 1, absolute_distance)
        await self.send_request(MGMSG.MOT_MOVE_ABSOLUTE,
                                [MGMSG.MOT_MOVE_COMPLETED,
                                 MGMSG.MOT_MOVE_STOPPED],
                                data=payload)

    async def move_jog(self, direction):
        """Start a jog move.

        :param direction: The direction to jog. 1 is forward, 2 is backward.
        """
        await self.send_request(MGMSG.MOT_MOVE_JOG,
                                [MGMSG.MOT_MOVE_COMPLETED,
                                 MGMSG.MOT_MOVE_STOPPED],
                                param1=1, param2=direction)

    async def move_velocity(self, direction):
        """Start a move.

        When this method is called, the motor will move continuously in the
        specified direction using the velocity parameter set by the
        :py:meth:`set_move_relative_parameters()
        <Tdc.set_move_relative_parameters>`
        command until a :py:meth:`move_stop()<Tdc.move_stop>` command (either
        StopImmediate or StopProfiled) is called, or a limit switch is reached.

        :param direction: The direction to jog: 1 to move forward, 2 to move
            backward.
        """
        await self.send(Message(MGMSG.MOT_MOVE_VELOCITY, param1=1,
                                param2=direction))

    async def move_stop(self, stop_mode):
        """Stop any type of motor move.

        Stops any of those motor move: relative, absolute, homing or move at
        velocity.

        :param stop_mode: The stop mode defines either an immediate (abrupt)
            or profiled stop. Set this byte to 1 to stop immediately, or to 2
            to stop in a controlled (profiled) manner.
        """
        if await self.is_moving():
            await self.send_request(MGMSG.MOT_MOVE_STOP,
                                    [MGMSG.MOT_MOVE_STOPPED,
                                     MGMSG.MOT_MOVE_COMPLETED],
                                    1, stop_mode)

    async def set_dc_pid_parameters(self, proportional, integral, differential,
                                    integral_limit, filter_control=0x0F):
        """Set the position control loop parameters.

        :param proportional: The proportional gain, values in range [0; 32767].
        :param integral: The integral gain, values in range [0; 32767].
        :param differential: The differential gain, values in range [0; 32767].
        :param integral_limit: The integral limit parameter is used to cap the
            value of the integrator to prevent runaway of the integral sum at
            the output. Values are in range [0; 32767]. If set to 0, then
            integration term in the PID loop is ignored.
        :param filter_control: Identifies which of the above are applied by
            setting the corresponding bit to 1. By default, all parameters are
            applied, and this parameter is set to 0x0F (1111).
        """
        payload = st.pack("<HLLLLH", 1, proportional, integral,
                          differential, integral_limit, filter_control)
        await self.send(Message(MGMSG.MOT_SET_DCPIDPARAMS, data=payload))

    async def get_dc_pid_parameters(self):
        """Get the position control loop parameters.

        :return: A 5 int tuple containing in this order:
            proportional gain, integral gain, differential gain, integral limit
            and filter control. Cf. :py:meth:`set_dc_pid_parameters()
            <Tdc.set_dc_pid_parameters>`
            for precise description.
        :rtype: A 5 int tuple.
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_DCPIDPARAMS,
                                          [MGMSG.MOT_GET_DCPIDPARAMS], 1)
        return st.unpack("<LLLLH", get_msg.data[2:])

    async def set_av_modes(self, mode_bits):
        """Set the LED indicator modes.

        The LED on the control keyboard can be configured to indicate certain
        driver states.

        :param mode_bits: Set the bit 0 will make the LED flash when the
            'Ident' message is sent.
            Set the bit 1 will make the LED flash when the motor reaches a
            forward or reverse limit switch.
            Set the bit 3 (value 8) will make the LED lit when motor is moving.
        """
        payload = st.pack("<HH", 1, mode_bits)
        await self.send(Message(MGMSG.MOT_SET_AVMODES, data=payload))

    async def get_av_modes(self):
        """Get the LED indicator mode bits.

        :return: The LED indicator mode bits.
        :rtype: int
        """
        get_msg = self.send_request(MGMSG.MOT_REQ_AVMODES,
                                    [MGMSG.MOT_GET_AVMODES], 1)
        return st.unpack("<H", get_msg.data[2:])[0]

    async def set_button_parameters(self, mode, position1, position2):
        """Set button parameters.

        The control keypad can be used either to jog the motor, or to perform
        moves to absolute positions. This function is used to set the front
        panel button functionality.

        :param mode: If set to 1, the buttons are used to jog the motor. Once
            set to this mode, the move parameters for the buttons are taken
            from the arguments of the :py:meth:`set_jog_parameters()
            <Tdc.set_jog_parameters>`
            method. If set to 2, each button can be programmed with a
            differente position value such that the controller will move the
            motor to that position when the specific button is pressed.
        :param position1: The position (in encoder counts) to which the motor
            will move when the top button is pressed.
        :param position2: The position (in encoder counts) to which the motor
            will move when the bottom button is pressed.
        """
        payload = st.pack("<HHllHH", 1, mode, position1, position2,
                          0, 0)
        await self.send(Message(MGMSG.MOT_SET_BUTTONPARAMS, data=payload))

    async def get_button_parameters(self):
        """Get button parameters.

        :return: A 3 int tuple containing in this order: button mode,
            position1 and position2. Cf. :py:meth:`set_button_parameters()
            <Tdc.set_button_parameters>`
            for description.
        :rtype: A 3 int tuple
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_BUTTONPARAMS,
                                          [MGMSG.MOT_GET_BUTTONPARAMS], 1)
        return st.unpack("<Hll", get_msg.data[2:12])

    async def set_eeprom_parameters(self, msg_id):
        """Save the parameter settings for the specified message.

        :param msg_id: The message ID of the message containing the parameters
            to be saved.
        """
        payload = st.pack("<HH", 1, msg_id)
        await self.send(Message(MGMSG.MOT_SET_EEPROMPARAMS, data=payload))

    async def get_dc_status_update(self):
        """Request a status update from the motor.

        This can be used instead of enabling regular updates.

        :return: A 3 int tuple containing in this order: position,
            velocity, status bits.
        :rtype: A 3 int tuple
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_DCSTATUSUPDATE,
                                          [MGMSG.MOT_GET_DCSTATUSUPDATE], 1)
        pos, vel, _, stat = st.unpack("<LHHL", get_msg.data[2:])
        return pos, vel, stat

    async def get_status_bits(self):
        """Request a cut down version of the status update with status bits.

        :return: The motor status.
        :rtype:
        """
        get_msg = await self.send_request(MGMSG.MOT_REQ_STATUSBITS,
                                          [MGMSG.MOT_GET_STATUSBITS], 1)
        return st.unpack("<L", get_msg.data[2:])[0]

    async def suspend_end_of_move_messages(self):
        """Disable all unsolicited "end of move" messages and error messages
        returned by the controller.

        i.e., MGMSG.MOT_MOVE_STOPPED, MGMSG.MOT_MOVE_COMPLETED,
        MGMSGS_MOT_MOVE_HOMED
        """
        await self.send(Message(MGMSG.MOT_SUSPEND_ENDOFMOVEMSGS))

    async def resume_end_of_move_messages(self):
        """Resume all unsolicited "end of move" messages and error messages
        returned by the controller.

        i.e., MGMSG.MOT_MOVE_STOPPED, MGMSG.MOT_MOVE_COMPLETED,
        MGMSG.MOT_MOVE_HOMED

        The command also disables the error messages that the controller sends
        when an error condition is detected:
        MGMSG.HW_RESPONSE,
        MGMSG.HW_RICHRESPONSE
        """
        await self.send(Message(MGMSG.MOT_RESUME_ENDOFMOVEMSGS))


class TpzSim:
    def __init__(self):
        self.voltage_limit = 150
        self.hub_analog_input = 1

    def close(self):
        pass

    def module_identify(self):
        pass

    def set_position_control_mode(self, control_mode):
        self.control_mode = control_mode

    def get_position_control_mode(self):
        return self.control_mode

    def set_output_volts(self, voltage):
        self.voltage = voltage

    def get_output_volts(self):
        return self.voltage

    def set_output_position(self, position_sw):
        self.position_sw = position_sw

    def get_output_position(self):
        return self.position_sw

    def set_input_volts_source(self, volt_src):
        self.volt_src = volt_src

    def get_input_volts_source(self):
        return self.volt_src

    def set_pi_constants(self, prop_const, int_const):
        self.prop_const = prop_const
        self.int_const = int_const

    def get_pi_constants(self):
        return self.prop_const, self.int_const

    def set_output_lut(self, lut_index, output):
        if lut_index < 0 or lut_index > 512:
            raise ValueError("LUT index should be in range [0;512] and not {}"
                             .format(lut_index))
        self.lut[lut_index] = output

    def get_output_lut(self):
        return 0, 0  # FIXME: the API description here doesn't make any sense

    def set_output_lut_parameters(self, mode, cycle_length, num_cycles,
                                  delay_time, precycle_rest, postcycle_rest):
        self.mode = mode
        self.cycle_length = cycle_length
        self.num_cycles = num_cycles
        self.delay_time = delay_time
        self.precycle_rest = precycle_rest
        self.postcycle_rest = postcycle_rest

    def get_output_lut_parameters(self):
        return (self.mode, self.cycle_length, self.num_cycles,
                self.delay_time, self.precycle_rest, self.postcycle_rest)

    def start_lut_output(self):
        pass

    def stop_lut_output(self):
        pass

    def set_eeprom_parameters(self, msg_id):
        pass

    def set_tpz_display_settings(self, intensity):
        self.intensity = intensity

    def get_tpz_display_settings(self):
        return self.intensity

    def set_tpz_io_settings(self, voltage_limit, hub_analog_input):
        if voltage_limit not in [75, 100, 150]:
            raise ValueError("voltage_limit must be 75 V, 100 V or 150 V")
        self.voltage_limit = voltage_limit
        self.hub_analog_input = hub_analog_input

    def get_tpz_io_settings(self):
        return self.voltage_limit, self.hub_analog_input


class TdcSim:
    def close(self):
        pass

    def module_identify(self):
        pass

    def set_pot_parameters(self, zero_wnd, vel1, wnd1, vel2, wnd2, vel3,
                           wnd3, vel4):
        self.zero_wnd = zero_wnd
        self.vel1 = vel1
        self.wnd1 = wnd1
        self.vel2 = vel2
        self.wnd2 = wnd2
        self.vel3 = vel3
        self.wnd3 = wnd3
        self.vel4 = vel4

    def get_pot_parameters(self):
        return (self.zero_wnd, self.vel1, self.wnd1, self.vel2, self.wnd2,
                self.vel3, self.wnd3, self.vel4)

    def hub_get_bay_used(self):
        return False

    def set_position_counter(self, position):
        self.position = position

    def get_position_counter(self):
        return self.position

    def set_encoder_counter(self, encoder_count):
        self.encoder_count = encoder_count

    def get_encoder_counter(self):
        return self.encoder_count

    def set_velocity_parameters(self, acceleration, max_velocity):
        self.acceleration = acceleration
        self.max_velocity = max_velocity

    def get_velocity_parameters(self):
        return self.acceleration, self.max_velocity

    def set_jog_parameters(self, mode, step_size, acceleration,
                           max_velocity, stop_mode):
        self.jog_mode = mode
        self.step_size = step_size
        self.acceleration = acceleration
        self.max_velocity = max_velocity
        self.stop_mode = stop_mode

    def get_jog_parameters(self):
        return (self.jog_mode, self.step_size, self.acceleration,
                self.max_velocity, self.stop_mode)

    def set_gen_move_parameters(self, backlash_distance):
        self.backlash_distance = backlash_distance

    def get_gen_move_parameters(self):
        return self.backlash_distance

    def set_move_relative_parameters(self, relative_distance):
        self.relative_distance = relative_distance

    def get_move_relative_parameters(self):
        return self.relative_distance

    def set_move_absolute_parameters(self, absolute_position):
        self.absolute_position = absolute_position

    def get_move_absolute_parameters(self):
        return self.absolute_position

    def set_home_parameters(self, home_velocity):
        self.home_velocity = home_velocity

    def get_home_parameters(self):
        return self.home_velocity

    def move_home(self):
        pass

    def set_limit_switch_parameters(self, cw_hw_limit, ccw_hw_limit):
        self.cw_hw_limit = cw_hw_limit
        self.ccw_hw_limit = ccw_hw_limit

    def get_limit_switch_parameters(self):
        return self.cw_hw_limit, self.ccw_hw_limit

    def move_relative_memory(self):
        pass

    def move_relative(self, relative_distance):
        pass

    def move_absolute_memory(self):
        pass

    def move_absolute(self, absolute_distance):
        pass

    def move_jog(self, direction):
        pass

    def move_velocity(self, direction):
        pass

    def move_stop(self, stop_mode):
        pass

    def set_dc_pid_parameters(self, proportional, integral, differential,
                              integral_limit, filter_control=0x0F):
        self.proportional = proportional
        self.integral = integral
        self.differential = differential
        self.integral_limit = integral_limit
        self.filter_control = filter_control

    def get_dc_pid_parameters(self):
        return (self.proportional, self.integral, self.differential,
                self.integral_limit, self.filter_control)

    def set_av_modes(self, mode_bits):
        self.mode_bits = mode_bits

    def get_av_modes(self):
        return self.mode_bits

    def set_button_parameters(self, mode, position1, position2):
        self.mode = mode
        self.position1 = position1
        self.position2 = position2

    def get_button_parameters(self):
        return self.mode, self.position1, self.position2

    def set_eeprom_parameters(self, msg_id):
        pass

    def get_dc_status_update(self):
        return 0, 0, 0x80000400  # FIXME: not implemented yet for simulation

    def get_status_bits(self):
        return 0x80000400  # FIXME: not implemented yet for simulation

    def suspend_end_of_move_messages(self):
        pass

    def resume_end_of_move_messages(self):
        pass
