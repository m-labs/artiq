import logging
import ctypes
import struct
import numpy.random
from artiq.language.units import dB, check_unit, Quantity


logger = logging.getLogger(__name__)


class ExampleARTIQDevice:
    """Example code demonstrating how to write an device controller for ARTIQ.

    What the class ought demonstrate was discussed
    on the ARTIQ mailing list Dec 2014. References to this discussion are in double parenthesis eg ((1a))
    https://ssl.serverraum.org/lists-archive/artiq/2014-December/000253.html
    """
    self._timeout_config = 1.0  # timeout in seconds for device to respond upon configuration
    self._timeout_interaction = 0.1  # timeout in seconds for device to respond post configuration

    def __init__(self, simulate_hw, serial_port):
        """Initialization steps require to create an instance of the device interface.

        Examples:
        * initiate communication with device hardware over serial port
        * locate on-disk configuration files
        * how should system respond if device can't be found? What's default timeout?

        """
        # TODO handle problem that /dev/ttyUSBx is not unique ((2g))

        # setup serial interface to device
        self.__setup_serial(serial_port)

    def __del__(self):
        """De-initialization steps required to safely shutdown an instance of the
        device interface go here.

        Examples:
        * close serial port
        * close any open files
        """

    def __setup_connection_to_parameter_database(self):
        """Do whatever is needed to communicate with the parameter database.

        :return None:
        """

    def __setup_serial(self, serial_port):
        """Do whatever is needed to communicate with a serial device.

        TODO: For the serial ports adduser user dialout and serial.serial_for_url() is much simpler,
        more powerful, and also works under windows. RJ

        :param str serial port: on Windows an integer in a string (e.g. "1"); on Linux a device path (e.g. "/dev/ttyUSB0")
        :return None:
        """

    def echo(self, s):
        """Demonstration of a simple device subroutine that echoes back whatever string is passed to it.

        :param str s: a string that will be echo'd back
        :return str: return s
        """
        replys = "echo: {}".format(s)
        logger.info(replys)
        return s

    def sphynx_documentation_example(self, arg1, arg2, arg3=True):
        """Example of how to properly label arguments for automatic parsing by the ARTIQ documentation system.

        ARTIQ uses the Sphinx documentation system to automatically generate help files for devices. The first line of
        the comment is a short synopsis of what the function does: "Example of how to...".  Separated from the first
        line by an empty carriage return is a more verbose description of what the function does. Finally, the
        documentation section is concluded by a description of the function arguments and return value in a
        particular format. See "Info field lists" http://sphinx-doc.org/domains.html#info-field-lists

        :param str arg1: arg1 is a string argument (no default value)
        :param int arg2: arg2 is an integer argument (no default value)
        :param bool arg3: arg3 is a boolean argument (true default value)
        :return int: the return value is an integer
        """
        return 0

    def example_using_logger(self):
        """Shows how to use the logger.

        The details on the python logger are here : https://docs.python.org/2/library/logging.html
        In the context of ARTIQ the logger is the mechanism by which a driver can communicate status information
        to the front-end Graphical User Interface or put critical errors into the experiment log.

        :return None:
        """
        logger.info("logs a message with level INFO")
        logger.warning("logs a message with level WARNING")
        logger.error("logs a message with level ERROR")
        logger.log("logs a message with level CRITICAL")

    def example_using_quantity_class(self, qvar1, qvar2):
        """Example of how to properly use write a function that takes arguments of the Quantity class.

        ARTIQ includes a special class for passing around Quantities that have specific types or ranges. For example,
        a device number might only be an integer, a phase (in rounds) should lie between 0 and 1, and a
        frequency can't be negative. Other advanced Quantities might be arrays or python classes.

        :param Quantity qvar1: is a ....
        :param Quantity qvar2: is a ....
        :return None:
        """
        # TODO: please include some code showing how to use this
        # show how to raise an exception if the wrong Quantity is passed or a variable that is not of type
        # Quantity

    def demo_exception_handling(self, myvar):
        """Example code that tells the device to do something specific. And throw an exception if it goes bad.

        :param int myvar: variable that modifies device behavior
        :return None:
        """
        try:
            my_random_num = numpy.random.rand(1)[0]
            if myvar < 0:
                logger.error("argument must be greater than zero")
            elif my_random_num > myvar:
                # alert GUI that this has happened
                # raise an ARTIQ specific exception here
                logger.error("you're unlucky")
            else:
                r = myvar/0
        except ZeroDivisionError:
            # caught a divide by zero error; if it can be handled locally do that
            # if it can't be handeled locally throw it for another
            logger.error("divide by zero")
            raise
        except:
            logger.error("unhandled exception")
            raise
        # TODO: Is this right? I don't know how artiq handles exceptions.

    def example_interface_with_c(self):
        """(1) example of how to interface with some generic C code

        Generic code in C with functions passing a representative sample of types
        e.g. (char[10], int[10], double[10], my_struct[10]). In a subfolder of example_artiq_device
        is the example C code along with a suitable makefile.

        :return None:
        """
        # TODO: implement this

    def program_device_with_vector_argument(self, my_vec):
        """get a vector to modify device behavior

        This could be a vector describing the waveform to be generated by an ADC

        :return None:
        """
        # TODO: implement this

    def get_from_parameter_database(self):
        """get some parameters from the parameter database

        Cases to consider:
        1) what if the requested parameter is not in the database
        2) parameter is a vector or class object

        :return None:
        """
        # TODO: implement this

    def set_variable_to_parameter_database(self):
        """update some parameters in the parameter database

        Cases to consider:
        1) requested parameter is not in the database
        2) parameter is a vector or class object

        :return None:
        """
        # TODO: implement this
    def gpib_communication_example(self):
        """per ((3a))

        :return None:
        """
        # TODO: implement this