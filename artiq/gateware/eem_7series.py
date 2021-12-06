from artiq.gateware import eem
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_7series, edge_counter


def peripheral_dio(module, peripheral, **kwargs):
    ttl_classes = {
        "input": ttl_serdes_7series.InOut_8X,
        "output": ttl_serdes_7series.Output_8X
    }
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    if peripheral["edge_counter"]:
        edge_counter_cls = edge_counter.SimpleEdgeCounter
    else:
        edge_counter_cls = None
    eem.DIO.add_std(module, peripheral["ports"][0],
        ttl_classes[peripheral["bank_direction_low"]],
        ttl_classes[peripheral["bank_direction_high"]],
        edge_counter_cls=edge_counter_cls, **kwargs)


def peripheral_urukul(module, peripheral, **kwargs):
    if len(peripheral["ports"]) == 1:
        port, port_aux = peripheral["ports"][0], None
    elif len(peripheral["ports"]) == 2:
        port, port_aux = peripheral["ports"]
    else:
        raise ValueError("wrong number of ports")
    if peripheral["synchronization"]:
        sync_gen_cls = ttl_simple.ClockGen
    else:
        sync_gen_cls = None
    eem.Urukul.add_std(module, port, port_aux, ttl_serdes_7series.Output_8X,
        sync_gen_cls, **kwargs)


def peripheral_novogorny(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Novogorny.add_std(module, peripheral["ports"][0],
        ttl_serdes_7series.Output_8X, **kwargs)


def peripheral_sampler(module, peripheral, **kwargs):
    if len(peripheral["ports"]) == 1:
        port, port_aux = peripheral["ports"][0], None
    elif len(peripheral["ports"]) == 2:
        port, port_aux = peripheral["ports"]
    else:
        raise ValueError("wrong number of ports")
    eem.Sampler.add_std(module, port, port_aux, ttl_serdes_7series.Output_8X,
        **kwargs)


def peripheral_suservo(module, peripheral, **kwargs):
    if len(peripheral["sampler_ports"]) != 2:
        raise ValueError("wrong number of Sampler ports")
    urukul_ports = []
    if len(peripheral["urukul0_ports"]) != 2:
        raise ValueError("wrong number of Urukul #0 ports")
    urukul_ports.append(peripheral["urukul0_ports"])
    if "urukul1_ports" in peripheral:
        if len(peripheral["urukul1_ports"]) != 2:
            raise ValueError("wrong number of Urukul #1 ports")
        urukul_ports.append(peripheral["urukul1_ports"])
    eem.SUServo.add_std(module,
        peripheral["sampler_ports"],
        urukul_ports, **kwargs)


def peripheral_zotino(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Zotino.add_std(module, peripheral["ports"][0],
        ttl_serdes_7series.Output_8X, **kwargs)


def peripheral_grabber(module, peripheral, **kwargs):
    if len(peripheral["ports"]) == 1:
        port = peripheral["ports"][0]
        port_aux = None
        port_aux2 = None
    elif len(peripheral["ports"]) == 2:
        port, port_aux = peripheral["ports"]
        port_aux2 = None
    elif len(peripheral["ports"]) == 3:
        port, port_aux, port_aux2 = peripheral["ports"]
    else:
        raise ValueError("wrong number of ports")
    eem.Grabber.add_std(module, port, port_aux, port_aux2, **kwargs)


def peripheral_mirny(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Mirny.add_std(module, peripheral["ports"][0],
        ttl_serdes_7series.Output_8X, **kwargs)


def peripheral_fastino(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Fastino.add_std(module, peripheral["ports"][0],
        peripheral["log2_width"], **kwargs)


def peripheral_phaser(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Phaser.add_std(module, peripheral["ports"][0], **kwargs)


def peripheral_hvamp(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.HVAmp.add_std(module, peripheral["ports"][0], 
        ttl_simple.Output, **kwargs)


peripheral_processors = {
    "dio": peripheral_dio,
    "urukul": peripheral_urukul,
    "novogorny": peripheral_novogorny,
    "sampler": peripheral_sampler,
    "suservo": peripheral_suservo,
    "zotino": peripheral_zotino,
    "grabber": peripheral_grabber,
    "mirny": peripheral_mirny,
    "fastino": peripheral_fastino,
    "phaser": peripheral_phaser,
    "hvamp": peripheral_hvamp,
}


def add_peripherals(module, peripherals, **kwargs):
    for peripheral in peripherals:
        peripheral_processors[peripheral["type"]](module, peripheral, **kwargs)
