from artiq.management.sync_struct import Notifier, process_mod


class RTResults:
    def __init__(self):
        self.groups = Notifier(dict())
        self.current_group = "default"

    def init(self, description):
        data = dict()
        for rtr in description.keys():
            if isinstance(rtr, tuple):
                for e in rtr:
                    data[e] = []
            else:
                data[rtr] = []
        self.groups[self.current_group] = {
            "description": description,
            "data": data
        }

    def update(self, mod):
        target = self.groups[self.current_group]["data"]
        process_mod(target, mod)
