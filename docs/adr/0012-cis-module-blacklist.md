# ADR-0012: CIS filesystem module blacklist

- **Status:** Accepted
- **Date:** 2026-06-04
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1.6
- **Supersedes:** none
- **Superseded by:** none

## Context

CIS Ubuntu 24.04 Benchmark v1.0.0 section 1.1.1 mandates neutralising unused
filesystem kernel modules to reduce the kernel attack surface. The
alternative CLUSTER_BASELINE does not implement this hardening, leaving a
larger attack surface. A curated subset of filesystem modules is blacklisted;
the set is scoped to the CIS filesystem-module list only.

## Decision

### Decision 1 — the blacklist set, mechanism, and file

The `os_prep_module_blacklist` list contains: `cramfs`, `freevxfs`, `hfs`,
`hfsplus`, `jffs2`, `squashfs`, `udf`, `usb-storage`. These are the CIS §1.1.1
filesystem entries, curated for a Kubernetes node.

Each module is neutralized with **both** an `install <module> /bin/false` line
and a `blacklist <module>` line, written to a single consolidated file
(`/etc/modprobe.d/cis-blacklist.conf`). The install directive uses `/bin/false`
(per CIS 24.04, not the older `/bin/true`) and returns non-zero, blocking
explicit loads; blacklist alone does not prevent explicit modprobe.

A single file keeps the configuration trivial and follows the pattern of
`os_prep_sysctl_file`. CIS requires the directives to exist somewhere under
`/etc/modprobe.d/`, not one file per module.

The blacklist set **must** be disjoint from `os_prep_kernel_modules` (the
platform’s loaded modules). This invariant is enforced in `verify.yml` (see
ADR-0007). The only exception — `overlay` — is explicitly excluded from the
blacklist because containerd’s overlayfs snapshotter requires it; it is loaded
via `os_prep_kernel_modules`.

`vfat` is also excluded. It was dropped from the CIS 24.04 list upstream;
blacklisting it risks unbootable UEFI nodes (vfat backs the EFI System
Partition). The exclusion is documented in the defaults for auditability.

### Decision 2 — snapd removal (squashfs coupling)

`squashfs` is blacklisted. snapd mounts snaps as squashfs filesystems; leaving
snapd installed would cause failures on snap mount. A Kubernetes node is a
single-purpose appliance that runs no snaps. Therefore the role removes the
`snapd` package (purge) in the same slice that deploys the blacklist.

## Consequences

- USB mass-storage and snap packages no longer function on the node (intended
  reduction of attack surface).
- Edge nodes that require USB recovery must override `os_prep_module_blacklist`
  in their group_vars to drop `usb-storage`.
- The blacklist set can be overridden per OS in group_vars without changing the
  role’s logic, because the mechanism (install+blacklist) is identical across
  Ubuntu releases.
- The runtime proof that modules cannot load (modprobe --dry-run resolving to
  /bin/false) is deferred to the L1.1.7 reboot smoke test, where real kernel
  behaviour can be observed.

## Alternatives considered

- **One file per module:** adds clutter without benefit; CIS does not require
  separate files.
- **Blacklist without install directive:** insufficient — CIS explicitly
  requires the install line; modules can still be loaded via modprobe.
- **Use /bin/true (older CIS version):** CIS 24.04 uses /bin/false to ensure a
  non-zero exit code; sticking to the target benchmark avoids drift.
- **Keep snapd and skip squashfs blacklist:** weakens hardening; snapd is
  unnecessary on Kubernetes nodes and can be removed safely.
- **Build per-OS lists now:** premature — the mechanism is version-invariant;
  when a second OS is adopted, override the list in group_vars.

## References

- CIS Ubuntu 24.04 Benchmark v1.0.0 §1.1.1
- ADR-0007 (kernel module strategy)
- ADR-0011 (AppArmor baseline)
