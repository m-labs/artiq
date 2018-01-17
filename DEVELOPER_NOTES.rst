Release process
===============

Maintain ``RELEASE_NOTES.rst`` with a list of new features and API changes in each major release.

Major releases
--------------

1. Create branch release-X from master.
2. Tag the next commit in master X+1.0.dev.
3. Ensure that release versions of all packages required are available under the ``main`` label in conda. Ensure that new packages in ``main`` do not break older ARTIQ releases.
4. In the release-X branch, remove any unfinished features.
5. Test and fix any problems found. Apply fixes to both master and release-X.
6. If you have willing testers for release candidates, tag X.0rc1 in the release-X branch (generally use signed annotated tags, i.e. ``git tag -sa X.0rc1``), have it build, and point testers there. Iterate over the previous points with new release candidates if necessary.
7. Tag X.0 in the release-X branch, build it, and copy its packages to ``main`` channel.
8. Mint a new DOI from Zenodo and update the README/introduction.
9. Update the m-labs.hk/artiq/manual redirect to point to m-labs.hk/artiq/manual-release-X (edit /artiq/.htaccess).
10. "Draft a new release" and close the milestone on GitHub.
11. Deprecate the old release documentation with a banner in
    doc/manual/_templates/layout.html in the old ``release-(X-1)`` branch.

Minor (bugfix) releases
-----------------------

1. Backport bugfixes from the master branch or fix bugs specific to old releases into the currently maintained release-X branch(es).
2. When significant bugs have been fixed, tag X.Y+1.
3. To help dealing with regressions, no new features or refactorings should be implemented in release-X branches. Those happen in the master branch, and then a new release-X+1 branch is created.
4. "Draft a new release" and close the milestone on GitHub.

Sharing development boards
==========================

To avoid conflicts for development boards on the server, while using a board you must hold the corresponding lock file present in ``/run/board``. Holding the lock file grants you exclusive access to the board.

To lock the KC705 for 30 minutes or until Ctrl-C is pressed:
::
  flock --verbose /run/boards/kc705-1 sleep 1800

Check that the command acquires the lock, i.e. prints something such as:
::
  flock: getting lock took 0.000003 seconds
  flock: executing sleep

To lock the KC705 for the duration of the execution of a shell:
::
  flock /run/boards/kc705-1 bash

You may also use this script:
::
  #!/bin/bash
  exec flock /run/boards/$1 bash --rcfile <(cat ~/.bashrc; echo PS1=\"[$1\ lock]\ \$PS1\")

If the board is already locked by another user, the ``flock`` commands above will wait for the lock to be released.

To determine which user is locking a board, use:
::
  fuser -v /run/boards/kc705-1


Selecting a development board with artiq_flash
==============================================

Use the ``bus:port`` notation::

  artiq_flash --preinit-command "ftdi_location 5:2"   # Sayma 1
  artiq_flash --preinit-command "ftdi_location 3:10"  # Sayma 2
  artiq_flash --preinit-command "ftdi_location 5:1"   # Sayma 3


Deleting git branches
=====================

Never use ``git push origin :branch`` nor ``git push origin --delete branch``, as this can delete code that others have pushed without warning. Instead, always delete branches using the GitHub web interface that lets you check better if the branch you are deleting has been fully merged.
