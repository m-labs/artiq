class EmbeddingMap:
    def __init__(self):
        self.object_inverse_map = {}
        self.object_map = {}
        self.string_map = {}
        self.string_reverse_map = {}
        self.function_map = {}
        self.attributes_writeback = []

        # Keep this list of exceptions in sync with `EXCEPTION_ID_LOOKUP` in `artiq::firmware::ksupport::eh_artiq`
        # The exceptions declared here must be defined in `artiq.coredevice.exceptions`
        # Verify synchronization by running the test cases in `artiq.test.coredevice.test_exceptions`
        self.preallocate_runtime_exception_names([
            "RTIOUnderflow",
            "RTIOOverflow",
            "RTIODestinationUnreachable",
            "DMAError",
            "I2CError",
            "CacheError",
            "SPIError",
            "SubkernelError",

            "0:AssertionError",
            "0:AttributeError",
            "0:IndexError",
            "0:IOError",
            "0:KeyError",
            "0:NotImplementedError",
            "0:OverflowError",
            "0:RuntimeError",
            "0:TimeoutError",
            "0:TypeError",
            "0:ValueError",
            "0:ZeroDivisionError",
            "0:LinAlgError",
            "UnwrapNoneError",
        ])

    def preallocate_runtime_exception_names(self, names):
        for i, name in enumerate(names):
            if ":" not in name:
                name = "0:artiq.coredevice.exceptions." + name
            exn_id = self.store_str(name)
            assert exn_id == i

    def store_function(self, key, fun):
        self.function_map[key] = fun
        return key

    def store_object(self, obj):
        obj_id = id(obj)
        if obj_id in self.object_inverse_map:
            return self.object_inverse_map[obj_id]
        key = len(self.object_map) + 1
        self.object_map[key] = obj
        self.object_inverse_map[obj_id] = key
        return key

    def store_str(self, s):
        if s in self.string_reverse_map:
            return self.string_reverse_map[s]
        key = len(self.string_map)
        self.string_map[key] = s
        self.string_reverse_map[s] = key
        return key

    def retrieve_function(self, key):
        return self.function_map[key]

    def retrieve_object(self, key):
        return self.object_map[key]

    def retrieve_str(self, key):
        return self.string_map[key]
