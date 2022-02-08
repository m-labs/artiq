#!/usr/bin/env python3

import argparse
import inspect
import os
import select
import sys

from artiq.experiment import *
from artiq.coredevice.ad9910 import AD9910, SyncDataEeprom
from artiq.master.databases import DeviceDB
from artiq.master.worker_db import DeviceManager


if os.name == "nt":
    import msvcrt


def chunker(seq, size):
    res = []
    for el in seq:
        res.append(el)
        if len(res) == size:
            yield res
            res = []
    if res:
        yield res


def is_enter_pressed() -> TBool:
    if os.name == "nt":
        if msvcrt.kbhit() and msvcrt.getch() == b"\r":
            return True
        else:
            return False
    else:
        if select.select([sys.stdin, ], [], [], 0.0)[0]:
            sys.stdin.read(1)
            return True
        else:
            return False


class SinaraTester(EnvExperiment):
    def build(self):
        self.setattr_device("core")

        self.leds = dict()
        self.ttl_outs = dict()
        self.ttl_ins = dict()
        self.urukul_cplds = dict()
        self.urukuls = dict()
        self.samplers = dict()
        self.zotinos = dict()
        self.fastinos = dict()
        self.phasers = dict()
        self.grabbers = dict()
        self.mirny_cplds = dict()
        self.mirnies = dict()
        self.suservos = dict()
        self.suschannels = dict()
        self.almaznys = dict()

        ddb = self.get_device_db()
        for name, desc in ddb.items():
            if isinstance(desc, dict) and desc["type"] == "local":
                module, cls = desc["module"], desc["class"]
                if (module, cls) == ("artiq.coredevice.ttl", "TTLOut"):
                    dev = self.get_device(name)
                    if "led" in name:  # guess
                        self.leds[name] = dev
                    else:
                        self.ttl_outs[name] = dev
                elif (module, cls) == ("artiq.coredevice.ttl", "TTLInOut"):
                    self.ttl_ins[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.urukul", "CPLD"):
                    self.urukul_cplds[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.ad9910", "AD9910"):
                    self.urukuls[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.ad9912", "AD9912"):
                    self.urukuls[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.sampler", "Sampler"):
                    self.samplers[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.zotino", "Zotino"):
                    self.zotinos[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.fastino", "Fastino"):
                    self.fastinos[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.phaser", "Phaser"):
                    self.phasers[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.grabber", "Grabber"):
                    self.grabbers[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.mirny", "Mirny"):
                    self.mirny_cplds[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.adf5356", "ADF5356"):
                    self.mirnies[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.suservo", "SUServo"):
                    self.suservos[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.suservo", "Channel"):
                    self.suschannels[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.mirny", "Almazny"):
                    self.almaznys[name] = self.get_device(name)

        # Remove Urukul, Sampler, Zotino and Mirny control signals
        # from TTL outs (tested separately) and remove Urukuls covered by
        # SUServo
        ddb = self.get_device_db()
        for name, desc in ddb.items():
            if isinstance(desc, dict) and desc["type"] == "local":
                module, cls = desc["module"], desc["class"]
                if ((module, cls) == ("artiq.coredevice.ad9910", "AD9910")
                    or (module, cls) == ("artiq.coredevice.ad9912", "AD9912")):
                    if "sw_device" in desc["arguments"]:
                        sw_device = desc["arguments"]["sw_device"]
                        del self.ttl_outs[sw_device]
                elif (module, cls) == ("artiq.coredevice.urukul", "CPLD"):
                    if "io_update_device" in desc["arguments"]:
                        io_update_device = desc["arguments"]["io_update_device"]
                        del self.ttl_outs[io_update_device]
                # check for suservos and delete respective urukuls
                elif (module, cls) == ("artiq.coredevice.suservo", "SUServo"):
                    for cpld in desc["arguments"]["cpld_devices"]:
                        del self.urukul_cplds[cpld]
                    for dds in desc["arguments"]["dds_devices"]:
                        del self.urukuls[dds]
                elif (module, cls) == ("artiq.coredevice.sampler", "Sampler"):
                    cnv_device = desc["arguments"]["cnv_device"]
                    del self.ttl_outs[cnv_device]
                elif (module, cls) == ("artiq.coredevice.zotino", "Zotino"):
                    ldac_device = desc["arguments"]["ldac_device"]
                    clr_device = desc["arguments"]["clr_device"]
                    del self.ttl_outs[ldac_device]
                    del self.ttl_outs[clr_device]
                elif (module, cls) == ("artiq.coredevice.adf5356", "ADF5356"):
                    sw_device = desc["arguments"]["sw_device"]
                    del self.ttl_outs[sw_device]

        # Sort everything by RTIO channel number
        self.leds = sorted(self.leds.items(), key=lambda x: x[1].channel)
        self.ttl_outs = sorted(self.ttl_outs.items(), key=lambda x: x[1].channel)
        self.ttl_ins = sorted(self.ttl_ins.items(), key=lambda x: x[1].channel)
        self.urukuls = sorted(self.urukuls.items(), key=lambda x: (x[1].cpld.bus.channel, x[1].chip_select))
        self.samplers = sorted(self.samplers.items(), key=lambda x: x[1].cnv.channel)
        self.zotinos = sorted(self.zotinos.items(), key=lambda x: x[1].bus.channel)
        self.fastinos = sorted(self.fastinos.items(), key=lambda x: x[1].channel)
        self.phasers = sorted(self.phasers.items(), key=lambda x: x[1].channel_base)
        self.grabbers = sorted(self.grabbers.items(), key=lambda x: x[1].channel_base)
        self.mirnies = sorted(self.mirnies.items(), key=lambda x: (x[1].cpld.bus.channel, x[1].channel))
        self.suservos = sorted(self.suservos.items(), key=lambda x: x[1].channel)
        self.suschannels = sorted(self.suschannels.items(), key=lambda x: x[1].channel)

    @kernel
    def test_led(self, led):
        while not is_enter_pressed():
            self.core.break_realtime()
            # do not fill the FIFOs too much to avoid long response times
            t = now_mu() - self.core.seconds_to_mu(0.2)
            while self.core.get_rtio_counter_mu() < t:
                pass
            for i in range(3):
                led.pulse(100*ms)
                delay(100*ms)

    def test_leds(self):
        print("*** Testing LEDs.")
        print("Check for blinking. Press ENTER when done.")

        for led_name, led_dev in self.leds:
            print("Testing LED: {}".format(led_name))
            self.test_led(led_dev)

    @kernel
    def test_ttl_out_chunk(self, ttl_chunk):
        while not is_enter_pressed():
            self.core.break_realtime()
            for _ in range(50000):
                i = 0
                for ttl in ttl_chunk:
                    i += 1
                    for _ in range(i):
                        ttl.pulse(1*us)
                        delay(1*us)
                    delay(10*us)

    def test_ttl_outs(self):
        print("*** Testing TTL outputs.")
        print("Outputs are tested in groups of 4. Touch each TTL connector")
        print("with the oscilloscope probe tip, and check that the number of")
        print("pulses corresponds to its number in the group.")
        print("Press ENTER when done.")

        for ttl_chunk in chunker(self.ttl_outs, 4):
            print("Testing TTL outputs: {}.".format(", ".join(name for name, dev in ttl_chunk)))
            self.test_ttl_out_chunk([dev for name, dev in ttl_chunk])

    @kernel
    def test_ttl_in(self, ttl_out, ttl_in):
        n = 42
        self.core.break_realtime()
        with parallel:
            ttl_in.gate_rising(1*ms)
            with sequential:
                delay(50*us)
                for _ in range(n):
                    ttl_out.pulse(2*us)
                    delay(2*us)
        return ttl_in.count(now_mu()) == n

    def test_ttl_ins(self):
        print("*** Testing TTL inputs.")
        if not self.ttl_outs:
            print("No TTL output channel available to use as stimulus.")
            return
        default_ttl_out_name, default_ttl_out_dev = next(iter(self.ttl_outs))
        ttl_out_name = input("TTL device to use as stimulus (default: {}): ".format(default_ttl_out_name))
        if ttl_out_name:
            ttl_out_dev = self.get_device(ttl_out_name)
        else:
            ttl_out_name = default_ttl_out_name
            ttl_out_dev = default_ttl_out_dev
        for ttl_in_name, ttl_in_dev in self.ttl_ins:
            print("Connect {} to {}. Press ENTER when done."
                  .format(ttl_out_name, ttl_in_name))
            input()
            if self.test_ttl_in(ttl_out_dev, ttl_in_dev):
                print("PASSED")
            else:
                print("FAILED")

    @kernel
    def init_urukul(self, cpld):
        self.core.break_realtime()
        cpld.init()

    @kernel
    def test_urukul_att(self, cpld):
        self.core.break_realtime()
        for i in range(32):
            test_word = 1 << i
            cpld.set_all_att_mu(test_word)
            readback_word = cpld.get_att_mu()
            if readback_word != test_word:
                print(readback_word, test_word)
                raise ValueError

    @kernel
    def calibrate_urukul(self, channel):
        self.core.break_realtime()
        channel.init()
        self.core.break_realtime()
        sync_delay_seed, _ = channel.tune_sync_delay()
        self.core.break_realtime()
        io_update_delay = channel.tune_io_update_delay()
        return sync_delay_seed, io_update_delay

    @kernel
    def setup_urukul(self, channel, frequency):
        self.core.break_realtime()
        channel.init()
        channel.set(frequency*MHz)
        channel.cfg_sw(True)
        channel.set_att(6.)

    @kernel
    def cfg_sw_off_urukul(self, channel):
        self.core.break_realtime()
        channel.cfg_sw(False)

    @kernel
    def rf_switch_wave(self, channels):
        while not is_enter_pressed():
            self.core.break_realtime()
            # do not fill the FIFOs too much to avoid long response times
            t = now_mu() - self.core.seconds_to_mu(0.2)
            while self.core.get_rtio_counter_mu() < t:
                pass
            for channel in channels:
                channel.pulse(100*ms)
                delay(100*ms)

    # We assume that RTIO channels for switches are grouped by card.
    def test_urukuls(self):
        print("*** Testing Urukul DDSes.")

        for name, cpld in sorted(self.urukul_cplds.items(), key=lambda x: x[0]):
            print(name + ": initializing CPLD...")
            self.init_urukul(cpld)
            print(name + ": testing attenuator digital control...")
            self.test_urukul_att(cpld)
            print(name + ": done")

        print("Calibrating inter-device synchronization...")
        for channel_name, channel_dev in self.urukuls:
            if (not isinstance(channel_dev, AD9910) or
                    not isinstance(channel_dev.sync_data, SyncDataEeprom)):
                print("{}\tno EEPROM synchronization".format(channel_name))
            else:
                eeprom = channel_dev.sync_data.eeprom_device
                offset = channel_dev.sync_data.eeprom_offset
                sync_delay_seed, io_update_delay = self.calibrate_urukul(channel_dev)
                print("{}\t{} {}".format(channel_name, sync_delay_seed, io_update_delay))
                eeprom_word = (sync_delay_seed << 24) | (io_update_delay << 16)
                eeprom.write_i32(offset, eeprom_word)
        print("...done")

        print("All urukul channels active.")
        print("Check each channel amplitude (~1.6Vpp/8dbm at 50ohm) and frequency.")
        print("Frequencies:")
        for card_n, channels in enumerate(chunker(self.urukuls, 4)):
            for channel_n, (channel_name, channel_dev) in enumerate(channels):
                frequency = 10*(card_n + 1) + channel_n
                print("{}\t{}MHz".format(channel_name, frequency))
                self.setup_urukul(channel_dev, frequency)
        print("Press ENTER when done.")
        input()

        sw = [channel_dev for channel_name, channel_dev in self.urukuls if hasattr(channel_dev, "sw")]
        if sw:
            print("Testing RF switch control. Check LEDs at urukul RF ports.")
            print("Press ENTER when done.")
            for swi in sw:
                self.cfg_sw_off_urukul(swi)
            self.rf_switch_wave([swi.sw for swi in sw])

    @kernel
    def init_mirny(self, cpld):
        self.core.break_realtime()
        cpld.init()

    @kernel
    def setup_mirny(self, channel, frequency):
        self.core.break_realtime()
        channel.init()

        channel.set_att(11.5*dB)
        channel.sw.on()
        self.core.break_realtime()

        channel.set_frequency(frequency*MHz)
        delay(5*ms)

    @kernel
    def sw_off_mirny(self, channel):
        self.core.break_realtime()
        channel.sw.off()

    @kernel
    def mirny_rf_switch_wave(self, channels):
        while not is_enter_pressed():
            self.core.break_realtime()
            # do not fill the FIFOs too much to avoid long response times
            t = now_mu() - self.core.seconds_to_mu(0.2)
            while self.core.get_rtio_counter_mu() < t:
                pass
            for channel in channels:
                channel.pulse(100*ms)
                delay(100*ms)
    @kernel
    def init_almazny(self, almazny):
        self.core.break_realtime()
        almazny.init()
        almazny.output_toggle(True)

    @kernel
    def almazny_set_attenuators_mu(self, almazny, ch, atts):
        self.core.break_realtime()
        almazny.set_att_mu(ch, atts)

    @kernel
    def almazny_set_attenuators(self, almazny, ch, atts):
        self.core.break_realtime()
        almazny.set_att(ch, atts)
    
    @kernel
    def almazny_toggle_output(self, almazny, rf_on):
        self.core.break_realtime()
        almazny.output_toggle(rf_on)

    def test_almaznys(self):
        print("*** Testing Almaznys.")
        for name, almazny in sorted(self.almaznys.items(), key=lambda x: x[0]):
            print(name + "...")
            print("Initializing Mirny CPLDs...")
            for name, cpld in sorted(self.mirny_cplds.items(), key=lambda x: x[0]):
                print(name + "...")
                self.init_mirny(cpld)
            print("...done")

            print("Testing attenuators. Frequencies:")
            for card_n, channels in enumerate(chunker(self.mirnies, 4)):
                for channel_n, (channel_name, channel_dev) in enumerate(channels):
                    frequency = 2000 + card_n * 250 + channel_n * 50
                    print("{}\t{}MHz".format(channel_name, frequency*2))
                    self.setup_mirny(channel_dev, frequency)
                    print("{} info: {}".format(channel_name, channel_dev.info()))
            self.init_almazny(almazny)
            print("RF ON, all attenuators ON. Press ENTER when done.")
            for i in range(4):
                self.almazny_set_attenuators_mu(almazny, i, 63)
            input()
            print("RF ON, half power attenuators ON. Press ENTER when done.")
            for i in range(4):
                self.almazny_set_attenuators(almazny, i, 15.5)
            input()
            print("RF ON, all attenuators OFF. Press ENTER when done.")
            for i in range(4):
                self.almazny_set_attenuators(almazny, i, 0)
            input()
            print("SR outputs are OFF. Press ENTER when done.")
            self.almazny_toggle_output(almazny, False)
            input()
            print("RF ON, all attenuators are ON. Press ENTER when done.")
            for i in range(4):
                self.almazny_set_attenuators(almazny, i, 31.5)
            self.almazny_toggle_output(almazny, True)
            input()
            print("RF OFF. Press ENTER when done.")
            self.almazny_toggle_output(almazny, False)
            input()

    def test_mirnies(self):
        print("*** Testing Mirny PLLs.")

        print("Initializing CPLDs...")
        for name, cpld in sorted(self.mirny_cplds.items(), key=lambda x: x[0]):
            print(name + "...")
            self.init_mirny(cpld)
        print("...done")

        print("All mirny channels active.")
        print("Frequencies:")
        for card_n, channels in enumerate(chunker(self.mirnies, 4)):
            for channel_n, (channel_name, channel_dev) in enumerate(channels):
                frequency = 1000*(card_n + 1) + channel_n * 100
                print("{}\t{}MHz".format(channel_name, frequency))
                self.setup_mirny(channel_dev, frequency)
                print("{} info: {}".format(channel_name, channel_dev.info()))
        print("Press ENTER when done.")
        input()

        sw = [channel_dev for channel_name, channel_dev in self.mirnies if hasattr(channel_dev, "sw")]
        if sw:
            print("Testing RF switch control. Check LEDs at mirny RF ports.")
            print("Press ENTER when done.")
            for swi in sw:
                self.sw_off_mirny(swi)
            self.mirny_rf_switch_wave([swi.sw for swi in sw])

    @kernel
    def get_sampler_voltages(self, sampler, cb):
        self.core.break_realtime()
        sampler.init()
        delay(5*ms)
        for i in range(8):
            sampler.set_gain_mu(i, 0)
            delay(100*us)
        smp = [0.0]*8
        sampler.sample(smp)
        cb(smp)

    def test_samplers(self):
        print("*** Testing Sampler ADCs.")
        for card_name, card_dev in self.samplers:
            print("Testing: ", card_name)

            for channel in range(8):
                print("Apply 1.5V to channel {}. Press ENTER when done.".format(channel))
                input()

                voltages = []
                def setv(x):
                    nonlocal voltages
                    voltages = x
                self.get_sampler_voltages(card_dev, setv)

                passed = True
                for n, voltage in enumerate(voltages):
                    if n == channel:
                        if abs(voltage - 1.5) > 0.2:
                            passed = False
                    else:
                        if abs(voltage) > 0.2:
                            passed = False
                if passed:
                    print("PASSED")
                else:
                    print("FAILED")
                    print(" ".join(["{:.1f}".format(x) for x in voltages]))

    @kernel
    def set_zotino_voltages(self, zotino, voltages):
        self.core.break_realtime()
        zotino.init()
        delay(200*us)
        i = 0
        for voltage in voltages:
            zotino.write_dac(i, voltage)
            delay(100*us)
            i += 1
        zotino.load()

    @kernel
    def zotinos_led_wave(self, zotinos):
        while not is_enter_pressed():
            self.core.break_realtime()
            # do not fill the FIFOs too much to avoid long response times
            t = now_mu() - self.core.seconds_to_mu(0.2)
            while self.core.get_rtio_counter_mu() < t:
                pass
            for zotino in zotinos:
                for i in range(8):
                    zotino.set_leds(1 << i)
                    delay(100*ms)
                zotino.set_leds(0)
                delay(100*ms)

    def test_zotinos(self):
        print("*** Testing Zotino DACs and USER LEDs.")
        print("Voltages:")
        for card_n, (card_name, card_dev) in enumerate(self.zotinos):
            voltages = [(-1)**i*(2.*card_n + .1*(i//2 + 1)) for i in range(32)]
            print(card_name, " ".join(["{:.1f}".format(x) for x in voltages]))
            self.set_zotino_voltages(card_dev, voltages)
        print("Press ENTER when done.")
        # Test switching on/off USR_LEDs at the same time
        self.zotinos_led_wave(
            [card_dev for _, (__, card_dev) in enumerate(self.zotinos)]
        )

    @kernel
    def set_fastino_voltages(self, fastino, voltages):
        self.core.break_realtime()
        fastino.init()
        delay(200*us)
        i = 0
        for voltage in voltages:
            fastino.set_dac(i, voltage)
            delay(100*us)
            i += 1

    @kernel
    def fastinos_led_wave(self, fastinos):
        while not is_enter_pressed():
            self.core.break_realtime()
            # do not fill the FIFOs too much to avoid long response times
            t = now_mu() - self.core.seconds_to_mu(0.2)
            while self.core.get_rtio_counter_mu() < t:
                pass
            for fastino in fastinos:
                for i in range(8):
                    fastino.set_leds(1 << i)
                    delay(100*ms)
                fastino.set_leds(0)
                delay(100*ms)

    def test_fastinos(self):
        print("*** Testing Fastino DACs and USER LEDs.")
        print("Voltages:")
        for card_n, (card_name, card_dev) in enumerate(self.fastinos):
            voltages = [(-1)**i*(2.*card_n + .1*(i//2 + 1)) for i in range(32)]
            print(card_name, " ".join(["{:.1f}".format(x) for x in voltages]))
            self.set_fastino_voltages(card_dev, voltages)
        print("Press ENTER when done.")
        # Test switching on/off USR_LEDs at the same time
        self.fastinos_led_wave(
            [card_dev for _, (__, card_dev) in enumerate(self.fastinos)]
        )

    @kernel
    def set_phaser_frequencies(self, phaser, duc, osc):
        self.core.break_realtime()
        phaser.init()
        delay(1*ms)
        phaser.channel[0].set_duc_frequency(duc)
        phaser.channel[0].set_duc_cfg()
        phaser.channel[0].set_att(6*dB)
        phaser.channel[1].set_duc_frequency(-duc)
        phaser.channel[1].set_duc_cfg()
        phaser.channel[1].set_att(6*dB)
        phaser.duc_stb()
        delay(1*ms)
        for i in range(len(osc)):
            phaser.channel[0].oscillator[i].set_frequency(osc[i])
            phaser.channel[0].oscillator[i].set_amplitude_phase(.2)
            phaser.channel[1].oscillator[i].set_frequency(-osc[i])
            phaser.channel[1].oscillator[i].set_amplitude_phase(.2)
            delay(1*ms)

    @kernel
    def phaser_led_wave(self, phasers):
        while not is_enter_pressed():
            self.core.break_realtime()
            # do not fill the FIFOs too much to avoid long response times
            t = now_mu() - self.core.seconds_to_mu(.2)
            while self.core.get_rtio_counter_mu() < t:
                pass
            for phaser in phasers:
                for i in range(6):
                    phaser.set_leds(1 << i)
                    delay(100*ms)
                phaser.set_leds(0)
                delay(100*ms)

    def test_phasers(self):
        print("*** Testing Phaser DACs and 6 USER LEDs.")
        print("Frequencies:")
        for card_n, (card_name, card_dev) in enumerate(self.phasers):
            duc = (card_n + 1)*10*MHz
            osc = [i*1*MHz for i in range(5)]
            print(card_name,
                  " ".join(["{:.0f}+{:.0f}".format(duc/MHz, f/MHz) for f in osc]),
                  "MHz")
            self.set_phaser_frequencies(card_dev, duc, osc)
        print("Press ENTER when done.")
        # Test switching on/off USR_LEDs at the same time
        self.phaser_led_wave(
            [card_dev for _, (__, card_dev) in enumerate(self.phasers)]
        )

    @kernel
    def grabber_capture(self, card_dev, rois):
        self.core.break_realtime()
        delay(100*us)
        mask = 0
        for i in range(len(rois)):
            i = rois[i][0]
            x0 = rois[i][1]
            y0 = rois[i][2]
            x1 = rois[i][3]
            y1 = rois[i][4]
            mask |= 1 << i
            card_dev.setup_roi(i, x0, y0, x1, y1)
        card_dev.gate_roi(mask)
        n = [0]*len(rois)
        card_dev.input_mu(n)
        self.core.break_realtime()
        card_dev.gate_roi(0)
        print("ROI sums:", n)

    def test_grabbers(self):
        print("*** Testing Grabber Frame Grabbers.")
        print("Activate the camera's frame grabber output, type 'g', press "
              "ENTER, and trigger the camera.")
        print("Just press ENTER to skip the test.")
        if input().strip().lower() != "g":
            print("skipping...")
            return
        rois = [[0, 0, 0, 2, 2], [1, 0, 0, 2048, 2048]]
        print("ROIs:", rois)
        for card_n, (card_name, card_dev) in enumerate(self.grabbers):
            print(card_name)
            self.grabber_capture(card_dev, rois)

    @kernel
    def setup_suservo(self, channel):
        self.core.break_realtime()
        channel.init()
        delay(1*us)
        # ADC PGIA gain 0
        for i in range(8):
            channel.set_pgia_mu(i, 0)
            delay(10*us)
        # DDS attenuator 10dB
        for i in range(4):
            for cpld in channel.cplds:
                cpld.set_att(i, 10.)
        delay(1*us)
        # Servo is done and disabled
        assert channel.get_status() & 0xff == 2
        delay(10*us)

    @kernel
    def setup_suservo_loop(self, channel, loop_nr):
        self.core.break_realtime()
        channel.set_y(
            profile=loop_nr,
            y=0.  # clear integrator
        )
        channel.set_iir(
            profile=loop_nr,
            adc=loop_nr,  # take data from Sampler channel
            kp=-1.,       # -1 P gain
            ki=0./s,      # no integrator gain
            g=0.,         # no integrator gain limit
            delay=0.      # no IIR update delay after enabling
        )
        # setpoint 0.5 (5 V with above PGIA gain setting)
        delay(100*us)
        channel.set_dds(
            profile=loop_nr,
            offset=-.3,  # 3 V with above PGIA settings
            frequency=10*MHz,
            phase=0.)
        # enable RF, IIR updates and set profile
        delay(10*us)
        channel.set(en_out=1, en_iir=1, profile=loop_nr)

    @kernel
    def setup_start_suservo(self, channel):
        self.core.break_realtime()
        channel.set_config(enable=1)
        delay(10*us)
        # check servo enabled
        assert channel.get_status() & 0x01 == 1
        delay(10*us)

    def test_suservos(self):
        print("*** Testing SUServos.")
        print("Initializing modules...")
        for card_name, card_dev in self.suservos:
            print(card_name)
            self.setup_suservo(card_dev)
        print("...done")
        print("Setting up SUServo channels...")
        for channels in chunker(self.suschannels, 8):
            for i, (channel_name, channel_dev) in enumerate(channels):
                print(channel_name)
                self.setup_suservo_loop(channel_dev, i)
        print("...done")
        print("Enabling...")
        for card_name, card_dev in self.suservos:
            print(card_name)
            self.setup_start_suservo(card_dev)
        print("...done")
        print("Each Sampler channel applies proportional amplitude control")
        print("on the respective Urukul0 (ADC 0-3) and Urukul1 (ADC 4-7, if")
        print("present) channels.")
        print("Frequency: 10 MHz, output power: about -9 dBm at 0 V and about -15 dBm at 1.5 V")
        print("Verify frequency and power behavior.")
        print("Press ENTER when done.")
        input()

    def run(self, tests):
        print("****** Sinara system tester ******")
        print("")
        self.core.reset()

        for name in tests:
            if getattr(self, name):
                getattr(self, f"test_{name}")()

    @classmethod
    def available_tests(cls):
        # listed in definition order
        return [
            name.split("_", maxsplit=1)[1]
            for name, obj in vars(cls).items()
            if is_hw_test(obj)
        ]


def is_hw_test(obj):
    return (
        inspect.isfunction(obj) and
        obj.__name__.startswith("test_") and
        len(inspect.signature(obj).parameters) == 1
    )


def get_argparser(available_tests):
    parser = argparse.ArgumentParser(description="Sinara crate testing tool")

    parser.add_argument("--device-db", default="device_db.py",
                        help="device database file (default: '%(default)s')")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-x", "--exclude", nargs="*", choices=available_tests,
                       help="do not run the listed tests")
    group.add_argument("-o", "--only", nargs="*", choices=available_tests,
                       help="run only the listed tests")
    return parser


def main():
    available_tests = SinaraTester.available_tests()
    args = get_argparser(available_tests).parse_args()

    if args.exclude is not None:
        # don't use set in order to keep the order
        tests = [test for test in available_tests if test not in args.exclude]
    elif args.only is not None:
        tests = args.only
    else:
        tests = available_tests

    device_mgr = DeviceManager(DeviceDB(args.device_db))
    try:
        experiment = SinaraTester((device_mgr, None, None, None))
        experiment.prepare()
        experiment.run(tests)
        experiment.analyze()
    finally:
        device_mgr.close_devices()


if __name__ == "__main__":
    main()
