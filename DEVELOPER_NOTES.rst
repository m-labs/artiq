Sharing development boards
==========================

To avoid conflicts for development boards on the server, while using a board you must hold the corresponding lock file present in the ``/tmp`` folder of the machine to which the board is connected. Holding the lock file grants you exclusive access to the board.

For example, to lock the KC705 until ENTER is pressed:
::
  ssh rpi-1.m-labs.hk "flock /tmp/board_lock-kc705-1 -c 'echo locked; read; echo unlocked'"

If the board is already locked by another user, the ``flock`` commands above will wait for the lock to be released.

To determine which user is locking a board, use a command such as:
::
  ssh rpi-1.m-labs.hk "fuser -v /tmp/board_lock-kc705-1"


Deleting git branches
=====================

Never use ``git push origin :branch`` nor ``git push origin --delete branch``, as this can delete code that others have pushed without warning. Instead, always delete branches using the GitHub web interface that lets you check better if the branch you are deleting has been fully merged.
