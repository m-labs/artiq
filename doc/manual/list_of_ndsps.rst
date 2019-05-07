List of available NDSPs
=======================

The following network device support packages are available for ARTIQ. This list is non-exhaustive.

+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| Equipment                       | Nix package                       | Conda package                    | Documentation                                                                                       |
+=================================+===================================+==================================+=====================================================================================================+
| PDQ2                            | Not available                     | Not available                    | `HTML <https://pdq.readthedocs.io>`_                                                                |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| Lab Brick Digital Attenuator    | ``m-labs.lda``                    | ``("main", "lda")``              | `HTML <https://nixbld.m-labs.hk/job/artiq/main/lda-manual-html/latest/download/1>`_                 |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| Novatech 409B                   | ``m-labs.novatech409b``           | ``("main", "novatech409b")``     | `HTML <https://nixbld.m-labs.hk/job/artiq/main/novatech409b-manual-html/latest/download/1>`_        |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| Thorlabs T-Cubes                | ``m-labs.thorlabs_tcube``         | ``("main", "thorlabs_tcube")``   | `HTML <https://nixbld.m-labs.hk/job/artiq/main/thorlabs_tcube-manual-html/latest/download/1>`_      |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| Korad KA3005P                   | ``m-labs.korad_ka3005p``          | ``("main", "korad_ka3005p")``    | `HTML <https://nixbld.m-labs.hk/job/artiq/main/korad_ka3005p-manual-html/latest/download/1>`_       |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| Newfocus 8742                   | ``m-labs.newfocus8742``           | ``("main", "newfocus8742")``     | `HTML <https://nixbld.m-labs.hk/job/artiq/main/newfocus8742-manual-html/latest/download/1>`_        |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| Princeton Instruments PICam     | Not available                     | Not available                    | Not available                                                                                       |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| Anel HUT2 power distribution    | ``m-labs.hut2``                   | ``("main", "hut2")``             | `HTML <https://nixbld.m-labs.hk/job/artiq/main/hut2-manual-html/latest/download/1>`_                |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| TOPTICA lasers                  | ``m-labs.toptica-lasersdk-artiq`` | See anaconda.org                 | Not available                                                                                       |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+
| HighFinesse wavemeters          | ``m-labs.highfinesse-net``        | ``("main", "highfinessse-net")`` | `HTML <https://nixbld.m-labs.hk/job/artiq/main/highfinesse-net-manual-html/latest/download/1>`_     |
+---------------------------------+-----------------------------------+----------------------------------+-----------------------------------------------------------------------------------------------------+

In the "Nix package" column, ``m-labs`` refer to the Nix channel at https://nixbld.m-labs.hk/channel/custom/artiq/main/channel.

The "Conda package" column gives the line to add into ``install-with-conda.py`` to install the corresponding package. Conda packages may also be downloaded from https://nixbld.m-labs.hk/project/artiq and installed manually.

For PDQ2 see https://github.com/m-labs/pdq. For PICam see https://github.com/quartiq/picam.
