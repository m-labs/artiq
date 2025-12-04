"""Driver for Spectrum Instrumentation AWG devices using SPCM."""

import logging
import spcm
from spcm import units, SpcmException

logger = logging.getLogger(__name__)

# *****************************************************************************
# SPCM Constant Mappings
# *****************************************************************************
# These mappings allow users to pass string arguments instead of SPCM constants.
# Use get_spcm_constant() to resolve a string or constant to its SPCM value.

SPCM_CONSTANTS = {
    # Card modes
    "dds": spcm.SPC_REP_STD_DDS,
    "single": spcm.SPC_REP_STD_SINGLE,
    "multi": spcm.SPC_REP_STD_MULTI,
    "gate": spcm.SPC_REP_STD_GATE,
    "singlerestart": spcm.SPC_REP_STD_SINGLERESTART,
    "sequence": spcm.SPC_REP_STD_SEQUENCE,
    "fifo_single": spcm.SPC_REP_FIFO_SINGLE,
    "fifo_multi": spcm.SPC_REP_FIFO_MULTI,
    "fifo_gate": spcm.SPC_REP_FIFO_GATE,
    
    # Card commands
    "enable_trigger": spcm.M2CMD_CARD_ENABLETRIGGER,
    "force_trigger": spcm.M2CMD_CARD_FORCETRIGGER,
    "disable_trigger": spcm.M2CMD_CARD_DISABLETRIGGER,
    "wait_ready": spcm.M2CMD_CARD_WAITREADY,
    "wait_trigger": spcm.M2CMD_CARD_WAITTRIGGER,
    
    # Trigger masks
    "ext0": spcm.SPC_TMASK_EXT0,
    "ext1": spcm.SPC_TMASK_EXT1,
    "software": spcm.SPC_TMASK_SOFTWARE,
    "none": spcm.SPC_TMASK_NONE,
    
    # Trigger modes
    "pos": spcm.SPC_TM_POS,
    "neg": spcm.SPC_TM_NEG,
    "both": spcm.SPC_TM_BOTH,
    "high": spcm.SPC_TM_HIGH,
    "low": spcm.SPC_TM_LOW,
    "winenter": spcm.SPC_TM_WINENTER,
    "winleave": spcm.SPC_TM_WINLEAVE,
    "inwin": spcm.SPC_TM_INWIN,
    "outsidewin": spcm.SPC_TM_OUTSIDEWIN,
    
    # Coupling modes
    "dc": spcm.COUPLING_DC,
    "ac": spcm.COUPLING_AC,
    
    # DDS data transfer modes
    "dma": spcm.SPCM_DDS_DTM_DMA,
    "single_dma": spcm.SPCM_DDS_DTM_SINGLE,
    
    # DDS trigger sources
    "card": spcm.SPCM_DDS_TRG_SRC_CARD,
    "timer": spcm.SPCM_DDS_TRG_SRC_TIMER,
    "dds_none": spcm.SPCM_DDS_TRG_SRC_NONE,
    
    # Channel enable masks
    "ch0": spcm.CHANNEL0,
    "ch1": spcm.CHANNEL1,
    "ch2": spcm.CHANNEL2,
    "ch3": spcm.CHANNEL3,
    
    # Clock modes
    "intpll": spcm.SPC_CM_INTPLL,
    "quartz1": spcm.SPC_CM_QUARTZ1,
    "quartz2": spcm.SPC_CM_QUARTZ2,
    "extrefclock": spcm.SPC_CM_EXTREFCLOCK,
    "pxirefclock": spcm.SPC_CM_PXIREFCLOCK,
}


def get_spcm_constant(value, default=None):
    """Resolve a string or constant to its SPCM value.
    
    Args:
        value: String key or SPCM constant
        default: Default value if string not found (returns value unchanged if None)
        
    Returns:
        SPCM constant value
    """
    if isinstance(value, str):
        return SPCM_CONSTANTS.get(value.lower(), default if default is not None else value)
    return value


