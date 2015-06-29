"""
Connection to device, parameter and result database.
"""

__all__ = ["Device", "NoDefault", "Parameter", "Argument", "Result", "AutoDB"]


class _AttributeKind:
    pass


class Device(_AttributeKind):
    """Represents a device for ``AutoDB`` to process."""
    pass


class NoDefault:
    """Represents the absence of a default value for ``Parameter``
    and ``Argument``.
    """
    pass


class Parameter(_AttributeKind):
    """Represents a parameter (from the database) for ``AutoDB``
    to process.

    :param default: Default value of the parameter to be used if not found
        in the database.
    """
    def __init__(self, default=NoDefault):
        self.default = default


class Argument(_AttributeKind):
    """Represents an argument (specifiable at instance creation) for
    ``AutoDB`` to process.

    :param default: Default value of the argument to be used if not specified
        at instance creation.
    """
    def __init__(self, default=NoDefault):
        self.default = default


class Result(_AttributeKind):
    """Represents a result for ``AutoDB`` to process."""
    pass


class AutoDB:
    """Base class to automate device, parameter and result database access.

    Drivers and experiments should in most cases overload this class to
    obtain the parameters and devices (including the core device) that they
    need, report results, and modify parameters.

    :param dbh: database hub to use. If ``None``, all devices and parameters
        must be supplied as keyword arguments, and reporting results and
        modifying parameters is not supported.
    """
    class DBKeys:
        pass

    realtime_results = dict()

    def __init__(self, dbh=None, **kwargs):
        self.dbh = dbh

        for k, v in kwargs.items():
            object.__setattr__(self, k, v)

        for k in dir(self.DBKeys):
            if k not in self.__dict__:
                ak = getattr(self.DBKeys, k)
                if isinstance(ak, Argument):
                    if ak.default is NoDefault:
                        raise AttributeError(
                            "No value specified for argument '{}'".format(k))
                    object.__setattr__(self, k, ak.default)
                elif isinstance(ak, Device):
                    try:
                        dev = self.dbh.get_device(k)
                    except KeyError:
                        raise KeyError("Device '{}' not found".format(k))
                    object.__setattr__(self, k, dev)
        self.build()
        if self.dbh is not None and self.realtime_results:
            self.dbh.add_rt_results(self.realtime_results)

    def __getattr__(self, name):
        ak = getattr(self.DBKeys, name)
        if isinstance(ak, Parameter):
            try:
                if self.dbh is None:
                    raise KeyError
                return self.dbh.get_parameter(name)
            except KeyError:
                if ak.default is not NoDefault:
                    return ak.default
                else:
                    raise AttributeError("Parameter '{}' not in database"
                                         " and without default value"
                                         .format(name))
        elif isinstance(ak, Result):
            try:
                return self.dbh.get_result(name)
            except KeyError:
                raise AttributeError("Result '{}' not found".format(name))
        else:
            raise ValueError

    def __setattr__(self, name, value):
        try:
            ak = getattr(self.DBKeys, name)
        except AttributeError:
            object.__setattr__(self, name, value)
        else:
            if isinstance(ak, Parameter):
                self.dbh.set_parameter(name, value)
            elif isinstance(ak, Result):
                self.dbh.set_result(name, value)
            else:
                raise ValueError

    def build(self):
        """This is called by ``__init__`` after the parameter initialization
        is done.

        The user may overload this method to complete the object's
        initialization with all parameters available.
        """
        pass
