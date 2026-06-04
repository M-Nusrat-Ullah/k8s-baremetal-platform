# ADR-0011: AppArmor baseline for `os_prep`

- **Status:** Accepted
- **Date:** 2026-06-04
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1
- **Supersedes:** none
- **Superseded by:** none

## Context

The `os_prep` role (ADR-0004) prepares each node's OS baseline as a sequence of
per-concern slices. This slice (L1.1.5) establishes the AppArmor baseline.

AppArmor is Ubuntu's default Linux Security Module and a Kubernetes node
prerequisite. AppArmor support in Kubernetes is stable as of v1.31, so it is GA
on the pinned 1.34 line (ADR-0003). The kubelet verifies AppArmor is enabled on
the host before admitting a Pod that explicitly requests an AppArmor profile,
and rejects the Pod if the kernel module is not enabled. The authoritative
signal is the kernel module flag: `/sys/module/apparmor/parameters/enabled`
reads `Y` when AppArmor is active.

Two noble-specific facts shape this slice and rule out the naive "install and
start the service" approach:

- On Ubuntu 24.04 AppArmor is installed and **baked into the kernel** by
  default. Fully disabling it requires a kernel command-line parameter
  (`apparmor=0`), not stopping a service.
- `apparmor.service` is a **oneshot profile loader** gated by
  `ConditionSecurity=apparmor`. Once it has loaded the shipped profiles it exits
  and reports `inactive (dead)` — by design. Enforcement lives in the kernel,
  not in a long-running service, so service liveness is *not* a meaningful
  enablement signal: `systemctl is-active apparmor` returning inactive is the
  normal, healthy state.

What remains to decide is therefore narrow: what the role ensures, how and where
it asserts that AppArmor is enabled, and what it deliberately does not touch.

## Decision

### Decision 1 — ensure the AppArmor packages are present

Ensure `os_prep_apparmor_packages` (`apparmor`, `apparmor-utils`) are installed,
with `state: present` and no version pin or hold — the same posture and
reasoning as the chrony install (ADR-0010): AppArmor is a base-OS security
component whose reproducibility boundary is the pinned distribution release, not
an exact package version, and it must remain patchable.

`apparmor` is the actual kernel-module prerequisite. `apparmor-utils` is the
operator/management tooling (`aa-status`, `aa-enforce`, `aa-complain`,
`aa-genprof`, ...), kept so a node carries the AppArmor tooling for incident
response without needing `apt` on a possibly air-gapped host. On a stock noble
node both are already present, so the install is a no-op; the list exists to
guarantee the baseline on a minimized image where they could be absent.

Package presence is the only artifact this slice can assert inside the Molecule
container, and it is asserted there, mirroring the chrony package-presence
check.

### Decision 2 — preflight-assert the kernel module is enabled; do not manage the service

On real hosts the role asserts `/sys/module/apparmor/parameters/enabled == Y`
and fails loudly, with an actionable message, if it is not. This reads
host-kernel state — which inside a container reflects the Docker host, not
anything the role did — so it is guarded out of containers and exercised during
real `site.yml` execution and the L1.1.7 smoke test, consistent with the
persist/guarded split (ADR-0004).

This assertion lives in `tasks/apparmor.yml`, not only in `verify.yml`, and that
placement is deliberate. It is a **preflight gate** on a precondition the role
cannot remediate: AppArmor-enabled is a boot/kernel-command-line property, and
kubeadm does **not** preflight it (it is a kubelet pod-admission concern, not a
kubeadm check). Without this gate, a node booted with AppArmor disabled would
prepare, pass kubeadm preflight, and join cleanly, then fail later and silently
the first time an AppArmor-profiled Pod is scheduled onto it. Asserting at
`os_prep` time surfaces the fault at the earliest possible point, in the spirit
of a kubeadm preflight check. This differs in intent from the assertions in
`verify.yml`, which check what the role *produced*; the difference is
intentional, not an inconsistency in the role's structure.

"Enabled and enforcing," as used in the role's documentation, means the LSM is
active and enforces the profiles loaded in the kernel. It does **not** mean
`apparmor.service` is active (a oneshot, inactive by design), and it is **not**
asserted as an enforce-mode profile count (see Deliberately excluded).

### Deliberately excluded

