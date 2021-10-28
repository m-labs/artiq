"""
Serialisation / deserialization functions extracted from the Dask library

Dask is a powerful parallel computing library (licensed under BSD) and, as such,
has capable serialization features. However, it's also quite a heavy dependancy
(pulling in lots of others) so this subpackage contains only the
(de)serialization code, with a few minor tweaks to decouple it from the rest of
the dask library. 

See issue #1674 for more information about this decision.
"""


from .serialize import serialize, deserialize
