# ADR-0003: Kubernetes version pin and upgrade strategy

- **Status:** Accepted
- **Date:** 2026-05-24
- **Deciders:** M Nusrat Ullah
- **Layer:** —
- **Supersedes:** none
- **Superseded by:** none

## Context

The repository must pin a specific Kubernetes minor version. Constraints
at decision time:

- A customer-side requirement (Grameenphone hardening) sets a floor of
  Kubernetes 1.32.
- Kubernetes 1.32 reached End of Life on 2026-02-28 — no further
  security patches.
- Kubernetes 1.33 reaches EOL on 2026-06-28 — approximately five weeks
  from this decision.
- Kubernetes 1.34 reaches EOL on 2026-10-27 — five months of standard
  patch support.
- Kubernetes 1.35 reaches EOL on 2027-02-28 — nine months of patch
  support; also the _last_ minor that supports containerd 1.x.
- Kubernetes 1.36 became GA in April 2026; very early in its patch series.

The repo will be developed and demoed over several months. A version
that goes EOL mid-development is unacceptable; a version that just GA'd
carries patch-stability risk.

## Decision

Pin to **Kubernetes 1.34** (latest patch at install time, refreshed per
patch release). Treat 1.35 as the next planned upgrade target.
`kubeadm`, `kubelet`, and `kubectl` are pinned via apt and held with
`apt-mark hold`.

Upgrade strategy:

- `kubeadm` upgrades are one minor at a time — skip-minor is unsupported.
- Add-on compatibility (Cilium in particular) is verified against the
  target K8s version _before_ the upgrade PR is opened.
- Each minor upgrade is a PR touching
  `bootstrap/group_vars/all/versions.yml` plus the relevant
  `gitops/infrastructure/*/release.yaml`. A runbook
  (`docs/runbooks/k8s-minor-upgrade.md`) is created the first time the
  upgrade is exercised.

## Consequences

**Positive:**

- Five months of patch support gives a generous build-out window for
  Layers 1–7 without an in-flight EOL.
- Forces a real, documented 1.34 → 1.35 upgrade during the project —
  portfolio asset.
- Avoids the early-patch risk of 1.36.

**Negative:**

- Forces the upgrade exercise before October 2026.
- One minor behind the latest GA. None of those features are required
  for current workloads.

## Alternatives considered

- **1.32.** Floor of the GP requirement, but already EOL. Rejected —
  running without security patches is not "production-grade."
- **1.33.** Live for five more weeks. Rejected — would force an upgrade
  before Layer 1 is finished.
- **1.35.** Longer runway, last containerd-1.x supporter. Acceptable
  alternative. Chose 1.34 because the _forced_ upgrade is a portfolio
  feature; 1.35 lets the project coast.
- **1.36.** Too early in its patch series. The first three patches of a
  new minor historically carry the most regressions. Rejected for
  production posture.