class AWGDriver:
    """Driver for controlling Spectrum Instrumentation AWG devices."""

    def __init__(self, device_path="/dev/spcm0"):
        """
        Initialize the AWG driver.

        Args:
            device_path: Path to the SPCM device (default: "/dev/spcm0")
        """
        logger.debug(f"Initializing AWGDriver with device_path={device_path}")
        self.device_path = device_path
        self.card = None  # Lazy initialization - open on first use
        self._channels = None
        self._trigger = None
        self._dds = None
        self._clock = None
        self._closed = False
        logger.debug("AWGDriver initialized (card=None, lazy initialization)")

    def __dir__(self):
        """Control attribute visibility to prevent property access during inspection."""
        # Only expose methods and non-property attributes
        attrs = set(object.__dir__(self))
        # Remove properties that should not be accessed during inspection
        attrs.discard('channels')
        attrs.discard('trigger')
        attrs.discard('dds')
        attrs.discard('clock')
        return sorted(attrs)
    
    # *****************************************************************************
    # Property Methods
    # *****************************************************************************

    @property
    def channels(self):
        """Lazy initialization of channels."""
        logger.debug("Accessing channels property")
        self._ensure_card_open()
        if self._channels is None:
            logger.debug("Creating new Channels object (lazy initialization)")
            try:
                self._channels = spcm.Channels(self.card)
                logger.debug("Channels object created successfully")
            except Exception as e:
                logger.debug(f"Exception creating Channels: {type(e).__name__}: {e}")
                if self._is_connection_closed_error(e):
                    logger.debug("Connection closed error detected, reopening card")
                    self._reopen_card()
                    self._ensure_card_open()
                    logger.debug("Retrying Channels creation after reopen")
                    self._channels = spcm.Channels(self.card)
                    logger.debug("Channels object created successfully after recovery")
                else:
                    logger.error(f"Failed to create Channels: {e}")
                    raise
        else:
            logger.debug("Using cached Channels object")
        return self._channels

    @property
    def trigger(self):
        """Lazy initialization of trigger."""
        logger.debug("Accessing trigger property")
        self._ensure_card_open()
        if self._trigger is None:
            logger.debug("Creating new Trigger object (lazy initialization)")
            try:
                self._trigger = spcm.Trigger(self.card)
                logger.debug("Trigger object created successfully")
            except Exception as e:
                logger.debug(f"Exception creating Trigger: {type(e).__name__}: {e}")
                if self._is_connection_closed_error(e):
                    logger.debug("Connection closed error detected, reopening card")
                    self._reopen_card()
                    self._ensure_card_open()
                    logger.debug("Retrying Trigger creation after reopen")
                    self._trigger = spcm.Trigger(self.card)
                    logger.debug("Trigger object created successfully after recovery")
                else:
                    logger.error(f"Failed to create Trigger: {e}")
                    raise
        else:
            logger.debug("Using cached Trigger object")
        return self._trigger

    @property
    def dds(self):
        """Lazy initialization of DDS."""
        logger.debug("Accessing dds property")
        self._ensure_card_open()
        if self._dds is None:
            logger.debug("Creating new DDS object (lazy initialization)")
            try:
                self._dds = spcm.DDS(self.card)
                logger.debug("DDS object created successfully")
            except Exception as e:
                logger.debug(f"Exception creating DDS: {type(e).__name__}: {e}")
                if self._is_connection_closed_error(e):
                    logger.debug("Connection closed error detected, reopening card")
                    self._reopen_card()
                    self._ensure_card_open()
                    logger.debug("Retrying DDS creation after reopen")
                    self._dds = spcm.DDS(self.card)
                    logger.debug("DDS object created successfully after recovery")
                else:
                    logger.error(f"Failed to create DDS: {e}")
                    raise
        else:
            logger.debug("Using cached DDS object")
        return self._dds

    @property
    def clock(self):
        """Lazy initialization of clock."""
        logger.debug("Accessing clock property")
        self._ensure_card_open()
        if self._clock is None:
            logger.debug("Creating new Clock object (lazy initialization)")
            try:
                self._clock = spcm.Clock(self.card)
                logger.debug("Clock object created successfully")
            except Exception as e:
                logger.debug(f"Exception creating Clock: {type(e).__name__}: {e}")
                if self._is_connection_closed_error(e):
                    logger.debug("Connection closed error detected, reopening card")
                    self._reopen_card()
                    self._ensure_card_open()
                    logger.debug("Retrying Clock creation after reopen")
                    self._clock = spcm.Clock(self.card)
                    logger.debug("Clock object created successfully after recovery")
                else:
                    logger.error(f"Failed to create Clock: {e}")
                    raise
        else:
            logger.debug("Using cached Clock object")
        return self._clock

    # *****************************************************************************
    # Private Helper Methods
    # *****************************************************************************

    def _ensure_card_open(self):
        """Ensure card connection is open, opening it if necessary."""
        logger.debug(f"_ensure_card_open() called: card={self.card is not None}, _closed={self._closed}")
        if self._closed:
            logger.error("Card connection has been permanently closed")
            raise RuntimeError("Card connection has been closed. Cannot perform operations.")
        if self.card is None:
            logger.info(f"Opening AWG card connection at {self.device_path} (lazy initialization)")
            try:
                self.card = spcm.Card(self.device_path)
                self.card.open()
                logger.debug(f"Card connection opened successfully: {self.card}")
            except Exception as e:
                logger.error(f"Failed to open card connection: {type(e).__name__}: {e}")
                raise
        else:
            logger.debug("Card connection already open")

    def _reopen_card(self):
        """Reopen the card connection after it has been closed."""
        logger.debug(f"_reopen_card() called: card={self.card is not None}, _closed={self._closed}")
        if self._closed:
            logger.error("Cannot reopen: card connection has been permanently closed")
            raise RuntimeError("Card connection has been closed. Cannot perform operations.")
        logger.warning("Card connection was closed, reopening...")
        logger.debug("Clearing cached objects (channels, trigger, dds, clock)")
        self._channels = None
        self._trigger = None
        self._dds = None
        self._clock = None
        if self.card is not None:
            logger.debug("Closing old card connection before creating new one")
            try:
                self.card.close()
                logger.debug("Old card connection closed successfully")
            except Exception as e:
                logger.debug(f"Ignoring error when closing old connection: {type(e).__name__}: {e}")
                pass
        logger.debug(f"Creating new card connection at {self.device_path}")
        try:
            self.card = spcm.Card(self.device_path)
            self.card.open()
            logger.debug(f"Card connection reopened successfully: {self.card}")
        except Exception as e:
            logger.error(f"Failed to reopen card connection: {type(e).__name__}: {e}")
            self.card = None
            raise

    def _is_connection_closed_error(self, exception):
        """Check if exception indicates connection was closed."""
        error_msg = str(exception).lower()
        is_closed = (
            "connection" in error_msg and "closed" in error_msg
        ) or isinstance(exception, SpcmException) and "closed" in error_msg.lower()
        logger.debug(f"_is_connection_closed_error({type(exception).__name__}): {is_closed} - '{error_msg[:100]}'")
        return is_closed

    def _execute_with_recovery(self, method_name, *args, **kwargs):
        """Execute a card method with automatic connection recovery."""
        logger.debug(f"_execute_with_recovery('{method_name}', args={args}, kwargs={kwargs})")
        try:
            logger.debug(f"Calling card.{method_name}()")
            method = getattr(self.card, method_name)
            result = method(*args, **kwargs)
            logger.debug(f"card.{method_name}() succeeded")
            return result
        except Exception as e:
            logger.debug(f"Exception in card.{method_name}(): {type(e).__name__}: {e}")
            if self._is_connection_closed_error(e):
                logger.debug("Connection closed, attempting recovery")
                self._reopen_card()
                self._ensure_card_open()
                logger.debug(f"Retrying card.{method_name}() after recovery")
                method = getattr(self.card, method_name)
                result = method(*args, **kwargs)
                logger.debug(f"card.{method_name}() succeeded after recovery")
                return result
            else:
                logger.error(f"Non-recoverable error in card.{method_name}(): {e}")
                raise

    def _execute_subobject_with_recovery(self, property_name, method_name, *args, **kwargs):
        """Execute a method on a subobject (channels/trigger/dds/clock) with connection recovery."""
        logger.debug(f"_execute_subobject_with_recovery('{property_name}', '{method_name}', args={args}, kwargs={kwargs})")
        try:
            logger.debug(f"Getting {property_name} property")
            obj = getattr(self, property_name)
            logger.debug(f"Calling {property_name}.{method_name}()")
            method = getattr(obj, method_name)
            result = method(*args, **kwargs)
            logger.debug(f"{property_name}.{method_name}() succeeded")
            return result
        except Exception as e:
            logger.debug(f"Exception in {property_name}.{method_name}(): {type(e).__name__}: {e}")
            if self._is_connection_closed_error(e):
                logger.debug("Connection closed, attempting recovery")
                setattr(self, f'_{property_name}', None)
                logger.debug(f"Cleared cached {property_name} object")
                self._reopen_card()
                logger.debug(f"Retrying {property_name}.{method_name}() after recovery")
                obj = getattr(self, property_name)
                method = getattr(obj, method_name)
                result = method(*args, **kwargs)
                logger.debug(f"{property_name}.{method_name}() succeeded after recovery")
                return result
            else:
                logger.error(f"Non-recoverable error in {property_name}.{method_name}(): {e}")
                raise

    def _execute_dds_channel_with_recovery(self, channel, method_name, *args, **kwargs):
        """Execute a method on a DDS channel with connection recovery."""
        logger.debug(f"_execute_dds_channel_with_recovery({channel}, '{method_name}', args={args}, kwargs={kwargs})")
        try:
            logger.debug(f"Calling dds[{channel}].{method_name}()")
            method = getattr(self.dds[channel], method_name)
            result = method(*args, **kwargs)
            logger.debug(f"dds[{channel}].{method_name}() succeeded")
            return result
        except Exception as e:
            logger.debug(f"Exception in dds[{channel}].{method_name}(): {type(e).__name__}: {e}")
            if self._is_connection_closed_error(e):
                logger.debug("Connection closed, attempting recovery")
                self._dds = None
                self._reopen_card()
                logger.debug(f"Retrying dds[{channel}].{method_name}() after recovery")
                method = getattr(self.dds[channel], method_name)
                result = method(*args, **kwargs)
                logger.debug(f"dds[{channel}].{method_name}() succeeded after recovery")
                return result
            else:
                logger.error(f"Non-recoverable error in dds[{channel}].{method_name}(): {e}")
                raise

    # *****************************************************************************
    # Card Methods
    # *****************************************************************************

    def ping(self):
        """Ping method for controller manager compatibility."""
        logger.debug("ping() called")
        return True

    def card_mode(self, mode):
        """Set the card mode.
        
        Args:
            mode: Card mode. Can be SPCM constant or string like "dds"
        """
        logger.debug(f"card_mode({mode}) called")
        original_mode = mode
        self._ensure_card_open()
        
        if isinstance(mode, str):
            mode_map = {
                "dds": spcm.SPC_REP_STD_DDS,
            }
            mode = mode_map.get(mode.lower(), mode)
            logger.debug(f"Mapped mode '{original_mode}' -> {mode}")
        
        logger.debug(f"Calling card.card_mode({mode})")
        self.card.card_mode(mode)
        logger.debug("card.card_mode() completed successfully")
        
        # Clear cached subobjects since they may need to be recreated with the new mode
        logger.debug("Clearing cached objects after card_mode()")
        self._channels = None
        self._trigger = None
        self._dds = None
        self._clock = None
        logger.debug("card_mode() completed")

    def write_setup(self):
        """Write setup to card (turns on system clock signals)."""
        logger.debug("write_setup() called")
        self._ensure_card_open()
        self._execute_with_recovery('write_setup')
        logger.debug("write_setup() completed")

    def start(self, *commands):
        """Start the card with specified commands.
        
        Args:
            *commands: Commands like "enable_trigger", "force_trigger" or SPCM constants
        """
        logger.debug(f"start({commands}) called")
        self._ensure_card_open()
        spcm_commands = []
        for cmd in commands:
            if isinstance(cmd, str):
                cmd_map = {
                    "enable_trigger": spcm.M2CMD_CARD_ENABLETRIGGER,
                    "force_trigger": spcm.M2CMD_CARD_FORCETRIGGER,
                }
                cmd = cmd_map.get(cmd.lower(), cmd)
            spcm_commands.append(cmd)
        logger.debug(f"Mapped commands: {commands} -> {spcm_commands}")
        self._execute_with_recovery('start', *spcm_commands)
        logger.debug("start() completed")

    def stop(self):
        """Stop the card."""
        logger.debug("stop() called")
        self._ensure_card_open()
        self._execute_with_recovery('stop')
        logger.debug("stop() completed")

    def timeout(self, timeout_ms):
        """Set card timeout in milliseconds.
        
        Args:
            timeout_ms: Timeout in milliseconds. 0 disables timeout.
        """
        logger.debug(f"timeout({timeout_ms}) called")
        self._ensure_card_open()
        self._execute_with_recovery('timeout', timeout_ms)
        logger.debug("timeout() completed")

    def get_i(self, register):
        """Get an integer value from a register.
        
        Args:
            register: SPCM register constant
            
        Returns:
            Integer value from the register
        """
        logger.debug(f"get_i({register}) called")
        self._ensure_card_open()
        result = self._execute_with_recovery('get_i', register)
        logger.debug(f"get_i({register}) = {result}")
        return result

    def get_d(self, register):
        """Get a double value from a register.
        
        Args:
            register: SPCM register constant
            
        Returns:
            Double value from the register
        """
        logger.debug(f"get_d({register}) called")
        self._ensure_card_open()
        result = self._execute_with_recovery('get_d', register)
        logger.debug(f"get_d({register}) = {result}")
        return result

    def set_i(self, register, value):
        """Set an integer value to a register.
        
        Args:
            register: SPCM register constant
            value: Integer value to set
        """
        logger.debug(f"set_i({register}, {value}) called")
        self._ensure_card_open()
        self._execute_with_recovery('set_i', register, value)
        logger.debug("set_i() completed")

    def set_d(self, register, value):
        """Set a double value to a register.
        
        Args:
            register: SPCM register constant
            value: Double value to set
        """
        logger.debug(f"set_d({register}, {value}) called")
        self._ensure_card_open()
        self._execute_with_recovery('set_d', register, value)
        logger.debug("set_d() completed")

    # =========================================================================
    # Channel Methods
    # =========================================================================

    def channels_enable(self, enable):
        """Enable or disable channels.
        
        Args:
            enable: True to enable, False to disable
        """
        logger.debug(f"channels_enable({enable}) called")
        self._execute_subobject_with_recovery('channels', 'enable', enable)
        logger.debug(f"channels_enable({enable}) completed")

    def channels_output_load(self, load):
        """Set output load impedance.
        
        Args:
            load: Load impedance in ohms (numeric) or with units
        """
        logger.debug(f"channels_output_load({load}) called")
        if isinstance(load, (int, float)):
            load = load * units.ohm
            logger.debug(f"Converted load to {load}")
        self._execute_subobject_with_recovery('channels', 'output_load', load)
        logger.debug("channels_output_load() completed")

    def channels_amp(self, amplitude):
        """Set channel amplitude.
        
        Args:
            amplitude: Amplitude in volts (numeric) or with units
        """
        logger.debug(f"channels_amp({amplitude}) called")
        if isinstance(amplitude, (int, float)):
            amplitude = amplitude * units.V
            logger.debug(f"Converted amplitude to {amplitude}")
        self._execute_subobject_with_recovery('channels', 'amp', amplitude)
        logger.debug("channels_amp() completed")

    # =========================================================================
    # Trigger Methods
    # =========================================================================

    def trigger_or_mask(self, mask):
        """Set trigger OR mask.
        
        Args:
            mask: Trigger mask. Can be SPCM constant or string like "ext0", "ext1"
        """
        logger.debug(f"trigger_or_mask({mask}) called")
        mask = get_spcm_constant(mask)
        self._execute_subobject_with_recovery('trigger', 'or_mask', mask)
        logger.debug("trigger_or_mask() completed")

    def trigger_and_mask(self, mask):
        """Set trigger AND mask.
        
        Args:
            mask: Trigger mask. Can be SPCM constant or string like "ext0", "ext1"
        """
        logger.debug(f"trigger_and_mask({mask}) called")
        mask = get_spcm_constant(mask)
        self._execute_subobject_with_recovery('trigger', 'and_mask', mask)
        logger.debug("trigger_and_mask() completed")

    def trigger_delay(self, delay):
        """Set trigger delay.
        
        Args:
            delay: Trigger delay value
        """
        logger.debug(f"trigger_delay({delay}) called")
        self._execute_subobject_with_recovery('trigger', 'delay', delay)
        logger.debug("trigger_delay() completed")

    def trigger_ext0_mode(self, mode):
        """Set external trigger 0 mode.
        
        Args:
            mode: Trigger mode. Can be SPCM constant or string like "pos", "neg", "both"
        """
        logger.debug(f"trigger_ext0_mode({mode}) called")
        mode = get_spcm_constant(mode)
        self._execute_subobject_with_recovery('trigger', 'ext0_mode', mode)
        logger.debug("trigger_ext0_mode() completed")

    def trigger_ext0_level0(self, level):
        """Set external trigger 0 level.
        
        Args:
            level: Trigger level in volts (numeric) or with units
        """
        logger.debug(f"trigger_ext0_level0({level}) called")
        if isinstance(level, (int, float)):
            level = level * units.V
            logger.debug(f"Converted level to {level}")
        self._execute_subobject_with_recovery('trigger', 'ext0_level0', level)
        logger.debug("trigger_ext0_level0() completed")

    def trigger_ext0_coupling(self, coupling):
        """Set external trigger 0 coupling.
        
        Args:
            coupling: Coupling type. Can be SPCM constant or string like "dc", "ac"
        """
        logger.debug(f"trigger_ext0_coupling({coupling}) called")
        coupling = get_spcm_constant(coupling)
        self._execute_subobject_with_recovery('trigger', 'ext0_coupling', coupling)
        logger.debug("trigger_ext0_coupling() completed")

    def trigger_ext1_mode(self, mode):
        """Set external trigger 1 mode.
        
        Args:
            mode: Trigger mode. Can be SPCM constant or string like "pos", "neg", "both"
        """
        logger.debug(f"trigger_ext1_mode({mode}) called")
        mode = get_spcm_constant(mode)
        self._execute_subobject_with_recovery('trigger', 'ext1_mode', mode)
        logger.debug("trigger_ext1_mode() completed")

    def trigger_ext1_level0(self, level):
        """Set external trigger 1 level.
        
        Args:
            level: Trigger level in volts (numeric) or with units
        """
        logger.debug(f"trigger_ext1_level0({level}) called")
        if isinstance(level, (int, float)):
            level = level * units.V
            logger.debug(f"Converted level to {level}")
        self._execute_subobject_with_recovery('trigger', 'ext1_level0', level)
        logger.debug("trigger_ext1_level0() completed")

    def trigger_ext1_coupling(self, coupling):
        """Set external trigger 1 coupling.
        
        Args:
            coupling: Coupling type. Can be SPCM constant or string like "dc", "ac"
        """
        logger.debug(f"trigger_ext1_coupling({coupling}) called")
        coupling = get_spcm_constant(coupling)
        self._execute_subobject_with_recovery('trigger', 'ext1_coupling', coupling)
        logger.debug("trigger_ext1_coupling() completed")

    # *****************************************************************************
    # DDS Methods
    # *****************************************************************************

    def reset(self):
        """Reset the DDS."""
        logger.debug("reset() called")
        self._execute_subobject_with_recovery('dds', 'reset')
        logger.debug("reset() completed")

    def dds_data_transfer_mode(self, mode):
        """Set DDS data transfer mode.
        
        Args:
            mode: Transfer mode. Can be SPCM constant or string like "dma"
        """
        logger.debug(f"dds_data_transfer_mode({mode}) called")
        mode = get_spcm_constant(mode)
        self._execute_subobject_with_recovery('dds', 'data_transfer_mode', mode)
        logger.debug("dds_data_transfer_mode() completed")

    def dds_trg_src(self, source):
        """Set DDS trigger source.
        
        Args:
            source: Trigger source. Can be SPCM constant or string like "card", "timer"
        """
        logger.debug(f"dds_trg_src({source}) called")
        source = get_spcm_constant(source)
        self._execute_subobject_with_recovery('dds', 'trg_src', source)
        logger.debug("dds_trg_src() completed")

    def dds_trg_timer(self, time_value):
        """Set DDS trigger timer.
        
        Args:
            time_value: Timer value in seconds (numeric) or with units
        """
        logger.debug(f"dds_trg_timer({time_value}) called")
        if isinstance(time_value, (int, float)):
            time_value = time_value * units.s
            logger.debug(f"Converted time_value to {time_value}")
        self._execute_subobject_with_recovery('dds', 'trg_timer', time_value)
        logger.debug("dds_trg_timer() completed")

    def dds_exec_at_trg(self):
        """Execute DDS command at trigger."""
        logger.debug("dds_exec_at_trg() called")
        self._execute_subobject_with_recovery('dds', 'exec_at_trg')
        logger.debug("dds_exec_at_trg() completed")

    def dds_write_to_card(self):
        """Write DDS configuration to card."""
        logger.debug("dds_write_to_card() called")
        self._execute_subobject_with_recovery('dds', 'write_to_card')
        logger.debug("dds_write_to_card() completed")

    # *****************************************************************************
    # DDS Channel Methods
    # *****************************************************************************

    def dds_channel_freq(self, channel, frequency):
        """Set DDS channel frequency.
        
        Args:
            channel: DDS channel index
            frequency: Frequency in Hz (numeric) or with units
        """
        logger.debug(f"dds_channel_freq(channel={channel}, frequency={frequency}) called")
        if isinstance(frequency, (int, float)):
            frequency = frequency * units.Hz
            logger.debug(f"Converted frequency to {frequency}")
        self._execute_dds_channel_with_recovery(channel, 'freq', frequency)
        logger.debug("dds_channel_freq() completed")

    def dds_channel_amp(self, channel, amplitude):
        """Set DDS channel amplitude.
        
        Args:
            channel: DDS channel index
            amplitude: Amplitude value (0-1 or percentage)
        """
        logger.debug(f"dds_channel_amp(channel={channel}, amplitude={amplitude}) called")
        self._execute_dds_channel_with_recovery(channel, 'amp', amplitude)
        logger.debug("dds_channel_amp() completed")

    def dds_channel_phase(self, channel, phase):
        """Set DDS channel phase.
        
        Args:
            channel: DDS channel index
            phase: Phase in degrees (numeric) or with units
        """
        logger.debug(f"dds_channel_phase(channel={channel}, phase={phase}) called")
        if isinstance(phase, (int, float)):
            phase = phase * units.deg
            logger.debug(f"Converted phase to {phase}")
        self._execute_dds_channel_with_recovery(channel, 'phase', phase)
        logger.debug("dds_channel_phase() completed")

    def dds_channel_amplitude_slope(self, channel, slope):
        """Set DDS channel amplitude slope.
        
        Args:
            channel: DDS channel index
            slope: Amplitude slope value
        """
        logger.debug(f"dds_channel_amplitude_slope(channel={channel}, slope={slope}) called")
        self._execute_dds_channel_with_recovery(channel, 'amplitude_slope', slope)
        logger.debug("dds_channel_amplitude_slope() completed")

    def dds_channel_freq_slope(self, channel, slope):
        """Set DDS channel frequency slope.
        
        Args:
            channel: DDS channel index
            slope: Frequency slope value (Hz/s)
        """
        logger.debug(f"dds_channel_freq_slope(channel={channel}, slope={slope}) called")
        self._execute_dds_channel_with_recovery(channel, 'freq_slope', slope)
        logger.debug("dds_channel_freq_slope() completed")

    # *****************************************************************************
    # Clock Methods
    # *****************************************************************************

    def clock_sample_rate(self, sample_rate=None, max_rate=False):
        """Set or get the clock sample rate.
        
        Args:
            sample_rate: Sample rate in Hz (numeric) or with units. None to get current.
            max_rate: If True, set to maximum sample rate
            
        Returns:
            Current sample rate if sample_rate is None
        """
        logger.debug(f"clock_sample_rate(sample_rate={sample_rate}, max_rate={max_rate}) called")
        if sample_rate is None and not max_rate:
            result = self._execute_subobject_with_recovery('clock', 'sample_rate')
            logger.debug(f"clock_sample_rate() returned {result}")
            return result
        
        if max_rate:
            result = self._execute_subobject_with_recovery('clock', 'sample_rate', max=True)
        else:
            if isinstance(sample_rate, (int, float)):
                sample_rate = sample_rate * units.Hz
                logger.debug(f"Converted sample_rate to {sample_rate}")
            result = self._execute_subobject_with_recovery('clock', 'sample_rate', sample_rate)
        logger.debug(f"clock_sample_rate() completed, result={result}")
        return result

    # *****************************************************************************
    # Cleanup
    # *****************************************************************************

    def close(self):
        """Close the card connection."""
        logger.debug("close() called")
        self._closed = True  # Set flag first to prevent new operations
        logger.debug("_closed flag set to True")
        if self.card is not None:
            logger.debug("Card exists, attempting to close")
            try:
                logger.debug("Stopping card before closing")
                self.card.stop()
                logger.debug("Card stopped successfully")
            except Exception as e:
                logger.debug(f"Card may already be stopped: {type(e).__name__}: {e}")
            try:
                logger.info("Closing AWG card connection")
                self.card.close()
                logger.debug("Card connection closed successfully")
            except Exception as e:
                logger.error(f"Error during card cleanup: {type(e).__name__}: {e}")
            finally:
                logger.debug("Clearing all references (card, channels, trigger, dds, clock)")
                self.card = self._channels = self._trigger = self._dds = self._clock = None
        else:
            logger.debug("Card is None, nothing to close")
        logger.debug("close() completed")