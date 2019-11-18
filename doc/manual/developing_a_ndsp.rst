Developing a Network Device Support Package (NDSP)
==================================================

Most ARTIQ devices are interfaced through "controllers" that expose RPC interfaces to the network (based on SiPyCo). The master never does direct I/O to the devices, but issues RPCs to the controllers when needed. As opposed to running everything on the master, this architecture has those main advantages:

* Each driver can be run on a different machine, which alleviates cabling issues and OS compatibility problems.
* Reduces the impact of driver crashes.
* Reduces the impact of driver memory leaks.

This mechanism is for "slow" devices that are directly controlled by a PC, typically over a non-realtime channel such as USB.

Certain devices (such as the PDQ2) may still perform real-time operations by having certain controls physically connected to the core device (for example, the trigger and frame selection signals on the PDQ2). For handling such cases, parts of the NDSPs may be kernels executed on the core device.

A network device support package (NDSP) is composed of several parts:

1. The `driver`, which contains the Python API functions to be called over the network, and performs the I/O to the device. The top-level module of the driver is called ``artiq.devices.XXX.driver``.
2. The `controller`, which instantiates, initializes and terminates the driver, and sets up the RPC server. The controller is a front-end command-line tool to the user and is called ``artiq.frontend.aqctl_XXX``. A ``setup.py`` entry must also be created to install it.
3. An optional `client`, which connects to the controller and exposes the functions of the driver as a command-line interface. Clients are front-end tools (called ``artiq.frontend.aqcli_XXX``) that have ``setup.py`` entries. In most cases, a custom client is not needed and the generic ``sipyco_rpctool`` utility can be used instead. Custom clients are only required when large amounts of data must be transferred over the network API, that would be unwieldy to pass as ``sipyco_rpctool`` command-line parameters.
4. An optional `mediator`, which is code executed on the client that supplements the network API. A mediator may contain kernels that control real-time signals such as TTL lines connected to the device. Simple devices use the network API directly and do not have a mediator. Mediator modules are called ``artiq.devices.XXX.mediator`` and their public classes are exported at the ``artiq.devices.XXX`` level (via ``__init__.py``) for direct import and use by the experiments.

The driver and controller
-------------------------

A controller is a piece of software that receives commands from a client over the network (or the ``localhost`` interface), drives a device, and returns information about the device to the client. The mechanism used is remote procedure calls (RPCs) using ``sipyco.pc_rpc``, which makes the network layers transparent for the driver's user.

The controller we will develop is for a "device" that is very easy to work with: the console from which the controller is run. The operation that the driver will implement is writing a message to that console.

For using RPC, the functions that a driver provides must be the methods of a single object. We will thus define a class that provides our message-printing method: ::

    class Hello:
        def message(self, msg):
            print("message: " + msg)

For a more complex driver, you would put this class definition into a separate Python module called ``driver``.

To turn it into a server, we use ``sipyco.pc_rpc``. Import the function we will use: ::

    from sipyco.pc_rpc import simple_server_loop

and add a ``main`` function that is run when the program is executed: ::

    def main():
        simple_server_loop({"hello": Hello()}, "::1", 3249)

    if __name__ == "__main__":
        main()

:tip: Defining the ``main`` function instead of putting its code directly in the ``if __name__ == "__main__"`` body enables the controller to be used as well as a setuptools entry point.

The parameters ``::1`` and ``3249`` are respectively the address to bind the server to (IPv6 localhost) and the TCP port to use. Then add a line: ::

    #!/usr/bin/env python3

at the beginning of the file, save it to ``aqctl_hello.py`` and set its execution permissions: ::

    $ chmod 755 aqctl_hello.py

Run it as: ::

    $ ./aqctl_hello.py

and verify that you can connect to the TCP port: ::

    $ telnet ::1 3249
    Trying ::1...
    Connected to ::1.
    Escape character is '^]'.

:tip: Use the key combination Ctrl-AltGr-9 to get the ``telnet>`` prompt, and enter ``close`` to quit Telnet. Quit the controller with Ctrl-C.

Also verify that a target (service) named "hello" (as passed in the first argument to ``simple_server_loop``) exists using the ``sipyco_rpctool`` program from the ARTIQ front-end tools: ::

    $ sipyco_rpctool ::1 3249 list-targets
    Target(s):   hello

The client
----------

Clients are small command-line utilities that expose certain functionalities of the drivers. The ``sipyco_rpctool`` utility contains a generic client that can be used in most cases, and developing a custom client is not required. Try these commands ::

    $ sipyco_rpctool ::1 3249 list-methods
    $ sipyco_rpctool ::1 3249 call message test

In case you are developing a NDSP that is complex enough to need a custom client, we will see how to develop one. Create a ``aqcli_hello.py`` file with the following contents: ::

    #!/usr/bin/env python3

    from sipyco.pc_rpc import Client


    def main():
        remote = Client("::1", 3249, "hello")
        try:
            remote.message("Hello World!")
        finally:
            remote.close_rpc()

    if __name__ == "__main__":
        main()

