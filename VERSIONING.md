# Versioning policy

Inventory Pro uses semantic versions in `VERSION` (`MAJOR.MINOR.PATCH`).

* `MAJOR` may include incompatible migration or API changes and provides an
  upgrade guide.
* `MINOR` adds backward-compatible behaviour or operational improvements.
* `PATCH` fixes compatible defects and security issues.

Pre-release identifiers are permitted for explicitly labelled test releases.
Every release is an immutable GitHub release and container image digest; moving
tags are not update targets.
