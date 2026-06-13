# ADR-0023: Cilium delivery — Helm via kubernetes.core.helm; two-plane split

- **Status** — Accepted
- **Date** — 2026-06-07
- **Deciders** — Nusrat Ullah
- **Layer** — L2
- **Supersedes** — none
- **Superseded by** — none

## Context

Cilium must be installed before the cluster is usable and before Flux runs
(Flux pods need a CNI for IPs). It cannot live in GitOps. Two questions
arise: which tool to use for the Helm install, and what boundary separates
the bootstrap-time install from the runtime configuration that GitOps owns.

**Installation tool candidates:**

- `cilium-cli` — the official Cilium CLI. Rejected: it obscures the exact
  values being deployed, is awkward to template per shape, and adds a
  bespoke binary that requires its own version pin with no general-purpose
  use beyond Cilium.
- `helm` (standalone) with shell tasks — works, but the `kubernetes.core.helm`
  collection module (`6.1.0`, already pinned) provides idempotent
  install/upgrade semantics, per-shape values templating, and namespace
  handling as a first-class Ansible task.
- `kubernetes.core.helm` — chosen. The collection is already a dependency.
  Per-shape values files (committed) replace `--set` soup. The helm binary
  must be present on the target node; it is installed in Slice A before
  the Cilium play runs.

**Plane split:** bootstrap (Ansible) owns day-0 install; GitOps (Flux, L4a)
owns runtime objects that benefit from drift-detection and reconciliation:
BGP CRs, LB-IPAM pools, Gateways/Routes, NetworkPolicies. The trade-off is
that Cilium feature-flag changes require an Ansible run, not a git commit.
This is accepted: the planned 1.34→1.35 upgrade is a deliberate documented
bootstrap operation, not a silent HelmRelease bump.

## Decision

**Cilium is installed via `kubernetes.core.helm`**, run on the first
control-plane node (`run_once`), with committed per-shape values files.
The chart is pinned to the `1.19.x` release chosen in ADR-0028.

**Two-plane split:**

| Plane | Owns |
|-------|------|
| Bootstrap (`bootstrap/roles/cilium_install`) | Gateway API CRDs; Cilium Helm release + all feature-flag values |
| GitOps (`gitops/`, L4a) | BGP CRs, LB-IPAM pools, Gateways/Routes, NetworkPolicies |

`cilium-cli` is explicitly rejected and must not be introduced.

## Consequences

- Cilium feature-flag changes (e.g., adding a Hubble metric, adjusting
  `externalIPs`) require an Ansible run, not a Flux reconciliation. This is
  an accepted trade-off: changes are infrequent and deserve a deliberate
  run, not silent drift-correction.
- The `helm` binary must be installed on the target before the Cilium play.
  This is Slice A of the implementation (versions.yml pin + install task).
- Per-shape values files live in the role and are committed. No `--set`
  arguments at runtime; the deployed state is fully auditable from git.
- `kubernetes.core.helm` is pinned at `6.1.0` via `requirements.yml`; bumps
  follow the normal `chore(deps)` pattern.

## Alternatives considered

**`cilium-cli`.** Rejected: obscures deployed values, hard to template,
bespoke binary with no other use.

**Standalone `helm` via shell tasks.** Works but is strictly worse than the
`kubernetes.core.helm` module for idempotency and structure.

**HelmRelease (Flux).** Rejected for the bootstrap layer: Flux itself needs
the CNI to run, creating a bootstrap cycle.

## References

- L2 design doc §4 (integration model, two-plane split)
- L2 design doc §10 (bootstrap role and sequence)
- ADR-0028 (Cilium version choice)