Run it as before, while the controller is running. You should see the message appearing on the controller's terminal: ::

    $ ./aqctl_hello.py
    message: Hello World!

When using the driver in an experiment, the ``Client`` instance can be returned by the environment mechanism (via the ``get_device`` and ``attr_device`` methods of :class:`artiq.language.environment.HasEnvironment`) and used normally as a device.

:warning: RPC servers operate on copies of objects provided by the client, and modifications to mutable types are not written back. For example, if the client passes a list as a parameter of an RPC method, and that method ``append()s`` an element to the list, the element is not appended to the client's list.

Command-line arguments
----------------------

Use the Python ``argparse`` module to make the bind address(es) and port configurable on the controller, and the server address, port and message configurable on the client.

We suggest naming the controller parameters ``--bind`` (which adds a bind address in addition to a default binding to localhost), ``--no-bind-localhost`` (which disables the default binding to localhost), and ``--port``, so that those parameters stay consistent across controllers. Use ``-s/--server`` and ``--port`` on the client. The ``sipyco.common_args.simple_network_args`` library function adds such arguments for the controller, and the ``sipyco.common_args.bind_address_from_args`` function processes them.

The controller's code would contain something similar to this: ::

    from sipyco.common_args import simple_network_args

    def get_argparser():
        parser = argparse.ArgumentParser(description="Hello world controller")
        simple_network_args(parser, 3249)  # 3249 is the default TCP port
        return parser

    def main():
        args = get_argparser().parse_args()
        simple_server_loop(Hello(), bind_address_from_args(args), args.port)

We suggest that you define a function ``get_argparser`` that returns the argument parser, so that it can be used to document the command line parameters using sphinx-argparse.

Logging
-------

For the debug, information and warning messages, use the ``logging`` Python module and print the log on the standard error output (the default setting). The logging level is by default "WARNING", meaning that only warning messages and more critical messages will get printed (and no debug nor information messages). By calling ``sipyco.common_args.verbosity_args`` with the parser as argument, you add support for the ``--verbose`` (``-v``) and ``--quiet`` (``-q``) arguments in the parser. Each occurence of ``-v`` (resp. ``-q``) in the arguments will increase (resp. decrease) the log level of the logging module. For instance, if only one ``-v`` is present in the arguments, then more messages (info, warning and above) will get printed. If only one ``-q`` is present in the arguments, then only errors and critical messages will get printed. If ``-qq`` is present in the arguments, then only critical messages will get printed, but no debug/info/warning/error.

The program below exemplifies how to use logging: ::

    import argparse
    import logging

    from sipyco.common_args import verbosity_args, init_logger_from_args


    # get a logger that prints the module name
    logger = logging.getLogger(__name__)


    def get_argparser():
        parser = argparse.ArgumentParser(description="Logging example")
        parser.add_argument("--someargument",
                            help="some argument")
        # [...]
        add_verbosity_args(parser) # This adds the -q and -v handling
        return parser


    def main():
        args = get_argparser().parse_args()
        init_logger_from_args(args) # This initializes logging system log level according to -v/-q args

        logger.debug("this is a debug message")
        logger.info("this is an info message")
        logger.warning("this is a warning message")
        logger.error("this is an error message")
        logger.critical("this is a critical message")

    if __name__ == "__main__":
        main()


Remote execution support
------------------------

If you wish to support remote execution in your controller, you may do so by simply replacing ``simple_server_loop`` with :class:`sipyco.remote_exec.simple_rexec_server_loop`.

General guidelines
------------------

* Do not use ``__del__`` to implement the cleanup code of your driver. Instead, define a ``close`` method, and call it using a ``try...finally...`` block in the controller.
* Format your source code according to PEP8. We suggest using ``flake8`` to check for compliance.
* Use new-style formatting (``str.format``) except for logging where it is not well supported, and double quotes for strings.
* The device identification (e.g. serial number, or entry in ``/dev``) to attach to must be passed as a command-line parameter to the controller. We suggest using ``-d`` and ``--device`` as parameter name.
* Controllers must be able to operate in "simulation" mode, where they behave properly even if the associated hardware is not connected. For example, they can print the data to the console instead of sending it to the device, or dump it into a file.
* The simulation mode is entered whenever the ``--simulation`` option is specified.
* Keep command line parameters consistent across clients/controllers. When adding new command line options, look for a client/controller that does a similar thing and follow its use of ``argparse``. If the original client/controller could use ``argparse`` in a better way, improve it.
* Use docstrings for all public methods of the driver (note that those will be retrieved by ``sipyco_rpctool``).
* Choose a free default TCP port and add it to the default port list in this manual.

Hosting your code
-----------------

We suggest that you create a Git repository for your code, and publish it on https://git.m-labs.hk/, GitLab, GitHub, or a similar website of your choosing. Then send us a message or pull request for your NDSP to be added to the list in this manual.
