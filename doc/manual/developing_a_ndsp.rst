Developing a Network Device Support Package (NDSP)
==================================================

Besides the kind of specialized real-time hardware most of ARTIQ is concerned with the control and management of, ARTIQ also easily handles more conventional 'slow' devices. This is done through *controllers*, based on `SiPyCo <https://github.com/m-labs/sipyco>`_ (manual hosted `here <https://m-labs.hk/artiq/sipyco-manual/>`_), which expose remote procedure call (RPC) interfaces to the network. This allows experiments to issue RPCs to the controllers as necessary, without needing to do direct I/O to the devices. Some advantages of this architecture include:

* Controllers/drivers can be run on different machines, alleviating cabling issues and OS compatibility problems.
* Reduces the impact of driver crashes.
* Reduces the impact of driver memory leaks.

Certain devices (such as the PDQ2) may still perform real-time operations by having certain controls physically connected to the core device (for example, the trigger and frame selection signals on the PDQ2). For handling such cases, parts of the support infrastructure may be kernels executed on the core device.

.. seealso::
    Some NDSPs for particular devices have already been written and made available to the public. A (non-exhaustive) list can be found on the page :doc:`list_of_ndsps`.

Components of a NDSP
--------------------

Full support for a specific device, called a network device support package or NDSP, requires several parts:

1. The `driver`, which contains the Python API functions to be called over the network and performs the I/O to the device. The top-level module of the driver should be called ``artiq.devices.XXX.driver``.
2. The `controller`, which instantiates, initializes and terminates the driver, and sets up the RPC server. The controller is a front-end command-line tool to the user and should be called ``artiq.frontend.aqctl_XXX``. A ``setup.py`` entry must also be created to install it.
3. An optional `client`, which connects to the controller and exposes the functions of the driver as a command-line interface. Clients are front-end tools (called ``artiq.frontend.aqcli_XXX``) that have ``setup.py`` entries. In most cases, a custom client is not needed and the generic ``sipyco_rpctool`` utility can be used instead. Custom clients are only required when large amounts of data, which would be unwieldy to pass as ``sipyco_rpctool`` command-line parameters, must be transferred over the network API.
4. An optional `mediator`, which is code executed on the client that supplements the network API. A mediator may contain kernels that control real-time signals such as TTL lines connected to the device. Simple devices use the network API directly and do not have a mediator. Mediator modules are called ``artiq.devices.XXX.mediator`` and their public classes are exported at the ``artiq.devices.XXX`` level (via ``__init__.py``) for direct import and use by the experiments.

The driver and controller
-------------------------

As an example, we will develop a controller for a "device" that is very easy to work with: the console from which the controller is run. The operation that the driver will implement (and offer as an RPC) is writing a message to that console.

To use RPCs, the functions that a driver provides must be the methods of a single object. We will thus define a class that provides our message-printing method: ::

    class Hello:
        def message(self, msg):
            print("message: " + msg)

For a more complex driver, we would place this class definition into a separate Python module called ``driver``. In this example, for simplicity, we can include it in the controller module.

For the controller itself, we will turn this method into a server using ``sipyco.pc_rpc``. Import the function we will use: ::

    from sipyco.pc_rpc import simple_server_loop

and add a ``main`` function that is run when the program is executed: ::

    def main():
        simple_server_loop({"hello": Hello()}, "::1", 3249)

    if __name__ == "__main__":
        main()

.. tip::
     Defining the ``main`` function instead of putting its code directly in the ``if __name__ == "__main__"`` body enables the controller to be used as a setuptools entry point as well.

The parameters ``::1`` and ``3249`` are respectively the address to bind the server to (in this case, we use IPv6 localhost) and the TCP port. Add a line: ::

    #!/usr/bin/env python3

at the beginning of the file, save it as ``aqctl_hello.py``, and set its execution permissions: ::

    $ chmod 755 aqctl_hello.py

Run it as: ::

    $ ./aqctl_hello.py

In a different console, verify that you can connect to the TCP port: ::

    $ telnet ::1 3249
    Trying ::1...
    Connected to ::1.
    Escape character is '^]'.

.. tip ::

    To exit telnet, use the escape character combination (Ctrl + ]) to access the ``telnet>`` prompt, and then enter ``quit`` or ``close`` to close the connection.

Also verify that a target (i.e. available service for RPC) named "hello" exists: ::

    $ sipyco_rpctool ::1 3249 list-targets
    Target(s):   hello

The client
----------

Clients are small command-line utilities that expose certain functionalities of the drivers. The ``sipyco_rpctool`` utility contains a generic client that can be used in most cases, and developing a custom client is not required. You have already used it above in the form of ``list-targets``. Try these commands: ::

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

Run it as before, making sure the controller is running first. You should see the message appear in the controller's terminal: ::

    $ ./aqctl_hello.py
    message: Hello World!

