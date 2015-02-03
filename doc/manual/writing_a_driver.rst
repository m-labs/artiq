Writing an ARTIQ Device Driver
==============================

These instructions cover writing a simple driver for a "slow" peripheral device.
A device driver consists primarily of three parts.

1. driver.py :: This file is where the low-level implementation details of the driver go. Things like
opening a serial connection to a device and passing it arguments.  Choose a name for
your driver with alphanumeric characters and underscore. For example,
widget_233A.

2. widget_233A_client.py :: This file provides a command line interface to the device. Its
an easy way to interact with the device without using the ARTIQ GUI.

3. widget_233A_controller.py :: The controller is a piece of software that receives
commands destined for driver.py from a client. The client could be my_driver_client.py
or it could be the ARTIQ GUI on another machine. The controller runs continuously in the
background waiting for requests from clients.

driver.py
---------

The low-level implementation of the driver goes here. To create a driver.py for your device
perform the following steps. By convention the name of this file is driver.py (and nothing
else).

1. Copy everything in artiq/devices/example_artiq_device to a new directory:
artiq/devices/widget_233A/.

3. Following the template in artiq/devices/widget_233A/driver.py fill out the details of your driver. Note that the
driver functionality is encapsulated in a class, e.g. Widget233A.

4. Edit artiq/devices/widget_233A/__init__.py to reflect the path to your class.

Controller Overview
-------------------

A controller is a piece of software that receives commands from a client over the network
(or the ``localhost`` interface), drives a device, and returns information about the device
to the client. The mechanism used is remote procedure calls (RPCs)
using :class:`artiq.protocols.pc_rpc`, which makes the network layers transparent
for the driver's user.

The controller we will develop is for a "device" that is very easy to work with: the
console from which the controller is run. The operation that the driver will implement
is writing a message to that console.

For using RPC, the functions that a driver provides must be the methods of a single
object. We will thus define a class that provides our message-printing method: ::

    class Hello:
        def message(self, msg):
            print("message: " + msg)

To turn it into a server, we use :class:`artiq.protocols.pc_rpc`. Import the function we will use: ::

    from artiq.protocols.pc_rpc import simple_server_loop

and add a ``main`` function that is run when the program is executed: ::

    def main():
        simple_server_loop({"hello": Hello()}, "::1", 3249)

    if __name__ == "__main__":
        main()

:tip: Defining the ``main`` function instead of putting its code directly in the ``if __name__ == "__main__"`` body enables the controller to be used as well as a setuptools entry point.

The parameters ``::1`` and ``3249`` are respectively the address to bind the server to (IPv6 localhost) and the TCP port to use. Then add a line: ::

    #!/usr/bin/env python3

at the beginning of the file, save it to ``controller.py`` and set its execution permissions: ::

    $ chmod 755 controller.py

Run it as: ::

    $ ./controller.py

and verify that you can connect to the TCP port: ::

    $ telnet ::1 3249
    Trying ::1...
    Connected to ::1.
    Escape character is '^]'.

:tip: Use the key combination Ctrl-AltGr-9 to get the ``telnet>`` prompt, and enter ``close`` to quit Telnet. Quit the controller with Ctrl-C.

Also verify that a target (service) named "hello" (as passed in the first argument to ``simple_server_loop``) exists using the ``artiq_ctlid.py`` program from the ARTIQ front-end tools: ::

    $ artiq_ctlid.py ::1 3249
    Target(s):   hello


widget_233A_controller.py
-------------------------
Use the following steps to create a controller that works with the ARTIQ ecosystem.
1. Copy artiq/frontend/example_artiq_device_controller.py to
artiq/frontend/widget_233A_controller.py.
2. With the Controller Overview in mind follow the instructions in the example code
to flesh out the behavior of a controller for your device.

Client Overview
---------------

Controller clients are small command-line utilities that expose certain
functionalities of the drivers.  It's an easy way to interact with the device
without using the ARTIQ GUI.

Create a ``client.py`` file with the following contents: ::

    #!/usr/bin/env python3

    from artiq.protocols.pc_rpc import Client


    def main():
        remote = Client("::1", 3249, "hello")
        try:
            remote.message("Hello World!")
        finally:
            remote.close_rpc()

    if __name__ == "__main__":
        main()

Run it as before, while the controller is running. You should see the message appearing
on the controller's terminal: ::

    $ ./controller.py
    message: Hello World!

When using the driver in an experiment, for simple cases the ``Client`` instance can
be returned by the :class:`artiq.language.db.AutoDB` mechanism and used normally as
a device.

:warning: RPC servers operate on copies of objects provided by the client, and
    modifications to mutable types are not written back. For example, if the
    client passes a list as a parameter of an RPC method, and that method
    ``append()s`` an element to the list, the element is not appended to the
    client's list.

The driver's controller should be saved in
~/artiq-dev/artiq/artiq/devices/driver_name/client.py.

Use the Python ``argparse`` module to make the bind address and port configurable on the controller, and the server
address, port and message configurable on the client.

