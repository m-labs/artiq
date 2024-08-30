Management system interface
===========================

ARTIQ makes certain provisions to allow interactions between different components when using the :doc:`management system <management_system>`. An experiment may make requests of the master or clients using virtual devices to represent the necessary line of communication; applets may interact with databases, the dashboard, and directly with the user (through argument widgets). This page collects the references for these features.

In experiments
--------------

``scheduler`` virtual device
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The scheduler is exposed to the experiments via a virtual device called ``scheduler``. It can be requested like any other device, and the methods below, as well as :meth:`pause`, can be called on the returned object.

The scheduler virtual device also contains the attributes ``rid``, ``pipeline_name``, ``priority`` and ``expid``, which contain the corresponding information about the current run.

.. autoclass:: artiq.master.scheduler.Scheduler
   :members:

``ccb`` virtual device
^^^^^^^^^^^^^^^^^^^^^^

Client control broadcasts (CCBs) are requests made by experiments for clients to perform some action. Experiments do so by requesting the ``ccb`` virtual device and calling its ``issue`` method. The first argument of the issue method is the name of the broadcast, and any further positional and keyword arguments are passed to the broadcast.

CCBs are especially used by experiments to configure applets in the dashboard, for example for plotting purposes.

.. autoclass:: artiq.dashboard.applets_ccb.AppletsCCBDock
   :members:

In applets
----------

.. _applet-references:

Applet request interfaces
^^^^^^^^^^^^^^^^^^^^^^^^^

Applet request interfaces allow applets to perform actions on the master database and set arguments in the dashboard. Applets may inherit from ``artiq.applets.simple.SimpleApplet`` and call the methods defined below through the ``req`` attribute.

Embedded applets should use ``AppletRequestIPC``, while standalone applets use ``AppletRequestRPC``. ``SimpleApplet`` automatically chooses the correct interface on initialization.

.. autoclass:: artiq.applets.simple._AppletRequestInterface
   :members:

Applet entry area
^^^^^^^^^^^^^^^^^

Argument widgets can be used in applets through the :class:`~artiq.gui.applets.EntryArea` class. Below is a simple example code snippet: ::

   entry_area = EntryArea()

   # Create a new widget
   entry_area.setattr_argument("bl", BooleanValue(True))

   # Get the value of the widget (output: True)
   print(entry_area.bl)

   # Set the value
   entry_area.set_value("bl", False)

   # False
   print(entry_area.bl)

The :class:`~artiq.gui.applets.EntryArea`  object can then be added to a layout and integrated with the applet GUI. Multiple :class:`~artiq.gui.applets.EntryArea`  objects can be used in a single applet.

.. class:: artiq.gui.applets.EntryArea

   .. method:: setattr_argument(name, proc, group=None, tooltip=None)

      Sets an argument as attribute. The names of the argument and of the
      attribute are the same.

      :param name: Argument name
      :param proc: Argument processor, for example :class:`~artiq.language.environment.NumberValue`
      :param group: Used to group together arguments in the GUI under a common category
      :param tooltip: Tooltip displayed when hovering over the entry widget

   .. method:: get_value(name)

      Get the value of an entry widget.

      :param name: Argument name

   .. method:: get_values()

      Get all values in the :class:`~artiq.gui.applets.EntryArea` as a dictionary. Names are stored as keys, and argument values as values.

   .. method:: set_value(name, value)

      Set the value of an entry widget. The change is temporary and will reset to default when the reset button is clicked.

      :param name: Argument name
      :param value: Object representing the new value of the argument. For :class:`~artiq.language.scan.Scannable` arguments, this parameter
          should be a :class:`~artiq.language.scan.ScanObject`. The type of the :class:`~artiq.language.scan.ScanObject` will be set as the selected type when this function is called.

   .. method:: set_values(values)

      Set multiple values from a dictionary input. Calls :meth:`set_value` for each key-value pair.

      :param values: Dictionary with names as keys and new argument values as values.