We see that the client has made a request to the server, which has, through the driver, performed the requisite I/O with the "device" (its console), resulting in the operation we wanted. Success!

.. warning::
    Note that RPC servers operate on copies of objects provided by the client, and modifications to mutable types are not written back. For example, if the client passes a list as a parameter of an RPC method, and that method ``append()s`` an element to the list, the element is not appended to the client's list.

To access this driver in an experiment, we can retrieve the ``Client`` instance with the ``get_device`` and ``set_device`` methods of :class:`artiq.language.environment.HasEnvironment`, and then use it like any other device (provided the controller is running and accessible at the time).

.. _ndsp-integration:

Integration with ARTIQ experiments
----------------------------------

Generally we will want to add the device to our :ref:`device database <device-db>` so that we can add it to an experiment with ``self.setattr_device`` and so the controller can be started and stopped automatically by a controller manager (the :mod:`~artiq_comtools.artiq_ctlmgr` utility from ``artiq-comtools``). To do so, add an entry to your device database in this format: ::

	device_db.update({
            "hello": {
        	"type": "controller",
        	"host": "::1",
        	"port": 3249,
        	"command": "python /abs/path/to/aqctl_hello.py -p {port}"
    	    },
	})

Now it can be added using ``self.setattr_device("hello")`` in the ``build()`` phase of the experiment, and its methods accessed via: ::

	self.hello.message("Hello world!")

.. note::
    In order to be correctly started and stopped by a controller manager, your controller must additionally implement a ``ping()`` method, which should simply return true, e.g. ::

        def ping(self):
            return True


Remote execution support
------------------------

If you wish to support remote execution in your controller, you may do so by simply replacing ``simple_server_loop`` with :class:`sipyco.remote_exec.simple_rexec_server_loop`.

Command-line arguments
----------------------

Use the Python ``argparse`` module to make the bind address(es) and port configurable on the controller, and the server address, port and message configurable on the client. We suggest naming the controller parameters ``--bind`` (which adds a bind address in addition to a default binding to localhost), ``--no-bind-localhost`` (which disables the default binding to localhost), and ``--port``, so that those parameters stay consistent across controllers. Use ``-s/--server`` and ``--port`` on the client. The :meth:`sipyco.common_args.simple_network_args` library function adds such arguments for the controller, and the :meth:`sipyco.common_args.bind_address_from_args` function processes them.

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

For debug, information and warning messages, use the ``logging`` Python module and print the log on the standard error output (the default setting). As in other areas, there are five logging levels, from most to least critical, ``CRITICAL``, ``ERROR``, ``WARNING``, ``INFO``, and ``DEBUG``. By default, the logging level starts at ``WARNING``, meaning it will print messages of level WARNING and above (and no debug nor information messages). By calling ``sipyco.common_args.verbosity_args`` with the parser as argument, you add support for the ``--verbose`` (``-v``) and ``--quiet`` (``-q``) arguments in your controller. Each occurrence of ``-v`` (resp. ``-q``) in the arguments will increase (resp. decrease) the log level of the logging module. For instance, if only one ``-v`` is present, then more messages (INFO and above) will be printed. If only one ``-q`` is present in the arguments, then ERROR and above will be printed. If ``-qq`` is present in the arguments, then only CRITICAL will be printed.

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

Additional guidelines
---------------------

Command line and options
^^^^^^^^^^^^^^^^^^^^^^^^

* Controllers should be able to operate in "simulation" mode, specified with ``--simulation``, where they behave properly even if the associated hardware is not connected. For example, they can print the data to the console instead of sending it to the device, or dump it into a file.
* The device identification (e.g. serial number, or entry in ``/dev``) to attach to must be passed as a command-line parameter to the controller. We suggest using ``-d`` and ``--device`` as parameter names.
* Keep command line parameters consistent across clients/controllers. When adding new command line options, look for a client/controller that does a similar thing and follow its use of ``argparse``. If the original client/controller could use ``argparse`` in a better way, improve it.

Style
^^^^^

* Do not use ``__del__`` to implement the cleanup code of your driver. Instead, define a ``close`` method, and call it using a ``try...finally...`` block in the controller.
* Format your source code according to PEP8. We suggest using ``flake8`` to check for compliance.
* Use new-style formatting (``str.format``) except for logging where it is not well supported, and double quotes for strings.
* Use docstrings for all public methods of the driver (note that those will be retrieved by ``sipyco_rpctool``).
* Choose a free default TCP port and add it to the :doc:`default port list<default_network_ports>` in this manual.

Hosting your code
-----------------

We suggest that you create a Git repository for your code, and publish it on https://git.m-labs.hk/, GitLab, GitHub, or a similar website of your choosing. Then send us a message or pull request for your NDSP to be added to :doc:`the list in this manual <list_of_ndsps>`.
