Writing a driver
================

These instructions cover writing a simple driver for a "slow" device, that uses the controller mechanism.

The controller
--------------

A controller is a piece of software that receives commands from a client over the network (or the ``localhost`` interface), drives a device, and returns information about the device to the client. The mechanism used is remote procedure calls (RPCs) using :class:`artiq.management.pc_rpc`, which makes the network layers transparent for the driver's user.

The controller we will develop is for a "device" that is very easy to work with: the console from which the controller is run. The operation that the driver will implement is writing a message to that console.

For using RPC, the functions that a driver provides must be the methods of a single object. We will thus define a class that provides our message-printing method: ::

    class Hello:
        def message(self, msg):
            print("message: " + msg)

To turn it into a server, we use :class:`artiq.management.pc_rpc`. Import the function we will use: ::

    from artiq.management.pc_rpc import simple_server_loop

and add a ``main`` function that is run when the program is executed: ::

    def main():
        simple_server_loop(Hello(), "::1", 7777)

    if __name__ == "__main__":
        main()

The parameters ``::1`` and 7777 are respectively the address to bind the server to (IPv6 localhost) and the TCP port to use. Then add a line: ::

    #!/usr/bin/env python3

at the beginning of the file, save it to ``hello-controller`` and set its execution permissions: ::

    $ chmod 755 hello-controller

Run it as: ::

    $ ./hello-controller

and verify that you can connect to the TCP port: ::

    $ telnet ::1 7777
    Trying ::1...
    Connected to ::1.
    Escape character is '^]'.

:tip: Use the key combination Ctrl-AltGr-9 to get the ``telnet>`` prompt, and enter ``close`` to quit Telnet. Quit the controller with Ctrl-C.

The client
----------

Controller clients are small command-line utilities that expose certain functionalities of the drivers. They are optional, and not used very often - typically for debugging and testing.

Create a ``hello-client`` file with the following contents: ::

    #!/usr/bin/env python3

    from artiq.management.pc_rpc import Client


    def main():
        remote = Client("::1", 7777)
        try:
            remote.message("Hello World!")
        finally:
            remote.close_rpc()

    if __name__ == "__main__":
        main()

Run it as before, while the controller is running. You should see the message appearing on the controller's terminal: ::

    $ ./hello-controller
    message: Hello World!

When using the driver in an experiment, for simple cases the ``Client`` instance can be returned by the :class:`artiq.language.core.AutoContext` mechanism and used normally as a device.

Command-line arguments
----------------------

Use the Python ``argparse`` module to make the bind address and port configurable on the controller, and the server address, port and message configurable on the client.

We suggest naming the controller parameters ``--bind`` and ``--port`` so that those parameters stay consistent across controller, and use ``-s/--server`` and ``--port`` on the client.

The controller's code would contain something similar to this: ::

    def _get_args():
        parser = argparse.ArgumentParser(description="Hello world controller")
        parser.add_argument("--bind", default="::1",
                            help="hostname or IP address to bind to")
        parser.add_argument("--port", default=7777, type=int,
                            help="TCP port to listen to")
        return parser.parse_args()

    def main():
        args = _get_args()
        simple_server_loop(Hello(), args.bind, args.port)
