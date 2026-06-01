# ADR-0002: Repository structure

- **Status:** Accepted
- **Date:** 2026-05-24
- **Deciders:** M Nusrat Ullah
- **Layer:** —
- **Supersedes:** none
- **Superseded by:** none

## Context

The repository deploys Kubernetes clusters to bare metal and on-prem VMs,
then drives day-2 operations through GitOps. It must support three deploy
shapes (`lab-single-node`, `edge-site`, `ha-bare-metal`) without
duplication, and stay navigable to a reviewer reading for five minutes.

Two structures are common in the wild:

1. **Flat top-level** — `clusters/`, `infrastructure/`, `apps/`,
   `ansible/`, `policies/` all at root.
2. **Grouped by execution model** — `bootstrap/` (imperative, Ansible)
   and `gitops/` (declarative, Flux) as two siblings, each with internal
   structure.

## Decision

Adopt the grouped structure:

- `bootstrap/` — Ansible: OS prep, kubeadm, CNI, Multus, Flux bootstrap.
- `gitops/` — Flux-managed: `clusters/`, `infrastructure/`, `apps/`,
  following the upstream Flux multi-cluster pattern.
- `policies/` — Kyverno policy library (baseline + workload exceptions),
  referenced _from_ `gitops/infrastructure/kyverno/`.
- `docs/` — ADRs, architecture, runbooks, diagrams.
- `scripts/`, `.github/workflows/` — supporting.

Per-cluster differences are expressed as Kustomize overlays under
`gitops/clusters/<name>/`, not by forking the tree.

## Consequences

**Positive:**

- The boundary between "what bootstrap does" and "what Flux owns" is a
  directory. Anything in `gitops/` is reconciled by Flux; anything in
  `bootstrap/` is run by an engineer with `ansible-playbook`. No
  ambiguity about where a manifest belongs.
- A new cluster shape is an inventory file plus a
  `gitops/clusters/<new-name>/` Kustomization. No surgery elsewhere.
- The `policies/` library is reusable across clusters and gives a stable
  home for the project's `PRIVILEGED_EXCEPTIONS` entries.

**Negative:**

- The `gitops/` wrapper adds one path segment vs. flat layout.
- Splitting `policies/` from `gitops/infrastructure/kyverno/` means a
  reviewer must look in two places to fully understand policy
  enforcement. Mitigated by short READMEs in each.
- New contributors must learn the bootstrap-vs-gitops split before
  touching anything.

## Alternatives considered

- **Flat top-level.** Less nesting, loses the explicit "Flux owns this"
  signal. Rejected for clarity.
- **Kustomize-only, no Flux.** Simpler, loses drift detection and the
  audit trail of reconciliation. Rejected; production posture requires
  reconciliation.
- **Helmfile / umbrella charts as source of truth.** Common, but
  charts-of-charts are hard to debug and lose per-cluster overlay
  clarity. Rejected.
- **One repo per cluster.** Eliminates cross-cluster coupling but
  multiplies maintenance and breaks the "same repo, multiple shapes"
  requirement.
