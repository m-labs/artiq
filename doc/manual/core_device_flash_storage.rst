.. _core-device-flash-storage:

Core device flash storage
=========================

The core device contains some flash space that can be used to store
some configuration data.

This storage area is used to store the core device MAC address, IP address and even the idle kernel.

The flash storage area is one sector (64 kB) large and is organized as a list
of key-value records.

This flash storage space can be accessed by using the artiq_coreconfig.py :ref:`core-device-configuration-tool`.
