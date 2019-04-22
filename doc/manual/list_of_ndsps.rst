List of available NDSPs
=======================

The following network device support packages are available for ARTIQ. This list is non-exhaustive.

+---------------------------------+-----------------------------------+----------------------------------+
| Equipment                       | Nix package                       | Conda package                    |
+=================================+===================================+==================================+
| PDQ2                            | Not available                     | Not available                    |
+---------------------------------+-----------------------------------+----------------------------------+
| Lab Brick Digital Attenuator    | ``m-labs.lda``                    | ``("main", "lda")``              |
+---------------------------------+-----------------------------------+----------------------------------+
| Novatech 409B                   | ``m-labs.novatech409b``           | ``("main", "novatech409b")``     |
+---------------------------------+-----------------------------------+----------------------------------+
| Thorlabs T-Cube                 | ``m-labs.thorlabs_tcube``         | ``("main", "thorlabs_tcube")``   |
+---------------------------------+-----------------------------------+----------------------------------+
| Korad KA3005P                   | ``m-labs.korad_k3005p``           | ``("main", "korad_k3005p")``     |
+---------------------------------+-----------------------------------+----------------------------------+
| Newfocus 8742                   | ``m-labs.newfocus8742``           | ``("main", "newfocus8742")``     |
+---------------------------------+-----------------------------------+----------------------------------+
| Princeton Instruments PICam     | Not available                     | Not available                    |
+---------------------------------+-----------------------------------+----------------------------------+
| Anel HUT2 power distribution    | ``m-labs.hut2``                   | ``("main", "hut2")``             |
+---------------------------------+-----------------------------------+----------------------------------+
| TOPTICA Lasers                  | ``m-labs.toptica-lasersdk-artiq`` | See anaconda.org                 |
+---------------------------------+-----------------------------------+----------------------------------+
| HighFinesse wavemeter           | ``m-labs.highfinesse-net``        | ``("main", "highfinessse-net")`` |
+---------------------------------+-----------------------------------+----------------------------------+

In the "Nix package" column, ``m-labs`` refer to the Nix channel at https://nixbld.m-labs.hk/channel/custom/artiq/main/channel.

The "Conda package" column gives the line to add into ``install-artiq.py`` to install the corresponding package. Conda packages may also be downloaded from https://nixbld.m-labs.hk/project/artiq and installed manually.

For PDQ2 see https://github.com/m-labs/pdq. For PICam see https://github.com/quartiq/picam.
