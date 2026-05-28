# ADR-0004 — `os_prep` role structure and idempotence as design rule

- **Status:** Accepted
- **Date:** 2026-05-28
- **Layer:** L1.1
- **Supersedes:** none
- **Superseded by:** none

## Context

Layer 1.1 introduces the first Ansible platform role: `os_prep`. The role
performs OS-level preparation for Kubernetes nodes — swap disable, kernel
module loading, sysctl tuning, time sync via chrony, AppArmor verification,
and a CIS-recommended unused-filesystem-module blacklist. It is the first
role applied by `bootstrap/site.yml` against every node in every deploy
shape (`lab-single-node`, `edge-site`, `ha-bare-metal`).

Two structural decisions had to be made before any task code was written.
Both have downstream consequences for every platform role that follows.

## Decision 1 — One role with per-concern task files (not split roles)

The role is implemented as a single Ansible role with task logic split
across per-concern task files (`tasks/swap.yml`, `tasks/kernel_modules.yml`,
`tasks/sysctl.yml`, etc.) imported from `tasks/main.yml` with tags.

### Alternatives considered

**A. Split into `os_baseline` + `kernel_tuning` + `hardening` roles.**
This is the canonical structure for a _shared role library_ — for example,
the Geerlingguy collection or DebOps — where roles are independently
consumed across multiple unrelated projects, and a consumer might want
`kernel_tuning` without `os_baseline`.

Rejected. This repository is a single platform, not a role library. No
consumer wants `kernel_tuning` without the rest. Splitting introduces
inter-role variable namespacing, `meta/main.yml` dependency chains, and
coordination overhead that earns nothing for a single-platform repo.
Revisit only if the role grows past ~200 tasks (it won't).

**B. One role, flat `tasks/main.yml` with inline tags.**
Workable but unreadable past ~200 lines. Per-concern files make each
concern scannable in 30 seconds.

### Decision

One role. Per-concern task files. Tags applied at the `import_tasks` level
in `tasks/main.yml`. Operator-facing tag surface documented in role README.

## Decision 2 — Idempotence is a hard design constraint, not a goal

Every task in the role MUST be idempotent. The Molecule scenario's
`idempotence` step (a second converge that fails if any task reports
`changed`) gates every commit in this slice.

### Consequences

Module choice is constrained from the first task:

- `swapoff -a` via `command` is forbidden; use `ansible.posix.mount` for
  fstab and gate runtime `swapoff` on `ansible_swaptotal_mb > 0`.
- `sysctl -w` via `command` is forbidden; use `ansible.posix.sysctl` with
  `sysctl_file:` for persistence.
- `modprobe` via `command` is forbidden; use `community.general.modprobe`
  for runtime + a template for `/etc/modules-load.d/` for persistence.
- Any `command` or `shell` task MUST carry a justifying `changed_when:`
  (typically `changed_when: false` for pure assertions).

The principle: a Kubernetes platform operator re-runs `site.yml` whenever
a node is added, replaced, or recovered. A role that reports `changed`
on every run trains operators to ignore change reports — which means real
unintended drift will be ignored too.

### Alternatives considered

**Make idempotence an aspirational goal, not a gate.**
Rejected. "Aspirational" idempotence decays the moment the gate is removed.
The molecule `idempotence` step is cheap; the operator cost of a noisy
role is high.

## Consequences

- Per-concern tagging is documented in the role README's Tags table.
- Every L1.1.x slice (swap, kernel_modules, sysctl, chrony, apparmor,
  cis_modules) ships its tasks AND its molecule assertions AND passes
  idempotence in the same commit set.
- Future platform roles (`containerd_install`, `kubeadm_install`, etc.)
  inherit this structure by default. Deviations require a new ADR.

## References

- HARDENING.md — defines workload-container hardening; this role does
  not contradict it but operates at a different layer (host OS).
- CLUSTER_BASELINE.md — `testbed-automator` audit; the anti-pattern this
  role is structured against (idempotence-blind shell scripts, no
  selective re-run, no test scaffold).
- Role README at `bootstrap/roles/os_prep/README.md` — operator-facing
  surface; this ADR is reviewer-facing rationale.
