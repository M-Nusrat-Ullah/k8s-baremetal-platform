# ADR-0013: Real-host smoke-test harness for os_prep

- **Status:** Accepted
- **Date:** 2026-06-04
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1.7
- **Supersedes:** none
- **Superseded by:** none

## Context

Every `os_prep` slice (L1.1.1–L1.1.6) splits its work into a *persist* half
(files, packages — asserted in the Molecule container) and a *live* half
(kernel modules, sysctls, systemd unit state — guarded out of containers by
`ansible_facts['virtualization_type']`). The container scenario therefore
proves the artifacts are *written* but never that they *take effect*, and
never that they *survive a reboot*. Thirteen assertions in `verify.yml` sit
behind that guard, unexecuted, until a real host runs them.

The whole point of persisting to `modules-load.d`, `sysctl.d`, `fstab`,
`modprobe.d`, the chrony unit, and the timesyncd mask is that these survive a
boot without the role re-running. Nothing had proven that. ADR-0012 explicitly
deferred the modprobe-resolution proof to this slice. The foil,
`testbed-automator` (CLUSTER_BASELINE), has no tests, no CI, and no reboot
validation of any kind; a defensible alternative must demonstrate the property
it cannot.

## Decision

### Decision 1 — harness form

The harness is a **documented runbook plus a thin reboot playbook**, reusing
the existing `verify.yml` verbatim as the single assertion source. The flow is
four invocations against a real-host inventory:

1. `site.yml` — apply `os_prep` (the real production path, not a bespoke one).
2. `verify.yml` — prove the *live* state is correct.
3. `tests/smoke/reboot.yml` — reboot and block until the host returns.
4. `verify.yml` again — prove the *persisted* state survives a cold boot.

`verify.yml` is reused without modification: it is `hosts: all` and loads role
defaults via a playbook-relative `vars_files`, so it runs against the real
inventory exactly as it does under Molecule. The reboot playbook uses
`ansible.builtin.reboot` with HDD-tuned timeouts (`reboot_timeout: 900`,
`post_reboot_delay: 30`).

`os_prep` is wired into `site.yml` (a second play, `become`, gathered facts)
rather than applied through a throwaway smoke-apply playbook, so the harness
exercises the same path a real deployment uses.

### Decision 2 — built-in / absent tolerance in the blacklist proof

The L1.1.6 blacklist proof assumed every blacklisted module is loadable
(`=m`), asserting each resolves to `/bin/false`. On the noble generic kernel
this is false for `squashfs`, which is compiled in (`CONFIG_SQUASHFS=y`) —
verified on hardware on both the 6.8 GA and 6.17 HWE kernels. `modprobe.d`
cannot neutralize a built-in module, and CIS Ubuntu 24.04 §1.1.1 treats a
module that is built into the kernel — or absent entirely — as "no remediation
necessary": the loadable attack surface it warns about does not exist.

`verify.yml` therefore classifies each module with `modinfo --field filename`
and passes built-in (`(builtin)`) and absent (`rc != 0`) modules on that basis;
only a genuinely loadable module that fails to resolve to `/bin/false` is a
failure. `squashfs`'s real mitigation remains snapd removal (ADR-0012): nothing
mounts squashfs images, so the inert blacklist line is harmless and is kept for
CIS alignment and forward-compatibility with a future kernel that ships it
loadable.

## Consequences

- The 13 guarded assertions execute and pass on a real noble host, and pass
  again unchanged after a reboot — persistence is proven, not assumed.
- The harness runs against `lab-single-node`; `edge-site` / `ha-bare-metal`
  reuse the same playbooks with their own inventories.
- The harness is operator-run, not CI-run: it needs a real VM, a reboot, and
  preconditions (key auth, sudo, a pinned address). These live in the runbook
  (`tests/smoke/README.md`), not in automated CI.
- The smoke run surfaced two role defects the container could not: chrony's
  install removing `systemd-timesyncd` (fixed; see ADR-0010 amendment), and the
  swap-decoy assert depending on a Molecule fixture (gated to the container
  context). Both are now fixed and committed.
- The blacklist runtime proof promised in ADR-0012 is discharged here.

## Alternatives considered

- **Molecule with a VM driver (vagrant/libvirt):** rejected. Nested
  virtualization on the HDD lab VM is heavyweight, and Molecule's value
  (ephemeral, matrixed instances) buys nothing for a single slow real host. It
  would also duplicate the container scenario's purpose.
- **A single orchestrator playbook (apply → verify → reboot → verify in one
  run):** rejected for now. Importing `verify.yml` twice introduces
  path-resolution nuance, and on a slow HDD each step must be independently
  re-runnable (the post-reboot verify is the one you iterate on). Separate
  invocations, documented in the runbook, are more robust.
- **Duplicating the assertions into a dedicated smoke verify:** rejected.
  `verify.yml` is the single source of truth; duplicated asserts drift.
- **Extracting asserts into an include_tasks file shared by both:** unnecessary
  — `verify.yml` already runs verbatim against a real inventory, so no
  refactor of L1.1.1–L1.1.6 verified code was needed.

## References

- ADR-0004 (os_prep structure and idempotence)
- ADR-0010 (chrony time sync) and its L1.1.7 amendment
- ADR-0012 (CIS filesystem module blacklist — deferred the runtime proof here)
- CIS Ubuntu 24.04 Benchmark v1.0.0 §1.1.1
- CLUSTER_BASELINE (the no-test foil)
