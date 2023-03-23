"""
Draft prototype of custom example EEM module
"""

from artiq.gateware.eem import _EEM, default_iostandard
from artiq.frontend.artiq_ddb_template import PeripheralManager
from artiq.language import kernel


# to be added to the artiq/gateware/eem.py
class Example(_EEM):
    @classmethod
    def add_std(cls, target, eem, iostandard=default_iostandard):
        cls.add_extension(target, eem, iostandard=iostandard)

    @staticmethod
    def io(eem, iostandard):
        return [((iostandard(eem),),)]


# to be added to the artiq/gateware/eem_7series.py
def peripheral_example(module, peripheral, **kwargs):
    Example.add_std(module, peripheral, **kwargs)


# to be added to the artiq/gateware/eem_7series.py/peripheral_processors dictionary
peripheral_processors = {
    "example": peripheral_example
}

# to be appended to the artiq/coredevice/coredevice_generic.schema.json/definitions/peripheral/allOf array
device_schema = """
{
    "title": "Example",
    "if": {
        "properties": {
            "type": {
                "const": "example"
            }
        }
    },
    "then": {
        "properties": {
            "ports": {
                "type": "array",
                "items": {
                    "type": "integer"
                },
                "minItems": 1,
                "maxItems": 3
            }, 
            "arg1": {
                "type": "string"
            }
        },
        "required": ["ports"]
    }
}
"""


# similar to artiq/coredevice/* devices
class ExampleDevice:
    kernel_invariants = {"core", "channel", "arg1"}

    def __init__(self, dmgr, channel, arg1, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.arg1 = arg1

    @staticmethod
    def get_rtio_channels(channel, **kwargs):
        return [(channel, None)]

    @kernel
    def test(self):
        pass


# this is to be loaded by the artiq_ddb_template
def process_example(self: PeripheralManager, rtio_offset, peripheral):
    self.gen("""
            device_db["{name}"] = {{
                "type": "local",
                "module": "modules.example",
                "class": "ExampleCore",
                "arguments": {{ "arg1": "{arg1}", "channel": 0x{channel:06x} }}
            }}""",
             name=self.get_name("example"),
             channel=rtio_offset,
             arg1=peripheral["arg1"])
    return 1
