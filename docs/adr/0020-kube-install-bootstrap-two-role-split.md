# ADR-0020: kube_install / kube_bootstrap two-role split

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.2
- **Supersedes:** none
- **Superseded by:** none

## Context

The kubeadm layer has two fundamentally different halves: installing
packages (testable in a Docker container) and forming the cluster
(requires real kernel, systemd as PID 1, etcd I/O, and real network
interfaces). These could be one role, two roles, or three roles (install
/ init / join).

The Molecule constraint is firm: `kubeadm init` and `kubeadm join`
cannot run in a Docker-driver Molecule scenario. A single role that
mixes both halves would produce a Molecule scenario that silently omits
its most consequential tasks.

## Decision

Two roles: `kube_install` (Molecule-testable) and `kube_bootstrap` (real-
host only, no Molecule scenario by design).

- `kube_install` — apt repo, package install, dpkg hold, image pre-pull.
- `kube_bootstrap` — `init.yml`, `join.yml`, `kubeconfig.yml`,
  `untaint.yml`.

## Consequences

**Positive:**

- The test boundary maps exactly onto the role boundary. `kube_install`
  has a Molecule scenario that covers everything it does. `kube_bootstrap`
  has no Molecule scenario and its README explains why — the gap is
  explicit and bounded, not silent.
- init and join remain in one role, keeping the cross-host variable
  contract (join command produced by CP, consumed by workers via hostvars)
  local to `kube_bootstrap`.
- `kube_install` runs on all nodes; init/join targeting is done by the
  playbook via host-group conditions. This is idiomatic Ansible.

**Negative:**

- `kube_bootstrap` has no automated test coverage. Mitigated by real-host
  smoke testing and the fact that `kubeadm init` itself is idempotent via
  its own preflight checks.

## Alternatives considered

**Single role.** Simpler file count. Rejected: forces a Molecule scenario
that is either misleading (skips init/join silently) or absent, with no
clear boundary explaining why.

**Three roles (install / init / join).** Maximum separation. Rejected:
the join command is produced by the CP and consumed by workers — splitting
init and join across roles smears that cross-host contract across a role
boundary and requires hostvars plumbing at the meta level rather than
within one role.
