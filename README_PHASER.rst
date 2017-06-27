ARTIQ Phaser
============

ARTIQ contains a proof-of-concept design of a GHz-datarate, multi-channel, interpolating, multi-tone, direct digital synthesizer (DDS) compatible with ARTIQ's RTIO channels.
Ultimately it will be the basis for the ARTIQ Sayma Smart Arbitrary Waveform Generator project. See https://github.com/m-labs/sinara and https://github.com/m-labs/artiq-hardware.

*Features*:

* up to 4 channels
* up to 500 MHz data rate per channel (KC705 limitation)
* up to 8x interpolation to 2.4 GHz DAC sample rate
* Real-time sample-coherent control over amplitude, frequency, phase of each channel through ARTIQ RTIO commands
* Full configurability of the AD9154 and AD9516 through SPI with ARTIQ kernel support
* All SPI registers and register bits exposed as human readable names
* Parametrized JESD204B core (also capable of operation with eight lanes)
* The code can be reconfigured. Possible example configurations are: support 2 channels at 1 GHz datarate, support 4 channels at 300 MHz data rate, no interpolation, and using mix mode to stress the second and third Nyquist zones (150-300 MHz and 300-450 MHz). Please contact M-Labs if you need help with this.

The hardware required is a KC705 with an AD9154-FMC-EBZ plugged into the HPC connector and a low-noise sample rate reference clock.

This work was supported by the Army Research Lab and the University of Maryland.

The code that was developed for this project is located in several repositories:

* In ARTIQ, the SAWG and Phaser code: https://github.com/m-labs/artiq
* The Migen/MiSoC JESD204B core: https://github.com/m-labs/jesd204b


Installation
------------

These installation instructions are a short form of those in the ARTIQ manual.
Please refer to and follow the ARTIQ manual for more details:
https://m-labs.hk/artiq/manual-master/index.html

* Set up a new conda environment and activate it.
* Install the standard ARTIQ runtime/install dependencies.
  See ``conda/artiq/meta.yaml`` for a list.
  They are all packaged as conda packages in ``m-labs/main``.

* Install the standard ARTIQ build dependencies.
  They are all available as conda packages in m-labs/main or m-labs/dev for linux-64:

  - migen
  - misoc
  - jesd204b
  - llvm-or1k
  - rust-core-or1k
  - cargo
  - binutils-or1k-linux

* Install a recent version of Vivado (tested and developed with 2016.2).
* Do a checkout of ARTIQ: ::

    mkdir ~/src
    cd ~/src
    git clone --recursive https://github.com/m-labs/artiq.git
    cd ../artiq
    python setup.py develop


Setup
-----

* Setup the KC705 (jumpers, etc.) observing the ARTIQ manual.
  VADJ does not need to be changed.
* On the AD9154-FMC-EBZ put jumpers:

  - on XP1, between pin 5 and 6 (will keep the PIC in reset)
  - on JP3 (will force output enable on FXLA108)

* Compile the ARTIQ Phaser bitstream, bios, and runtime (c.f. ARTIQ manual): ::

    python -m artiq.gateware.targets.phaser

* From time to time and on request there may be pre-built binaries in the
  ``artiq-kc705-phaser`` package on the M-Labs conda package label.
* Generate an ARTIQ configuration flash image with MAC and IP address (see the
  documentation for ``artiq_mkfs``). Name it ``phaser_config.bin``.
* Run the following OpenOCD command to flash the ARTIQ phaser design: ::

    openocd -f board/kc705.cfg -c "init; jtagspi_init 0 bscan_spi_xc7k325t.bit; jtagspi_program misoc_phaser_kc705/gateware/top.bin 0x000000; jtagspi_program misoc_phaser_kc705/software/bios/bios.bin 0xaf0000; jtagspi_program misoc_phaser_kc705/software/runtime/runtime.fbi 0xb00000;jtagspi_program phaser_config.bin 0xb80000; xc7_program xc7.tap; exit"

  The proxy bitstream ``bscan_spi_xc7k325t.bit`` can be found at https://github.com/jordens/bscan_spi_bitstreams or in any ARTIQ conda package for the KC705.
  See the source code of ``artiq_flash.py`` from ARTIQ for more details.

  If you are using the OpenOCD Conda package:

  * locate the OpenOCD scripts directory with: ``python3 -c "import artiq.frontend.artiq_flash as af; print(af.scripts_path)"``
  * add ``-s <scripts directory>`` to the OpenOCD command line.

* Refer to the ARTIQ documentation to configure an IP address and other settings for the transmitter device.
  If the board was running stock ARTIQ before, the settings will be kept.
* A 300 MHz clock of roughly 10 dBm (0.2 to 3.4 V peak-to-peak into 50 Ohm) must be connected to the AD9154-FMC-EBZ J1. The input is 50 Ohm terminated. The RTIO clock, DAC deviceclock, FPGA deviceclock, and SYSREF are derived from this signal.
* The RTIO coarse clock (the rate of the RTIO timestamp counter) is 150
  MHz. The RTIO ``ref_period`` is 1/150 MHz = 5ns/6. The RTIO ``ref_multiplier`` is ``1``. C.f. ``device_db.py`` for both variables. The JED204B DAC data rate and DAC device clock are both 300 MHz. The JESD204B line rate is 6 GHz.
* Configure an oscilloscope to trigger at 0.5 V on rising edge of ttl_sma (user_gpio_n on the KC705 board). Monitor DAC0 (J17) on the oscilloscope set for 100 mV/div and 200 ns/div.
* An example device database, several status and test scripts are provided in ``artiq/examples/phaser/``. ::

    cd artiq/examples/phaser

* Edit ``device_db.py`` to match the hostname or IP address of the core device.
* Use ``ping`` and ``flterm`` to verify that the core device starts up and boots correctly.

Usage
-----

* Run ``artiq_run repository/demo.py`` for an example that exercises several different use cases of synchronized phase, amplitude, and frequency updates.
  for an example that exercises several different use cases of synchronized phase, amplitude, and frequency updates.
* Run ``artiq_run repository/demo_2tone.py`` for an example that emits a shaped two-tone pulse.
* Implement your own experiments using the SAWG channels.
* Verify clock stability between the sample rate reference clock and the DAC outputs.
