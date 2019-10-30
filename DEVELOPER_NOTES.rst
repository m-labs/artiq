Sharing development boards
==========================

To avoid conflicts for development boards on the server, while using a board you must hold the corresponding lock file present in ``/var/lib/artiq/boards``. Holding the lock file grants you exclusive access to the board.

To lock the KC705 for 30 minutes or until Ctrl-C is pressed:
::
  flock --verbose /var/lib/artiq/boards/kc705-1 sleep 1800

Check that the command acquires the lock, i.e. prints something such as:
::
  flock: getting lock took 0.000003 seconds
  flock: executing sleep

To lock the KC705 for the duration of the execution of a shell:
::
  flock /var/lib/artiq/boards/kc705-1 bash

You may also use this script:
::
  #!/bin/bash
  exec flock /var/lib/artiq/boards/$1 bash --rcfile <(cat ~/.bashrc; echo PS1=\"[$1\ lock]\ \$PS1\")

If the board is already locked by another user, the ``flock`` commands above will wait for the lock to be released.

To determine which user is locking a board, use:
::
  fuser -v /var/lib/artiq/boards/kc705-1


Selecting a development board with artiq_flash
==============================================

The board lock file also contains the openocd commands for selecting the corresponding developer board:
::
  artiq_flash -I "$(cat /var/lib/artiq/boards/sayma-1)"


Deleting git branches
=====================

Never use ``git push origin :branch`` nor ``git push origin --delete branch``, as this can delete code that others have pushed without warning. Instead, always delete branches using the GitHub web interface that lets you check better if the branch you are deleting has been fully merged.
