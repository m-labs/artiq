from artiq.management.sync_struct import Notifier, process_mod


class RTResults:
    def __init__(self):
        self.sets = Notifier(dict())
        self.current_set = "default"

    def init(self, description):
        data = dict()
        for rtr in description.keys():
            if isinstance(rtr, tuple):
                for e in rtr:
                    data[e] = []
            else:
                data[rtr] = []
        self.sets[self.current_set] = {
            "description": description,
            "data": data
        }

    def update(self, mod):
        target = self.sets[self.current_set]["data"]
        process_mod(target, mod)
