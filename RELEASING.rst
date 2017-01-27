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
6. If you have willing testers for release candidates, tag X.0rc1 in the release-X branch, have it build, and point testers there. Iterate over the previous points with new release candidates if necessary.
7. Tag X.0 in the release-X branch, build it, and copy its packages to ``main`` channel.
8. Mint a new DOI from Zenodo and update the README/introduction.
9. Update the m-labs.hk/artiq/manual redirect to point to m-labs.hk/artiq/manual-release-X (edit /artiq/.htaccess).

Minor (bugfix) releases
-----------------------

1. Backport bugfixes from the master branch or fix bugs specific to old releases into the currently maintained release-X branch(es).
2. When significant bugs have been fixed, tag X.Y+1.
3. To help dealing with regressions, no new features or refactorings should be implemented in release-X branches. Those happen in the master branch, and then a new release-X+1 branch is created.
