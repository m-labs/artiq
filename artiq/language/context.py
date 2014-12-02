"""
Device and parameter attributes.

"""

class _AttributeKind:
    pass


class Device(_AttributeKind):
    """Represents a device for ``AutoContext`` to process.

    :param type_hint: An optional string giving a hint about the type of the
        device.

    """
    def __init__(self, type_hint=None):
        self.type_hint = type_hint


class NoDefault:
    """Represents the absence of a default value for ``Parameter``.

    """
    pass


class Parameter(_AttributeKind):
    """Represents a parameter for ``AutoContext`` to process.

    :param default: Default value of the parameter to be used if not found
        in database.

    """
    def __init__(self, default=NoDefault):
        self.default = default


class AutoContext:
    """Base class to automate device and parameter discovery.

    Drivers and experiments should in most cases overload this class to
    obtain the parameters and devices (including the core device) that they
    need.

    This class sets all its ``__init__`` keyword arguments as attributes. It
    then iterates over each element in the attribute dictionary of the class,
    and when they are abtract attributes (e.g. ``Device``, ``Parameter``),
    requests them from the ``mvs`` (Missing Value Supplier) object.

    A ``AutoContext`` instance can be used as MVS. If the requested parameter
    is within its attributes, the value of that attribute is returned.
    Otherwise, the request is forwarded to the parent MVS.

    All keyword arguments are set as object attributes. This enables setting
    parameters of a lower-level ``AutoContext`` object using keyword arguments
    without having those explicitly listed in the upper-level ``AutoContext``
    parameter list.

    At the top-level, it is possible to have a MVS that issues requests to a
    database and hardware management system.

    :var implicit_core: Automatically adds a ``core`` device to the attributes.
        Default: True.

    Example:

    >>> class SubExperiment(AutoContext):
    ...     foo = Parameter()
    ...     bar = Parameter()
    ...
    ...     def run(self):
    ...         do_something(self.foo, self.bar)
    ...
    >>> class MainExperiment(AutoContext):
    ...     bar1 = Parameter()
    ...     bar2 = Parameter()
    ...     offset = Parameter()
    ...
    ...     def build(self):
    ...         self.exp1 = SubExperiment(self, bar=self.bar1)
    ...         self.exp2 = SubExperiment(self, bar=self.bar2)
    ...         self.exp3 = SubExperiment(self, bar=self.bar2 + self.offset)
    ...
    ...     def run(self):
    ...         self.exp1.run()
    ...         self.exp2.run()
    ...         self.exp3.run()
    ...
    >>> # does not require a database.
    >>> a = MainExperiment(foo=1, bar1=2, bar2=3, offset=0)
    >>> # "foo" and "offset" are automatically retrieved from the database.
    >>> b = MainExperiment(db_mvs, bar1=2, bar2=3)

    """
    implicit_core = True

    def __init__(self, mvs=None, **kwargs):
        if self.implicit_core:
            if hasattr(self, "core"):
                raise ValueError(
                    "Set implicit_core to False when"
                    " core is explicitly specified")
            self.core = Device("core")

        self.mvs = mvs
        for k, v in kwargs.items():
            setattr(self, k, v)

        for k in dir(self):
            v = getattr(self, k)
            if isinstance(v, _AttributeKind):
                value = self.mvs.get_missing_value(k, v)
                setattr(self, k, value)

        self.build()

    def get_missing_value(self, name, kind):
        """Attempts to retrieve ``parameter`` from the object's attributes.
        If not present, forwards the request to the parent MVS.

        The presence of this method makes ``AutoContext`` act as a MVS.

        """
        try:
            return getattr(self, name)
        except AttributeError:
            return self.mvs.get_missing_value(name, kind)

    def build(self):
        """This is called by ``__init__`` after the parameter initialization
        is done.

        The user may overload this method to complete the object's
        initialization with all parameters available.

        """
        pass