- **`apparmor.service` state management.** The unit is a oneshot that is
  inactive once it has run; a task ensuring it `started`/`enabled` would report
  state that does not reflect enforcement and would mislead a reader into
  treating service liveness as the health signal. Enablement is read from the
  kernel flag instead.
- **Kernel command-line / GRUB modification.** A malformed `GRUB_CMDLINE_LINUX`
  can render a node unbootable — the wrong risk to take on in a baseline — and
  AppArmor is enabled by default on noble, so forcing `apparmor=1` would be
  redundant. Re-enabling AppArmor on a host that has been explicitly disabled is
  a separate, deliberate operator action, not a silent baseline change.
- **A `/proc/cmdline` check for `apparmor=0`.** Every disable vector
  (`apparmor=0`, selecting another LSM via `security=`) drives
  `/sys/module/apparmor/parameters/enabled` to `N`, so the kernel-flag check
  already covers them; a cmdline grep would be strictly narrower and add no
  coverage. The likely cause is surfaced in the assertion's failure message
  instead.
- **Profile authoring and enforce/complain mode changes.** These are
  per-profile and workload-specific, and flipping a profile to enforce can break
  the workload it confines. The CIS unused-filesystem-module blacklist is the
  separate L1.1.6 slice.
- **An `aa-status` enforce-mode-count assertion.** Which profiles are loaded and
  in enforce mode is node-dependent and verges on the profile-management concern
  this slice excludes. At the kernel level, "enabled" means the enforcement
  mechanism is live, which is the node prerequisite.

## Consequences

**Positive:**

- The kubelet's AppArmor prerequisite is guaranteed, and a node booted with
  AppArmor disabled fails loudly at `os_prep` time rather than silently at
  Pod-schedule time.
- The AppArmor packages, including the management tooling, are present even on a
  minimized image.
- The service-state and enablement facts are documented, so a future "the
  apparmor service isn't running" report is answered by this record rather than
  treated as a fault, and a future "add a cmdline grep / start the service" edit
  is caught in review.

**Negative:**

- This slice introduces an assertion in a task file (a preflight gate), a shape
  the prior slices do not use — they keep assertions in `verify.yml`. The
  distinction is justified above and noted in the task file, but it is a pattern
  a reviewer must understand.
- The enablement guarantee is verified only on real hosts and at L1.1.7, not in
  Molecule — consistent with every prior slice's live-action split (ADR-0004),
  but it means the container test proves only package presence.

## Alternatives considered

- **Manage `apparmor.service` (`enabled`/`started`).** Rejected: the unit is a
  oneshot that is inactive by design; its state is not an enablement signal, and
  managing it would misrepresent the baseline.
- **Modify GRUB to force `apparmor=1 security=apparmor`.** Rejected: a bad
  cmdline can make a node unbootable, and it is redundant on noble where
  AppArmor is the default. A separate, deliberate decision if a re-enable is
  ever required.
- **Author and enforce AppArmor profiles in the baseline.** Rejected: per-profile
  and workload-specific, and enforcing a profile can break its workload; the CIS
  module blacklist is L1.1.6.
- **Verify-only, without ensuring the packages.** Rejected: a minimized image
  could lack `apparmor`/`apparmor-utils`, leaving both the prerequisite and the
  incident-response tooling absent.
- **Assert enablement only in `verify.yml`.** Rejected: that checks at test time
  only. The preflight gate in `tasks/apparmor.yml` is what stops a real
  `site.yml` run against a non-compliant node, which is the point of the slice.

## References

- ADR-0003 — Kubernetes version pin; the pinned 1.34 line on which AppArmor is GA
- ADR-0004 — `os_prep` role structure and idempotence; the persist/guarded split
- ADR-0009 — sysctl baseline; the model for recording deliberate exclusions
- ADR-0010 — chrony slice; the `state: present` / no-pin package posture reused here
- Kubernetes documentation (v1.34), "Restrict a Container's Access to Resources
  with AppArmor" — AppArmor stable since v1.31; the kubelet verifies the module
  is enabled before admitting an AppArmor Pod; `/sys/module/apparmor/parameters/enabled`
- Ubuntu Server documentation, AppArmor — installed and loaded by default,
  kernel-baked from 24.04, and `apparmor.service` as a oneshot profile loader
