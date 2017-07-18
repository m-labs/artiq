.. Github links to this from the new issue page
   https://github.com/m-labs/artiq/issues/new. Keep relevant information for
   bug reporting at the top.

Reporting Issues/Bugs
=====================

Thanks for `reporting issues to ARTIQ
<https://github.com/m-labs/artiq/issues/new>`_! You can also discuss issues and
ask questions on IRC (the `#m-labs channel on freenode
<https://webchat.freenode.net/?channels=m-labs>`_) or on the `mailing list
<https://ssl.serverraum.org/lists/listinfo/artiq>`_.

The best bug reports are those which contain sufficient information. With
accurate and comprehensive context, an issue can be resolved quickly and
efficiently. Please consider adding the following data to your issue
report if possible:

* A clear and unique summary that fits into one line. Also check that
  this issue has not jet been reported. If it has, add additional information there.
* Precise steps to reproduce (list of actions that leads to the issue)
* Expected behavior (what should happen)
* Actual behavior (what happens instead)
* Logging message, trace backs, screen shots where relevant
* Components involved:

  * Operating system
  * Conda version
  * ARTIQ version (package or git commit id, versions for bitstream, BIOS,
    runtime and host software)
  * Hardware involved

For in-depth information on bug reporting, see:

http://www.chiark.greenend.org.uk/~sgtatham/bugs.html
https://developer.mozilla.org/en-US/docs/Mozilla/QA/Bug_writing_guidelines


Contributing Code
=================

ARTIQ welcomes contributions. Write bite-sized patches that can stand alone,
clean them up, write proper commit messages, add docstrings and unittests. Then
``git rebase`` them onto the current master or merge the current master. Verify
that the testsuite passes. Then prepare a pull request or send patches to the
`mailing list <https://ssl.serverraum.org/lists/listinfo/artiq>`_ to be
discussed. Expect your contribution to be held up to coding standards (e.g. use
``flake8`` to check yourself).

Copyright and Sign-Off
----------------------

Authors retain copyright of their contributions to ARTIQ, but whenever possible
should use the GNU LGPL version 3 license for them to be merged.

Works of US government employees are not copyrighted but can also be merged.

We've introduced a "sign-off" procedure on patches that are being sent around.

The sign-off is a simple line at the end of the explanation for the
patch, which certifies that you wrote it or otherwise have the right to
pass it on as an open-source patch.  The rules are pretty simple: if you
can certify the below:

        Developer's Certificate of Origin (1.1 from the Linux kernel)

        By making a contribution to this project, I certify that:

        (a) The contribution was created in whole or in part by me and I
            have the right to submit it under the open source license
            indicated in the file; or

        (b) The contribution is based upon previous work that, to the best
            of my knowledge, is covered under an appropriate open source
            license and I have the right under that license to submit that
            work with modifications, whether created in whole or in part
            by me, under the same open source license (unless I am
            permitted to submit under a different license), as indicated
            in the file; or

        (c) The contribution was provided directly to me by some other
            person who certified (a), (b) or (c) and I have not modified
            it.

        (d) I understand and agree that this project and the contribution
            are public and that a record of the contribution (including all
            personal information I submit with it, including my sign-off) is
            maintained indefinitely and may be redistributed consistent with
            this project or the open source license(s) involved.

then you just add a line saying

        Signed-off-by: Random J Developer <random@developer.example.org>

using your legal name (sorry, no pseudonyms or anonymous contributions.)

ARTIQ files that do not contain a license header are copyrighted by M-Labs Limited
and are licensed under GNU GPL version 3.