We suggest naming the controller parameters ``--bind`` and ``--port`` so that those parameters stay consistent across
controller, and use ``-s/--server`` and ``--port`` on the client.

The controller's code would contain something similar to this: ::

    def get_argparser():
        parser = argparse.ArgumentParser(description="Hello world controller")
        parser.add_argument("--bind", default="::1",
                            help="hostname or IP address to bind to")
        parser.add_argument("--port", default=3249, type=int,
                            help="TCP port to listen to")
        return parser

    def main():
        args = get_argparser().parse_args()
        simple_server_loop(Hello(), args.bind, args.port)

We suggest that you define a function ``get_argparser`` that returns the argument parser, so that it can be used to document the command line parameters using sphinx-argparse.

Logging and error handling in controllers
-----------------------------------------

Unrecoverable errors (such as the hardware being unplugged) should cause timely termination of the controller, in order to notify the controller manager which may try to restart the controller later according to its policy. Throwing an exception and letting it propagate is the preferred way of reporting an unrecoverable error.

For the debug, information and warning messages, use the ``logging`` Python module and print the log on the standard error output (the default setting). The logging level is by default "WARNING", meaning that only warning messages and more critical messages will get printed (and no debug nor information messages). By calling the ``verbosity_args()`` with the parser as argument, you add support for the ``--verbose`` (``-v``) and ``--quiet`` (``-q``) arguments in the parser. Each occurence of ``-v`` (resp. ``-q``) in the arguments will increase (resp. decrease) the log level of the logging module. For instance, if only one ``-v`` is present in the arguments, then more messages (info, warning and above) will get printed. If only one ``-q`` is present in the arguments, then only errors and critical messages will get printed. If ``-qq`` is present in the arguments, then only critical messages will get printed, but no debug/info/warning/error.

The program below exemplifies how to use logging: ::

    import argparse
    import logging
    from artiq.tools import verbosity_args, init_logger


    def get_argparser():
        parser = argparse.ArgumentParser(description="Logging example")
        parser.add_argument("--someargument",
                            help="some argument")
        # [...]
        verbosity_args(parser) # This adds the -q and -v handling
        return parser


    def main():
        args = get_argparser().parse_args()
        init_logger(args) # This initializes logging system log level according to -v/-q args

        logging.debug("this is a debug message")
        logging.info("this is an info message")
        logging.warning("this is a warning message")
        logging.error("this is an error message")
        logging.critical("this is a critical message")

    if __name__ == "__main__":
        main()

The driver's server should be saved in ~/artiq-dev/artiq/artiq/devices/driver_name/server.py.

widget_233A_client.py
---------------------
Use the following steps to create a client that works with the ARTIQ ecosystem.
1. Copy artiq/frontend/example_artiq_device_client.py to
artiq/frontend/widget_233A_client.py.
2. With the Client Overview in mind follow the instructions in the example code
to flesh out the behavior of a client for your device.

setup.py
--------
Edit the entry_points section of setup.py to point to your client and controller following
the model set by example_artiq_device_client and example_artiq_device_controller.

Device Manager Udev Rules
-------------------------
On Linux systems udev is the device manager. It manages device nodes in /dev. ARTIQ drivers
often interface with instruments that have USB-Serial interfaces. Normally these devices
are assigned device nodes on an ad hock basis by the kernel (e.g. /dev/ttyUSB3); the
assignment is not deterministic. It is convenient
for device node names to be consistent for each device (e.g. /dev/artiq_ppro). This can be accomplished
by creating a udev rule (https://wiki.archlinux.org/index.php/udev).

 * Get a list of device attributes. ::

        $udevadm info -a  /dev/ttyUSB2

 *force reloading of udev
    $ sudo udevadm control --reload; udevadm trigger

        $ sudo vim /etc/udev/rules.d/30-usb-papilio-pro.rules
        SUBSYSTEM=="usb", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010", ATTRS{manufacturer}=="FTDI",
        ATTRS{manufacturer}=="FTDI", GROUP="plugdev", SYMLINK+="artiq_ppro"

 * To confirm that everything is wroking, force reloading of udev. Then disconnect and reconnect
    the serial device. ::

        $ sudo udevadm control --reload; udevadm trigger

General guidelines
------------------

* Format your source code according to PEP8. We suggest using ``flake8`` to check for compliance.
* Use new-style formatting (``str.format``) except for logging where it is not well supported, and double quotes for strings.
* The device identification (e.g. serial number) to attach to must be passed as a command-line parameter to the controller. We suggest using ``-s`` and ``--serial`` as parameter name.
* Controllers must be able to operate in "simulation" mode, where they behave properly even if the associated hardware is not connected. For example, they can print the data to the console instead of sending it to the device, or dump it into a file.
* We suggest that the simulation mode is entered by using "sim" in place of the serial number.
* Keep command line parameters consistent across clients/controllers. When adding new command line options, look for a client/controller that does a similar thing and follow its use of ``argparse``. If the original client/controller could use ``argparse`` in a better way, improve it.
* Choose a free default TCP port and add it to the default port list in this manual.
