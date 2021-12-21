#!/usr/bin/env python3

import argparse
import logging
from distutils.version import LooseVersion

from misoc.integration.builder import builder_args, builder_argdict
from misoc.targets.kasli import soc_kasli_args, soc_kasli_argdict

from artiq import __version__ as artiq_version
from artiq.coredevice import jsondesc
from artiq.gateware import rtio, eem_7series
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.targets.kasli import StandaloneBase, MasterBase, SatelliteBase
from artiq.build_soc import *

logger = logging.getLogger(__name__)

class GenericStandalone(StandaloneBase):
    def __init__(self, description, hw_rev=None,**kwargs):
        if hw_rev is None:
            hw_rev = description["hw_rev"]
        self.class_name_override = description["variant"]
        StandaloneBase.__init__(self, hw_rev=hw_rev, **kwargs)

        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["RTIO_FREQUENCY"] = "{:.1f}".format(description["rtio_frequency"]/1e6)
        if "ext_ref_frequency" in description:
            self.config["SI5324_EXT_REF"] = None
            self.config["EXT_REF_FREQUENCY"] = "{:.1f}".format(
                description["ext_ref_frequency"]/1e6)
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)

        has_grabber = any(peripheral["type"] == "grabber" for peripheral in description["peripherals"])
        if has_grabber:
            self.grabber_csr_group = []

        self.rtio_channels = []
        eem_7series.add_peripherals(self, description["peripherals"])
        if hw_rev in ("v1.0", "v1.1"):
            for i in (1, 2):
                print("SFP LED at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
                sfp_ctl = self.platform.request("sfp_ctl", i)
                phy = ttl_simple.Output(sfp_ctl.led)
                self.submodules += phy
                self.rtio_channels.append(rtio.Channel.from_phy(phy))
        if hw_rev == "v2.0":
            for i in (1, 2):
                print("USER LED at RTIO channel 0x{:06x}".format(len(self.rtio_channels)))
                phy = ttl_simple.Output(self.platform.request("user_led", i))
                self.submodules += phy
                self.rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        self.add_rtio(self.rtio_channels, sed_lanes=description["sed_lanes"])

        if has_grabber:
            self.config["HAS_GRABBER"] = None
            self.add_csr_group("grabber", self.grabber_csr_group)
            for grabber in self.grabber_csr_group:
                self.platform.add_false_path_constraints(
                    self.rtio_crg.cd_rtio.clk, getattr(self, grabber).deserializer.cd_cl.clk)


class GenericMaster(MasterBase):
    def __init__(self, description, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = description["hw_rev"]
        self.class_name_override = description["variant"]
        MasterBase.__init__(self,
            hw_rev=hw_rev,
            rtio_clk_freq=description["rtio_frequency"],
            enable_sata=description["enable_sata_drtio"],
            **kwargs)
        if "ext_ref_frequency" in description:
            self.config["SI5324_EXT_REF"] = None
            self.config["EXT_REF_FREQUENCY"] = "{:.1f}".format(
                description["ext_ref_frequency"]/1e6)
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)

        has_grabber = any(peripheral["type"] == "grabber" for peripheral in description["peripherals"])
        if has_grabber:
            self.grabber_csr_group = []

        self.rtio_channels = []
        eem_7series.add_peripherals(self, description["peripherals"])
        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        self.add_rtio(self.rtio_channels, sed_lanes=description["sed_lanes"])
        if has_grabber:
            self.config["HAS_GRABBER"] = None
            self.add_csr_group("grabber", self.grabber_csr_group)
            for grabber in self.grabber_csr_group:
                self.platform.add_false_path_constraints(
                    self.drtio_transceiver.gtps[0].txoutclk, getattr(self, grabber).deserializer.cd_cl.clk)


class GenericSatellite(SatelliteBase):
    def __init__(self, description, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = description["hw_rev"]
        self.class_name_override = description["variant"]
        SatelliteBase.__init__(self,
                               hw_rev=hw_rev,
                               rtio_clk_freq=description["rtio_frequency"],
                               enable_sata=description["enable_sata_drtio"],
                               **kwargs)
        if hw_rev == "v1.0":
            # EEM clock fan-out from Si5324, not MMCX
            self.comb += self.platform.request("clk_sel").eq(1)

        has_grabber = any(peripheral["type"] == "grabber" for peripheral in description["peripherals"])
        if has_grabber:
            self.grabber_csr_group = []

        self.rtio_channels = []
        eem_7series.add_peripherals(self, description["peripherals"])
        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(self.rtio_channels)
        self.rtio_channels.append(rtio.LogChannel())

        self.add_rtio(self.rtio_channels, sed_lanes=description["sed_lanes"])
        if has_grabber:
            self.config["HAS_GRABBER"] = None
            self.add_csr_group("grabber", self.grabber_csr_group)
            for grabber in self.grabber_csr_group:
                self.platform.add_false_path_constraints(
                    self.drtio_transceiver.gtps[0].txoutclk, getattr(self, grabber).deserializer.cd_cl.clk)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for generic Kasli systems")
    builder_args(parser)
    soc_kasli_args(parser)
    parser.set_defaults(output_dir="artiq_kasli")
    parser.add_argument("description", metavar="DESCRIPTION",
                        help="JSON system description file")
    parser.add_argument("--gateware-identifier-str", default=None,
                        help="Override ROM identifier")
    args = parser.parse_args()
    description = jsondesc.load(args.description)

    min_artiq_version = description.get("min_artiq_version", "0")
    if LooseVersion(artiq_version) < LooseVersion(min_artiq_version):
        logger.warning("ARTIQ version mismatch: current %s < %s minimum",
                       artiq_version, min_artiq_version)

    if description["target"] != "kasli":
        raise ValueError("Description is for a different target")

    if description["base"] == "standalone":
        cls = GenericStandalone
    elif description["base"] == "master":
        cls = GenericMaster
    elif description["base"] == "satellite":
        cls = GenericSatellite
    else:
        raise ValueError("Invalid base")

    soc = cls(description, gateware_identifier_str=args.gateware_identifier_str, **soc_kasli_argdict(args))
    args.variant = description["variant"]
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
