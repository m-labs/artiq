ARTIQ Phaser
============

This ARTIQ branch contains a proof-of-concept design of a GHz-datarate multichannel direct digital synthesizer (DDS) compatible with ARTIQ's RTIO channels.
In later developments this proof-of-concept can be expanded to provide a two-tone output with spline modulation and multi-DAC synchronization.
Ultimately it will be the basis for the ARTIQ Sayma Smart Arbitrary Waveform Generator project. See https://github.com/m-labs/sayma and https://github.com/m-labs/artiq-hardware.

*Features*:

* 4 channels
* 500 MHz data rate per channel (KC705 limitation)
* 4x interpolation to 2 GHz DAC sample rate
* Real-time control over amplitude, frequency, phase of each channel through ARTIQ RTIO commands
* Full configurability of the AD9154 and AD9516 through SPI with ARTIQ kernel support
* All SPI registers and register bits exposed as human readable names
* Parametrized JESD204B core (also capable of operation with eight lanes)
* The code can be reconfigured. Possible example configurations are: support 2 channels at 1 GHz datarate, support 4 channels at 300 MHz data rate, no interpolation, and using mix mode to stress the second and third Nyquist zones (150-300 MHz and 300-450 MHz).

The hardware required to use the ARTIQ phaser branch is a KC705 with an AD9154-FMC-EBZ plugged into the HPC connector and a low-noise 2 GHz reference clock.

This work was supported by the Army Research Lab.

The code that was developed for this project is located in several repositories:

* In ARTIQ, the SAWG and Phaser code: https://github.com/m-labs/artiq/compare/phaser
* The CORDIC core has been reused from the PDQ2 gateware https://github.com/m-labs/pdq2
* The Migen/MiSoC JESD204B core: https://github.com/m-labs/jesd204b


Installation
------------

These installation instructions are a short form of those in the ARTIQ manual.
Please refer to and follow the ARTIQ manual for more details:
https://m-labs.hk/artiq/manual-release-2/index.html

* Set up a new conda environment and activate it.
* Install the standard ARTIQ runtime/install dependencies.
  See ``conda/artiq/meta.yaml`` for a list.
  They are all packaged as conda packages in ``m-labs/main``.

* Install the standard ARTIQ build dependencies.
  They are all available as conda packages in m-labs/main at least for linux-64:

  - migen 0.4
  - misoc 0.3
  - llvm-or1k
  - rust-core-or1k
  - cargo
  - binutils-or1k-linux

* Install a recent version of Vivado (tested and developed with 2016.2).
* Checkout the ARTIQ phaser branch and the JESD204B core: ::

    mkdir ~/src
    cd ~/src
    git clone --recursive -b phaser https://github.com/m-labs/artiq.git
    git clone https://github.com/m-labs/jesd204b.git
    cd jesd204b
    python setup.py develop
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

    python -m artiq.gateware.targets.kc705 -H phaser --toolchain vivado

* Run the following OpenOCD command to flash the ARTIQ transmitter design: ::

    openocd -f board/kc705.cfg -c "init; jtagspi_init 0 bscan_spi_xc7k325t.bit; jtagspi_program misoc_phaser_kc705/gateware/top.bin 0x000000; jtagspi_program misoc_phaser_kc705/software/bios/bios.bin 0xaf0000; jtagspi_program misoc_phaser_kc705/software/runtime/runtime.fbi 0xb00000; xc7_program xc7.tap; exit"

  The proxy bitstream ``bscan_spi_xc7k325t.bit`` can be found at https://github.com/jordens/bscan_spi_bitstreams or in any ARTIQ conda package for the KC705.
  See the source code of ``artiq_flash.py`` from ARTIQ for more details.

  If you are using the OpenOCD Conda package:

  * locate the OpenOCD scripts directory with: ``python3 -c "import artiq.frontend.artiq_flash as af; print(af.scripts_path)"``
  * add ``-s <scripts directory>`` to the OpenOCD command line.

* Refer to the ARTIQ documentation to configure an IP address and other settings for the transmitter device.
  If the board was running stock ARTIQ before, the settings will be kept.
* A 2 GHz of roughly 10 dBm (0.2 to 3.4 V peak-to-peak into 50 Ohm) must be connected to the AD9154-FMC-EBZ J1.
  The external RTIO clock, DAC deviceclock, FPGA deviceclock, and SYSREF are derived from this signal.
* The ``startup_clock`` needs to be set to internal (``i``) for bootstrapping the clock distribution tree.
* Compile and flash the startup kernel in ``artiq/examples/phaser/startup_kernel.py``.

Usage
-----

* An example device database, several status and test scripts are provided in ``artiq/examples/phaser/``.
* After each boot, run the ``dac_setup.py`` experiment to establish the JESD204B links (``artiq_run repository/dac_setup.py``).
* Run ``artiq_run repository/sawg.py`` for an example that sets up amplitudes, frequencies, and phases on all four DDS channels.
* Implement your own experiments using the SAWG channels.
* Verify clock stability between the 2 GHz reference clock and the DAC outputs.
* Verify phase alignment between the DAC channels.
* Changes to the AD9154 configuration can also be performed at runtime in experiments.
  See the example ``dac_setup.py``.
  This can e.g. be used to enable and evaluate mix mode without having to change any other code (bitstream/bios/runtime/startup_kernel).
