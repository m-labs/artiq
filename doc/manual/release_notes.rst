ARTIQ Releases 
##############

ARTIQ follows a rolling release model, with beta, stable, and legacy channels. Different releases are saved as different branches on the M-Labs `ARTIQ repository <https://github.com/m-labs/artiq>`_. The ``master`` branch represents the beta version, where at any time the next stable release of ARTIQ is currently in development. This branch is unstable and does not yet guarantee reliability or consistency, but may also already offer new features and improvements; see the `beta release notes <https://github.com/m-labs/artiq/blob/master/RELEASE_NOTES.rst>`_ for the most up-to-date information. The ``release-[number]`` branches represent stable releases, of which the most recent is considered the current stable version, and the second-most recent the current legacy version. 

To install the current stable version of ARTIQ, consult the *current* `Installing ARTIQ <https://m-labs.hk/artiq/manual/installing.html>`_ page. To install beta or legacy versions, consult the same page in their respective manuals. Instructions given in pre-legacy versions of the manual may or may not install their corresponding ARTIQ systems, and may or may not currently be supported (e.g. M-Labs does not host older ARTIQ versions for Conda, and Conda support will probably eventually be removed entirely). Regardless, all out-of-date versions remain available as complete source code on the repository.

The beta manual is hosted `here <https://m-labs.hk/artiq/manual-beta/>`_. The current manual is hosted `here <https://m-labs.hk/artiq/manual/>`_. The legacy manual is hosted `here <https://m-labs.hk/artiq/manual-legacy/>`_. Older versions of the manual can be rebuilt from the source files in ``doc/manual``, retrieved from the respective branch.

.. include:: ../../RELEASE_NOTES.rst
