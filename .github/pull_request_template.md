<!--

Thank you for submitting a PR to ARTIQ!

To ease the process of reviewing your PR, do make sure to complete the following boxes.

You can also read more about contributing to ARTIQ in this document:
https://github.com/m-labs/artiq/blob/master/CONTRIBUTING.rst#contributing-code

Based on https://raw.githubusercontent.com/PyCQA/pylint/master/.github/PULL_REQUEST_TEMPLATE.md
-->

# ARTIQ Pull Request

## Description of Changes

### Related Issue

<!-- 
If this PR fixes a particular issue, use the following to automatically close that issue
once this PR gets merged:

Closes #XXX 
-->

## Type of Changes

<!-- Leave ONLY the corresponding lines for the applicable type of change: -->
|   | Type |
| ------------- | ------------- |
| ✓  | :bug: Bug fix  |
| ✓  | :sparkles: New feature |
| ✓  | :hammer: Refactoring  |
| ✓  | :scroll: Docs |

## Steps (Choose relevant, delete irrelevant before submitting)

### All Pull Requests

- [x] Use correct spelling and grammar.
- [ ] Update [RELEASE_NOTES.md](../RELEASE_NOTES.md) if there are noteworthy changes, especially if there are changes to existing APIs.
- [ ] Close/update issues.
- [ ] Check the copyright situation of your changes and sign off your patches (`git commit --signoff`, see [copyright](../CONTRIBUTING.rst#copyright-and-sign-off)).

### Code Changes

- [ ] Run `flake8` to check code style (follow PEP-8 style). `flake8` has issues with parsing Migen/gateware code, ignore as necessary.
- [ ] Test your changes or have someone test them. Mention what was tested and how.
- [ ] Add and check docstrings and comments
- [ ] Check, test, and update the [unittests in /artiq/test/](../artiq/test/) or [gateware simulations in /artiq/gateware/test](../artiq/gateware/test)

### Documentation Changes

- [ ] Check, test, and update the documentation in [doc/](../doc/). Build documentation (`cd doc/manual/; make html`) to ensure no errors.

### Git Logistics

- [ ] Split your contribution into logically separate changes (`git rebase --interactive`). Merge/squash/fixup commits that just fix or amend previous commits. Remove unintended changes & cleanup. See [tutorial](https://www.atlassian.com/git/tutorials/rewriting-history/git-rebase).
- [ ] Write short & meaningful commit messages. Review each commit for messages (`git show`). Format:
  ```
  topic: description. < 50 characters total.
  
  Longer description. < 70 characters per line
  ```

### Licensing

See [copyright & licensing for more info](https://github.com/m-labs/artiq/blob/master/CONTRIBUTING.rst#copyright-and-sign-off).
ARTIQ files that do not contain a license header are copyrighted by M-Labs Limited and are licensed under LGPLv3+.
