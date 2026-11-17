# ADR-0029: Kubernetes 1.36 re-baseline and version lifecycle policy

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** M Nusrat Ullah
- **Layer:** —
- **Supersedes:** ADR-0003
- **Superseded by:** none
- **Amends:** ADR-0015 (containerd line, config schema version, pause pin)

## Context

ADR-0003 pinned Kubernetes 1.34 and planned a 1.34 → 1.35 upgrade before
October 2026. That upgrade did not happen. Kubernetes 1.34 reached End of
Life on 2026-10-27 (final patch 1.34.13), so the pin is now an unpatched
line.

The lab cluster is still at the end of L1.2: one node, `NotReady` because
no CNI is installed, and no workloads.

Upstream state, checked on 2026-11-16:

| Component | Line | Latest | Maintenance mode | End of Life |
| --------- | ---- | ------ | ---------------- | ----------- |
| Kubernetes | 1.35 | 1.35.10 | 2026-12-28 | 2027-02-28 |
| Kubernetes | 1.36 | 1.36.6 | 2027-04-28 | 2027-06-28 |
| Kubernetes | 1.37 | 1.37.2 | 2027-08-28 | 2027-10-28 |
| containerd | 2.1 | 2.1.9 | — | 2026-07-03 (past) |
| containerd | 2.2 | 2.2.10 | — | 2026-11-06 (past) |
| containerd | 2.3 (LTS) | 2.3.7 | — | 2028-04-30 |
| containerd | 2.4 | 2.4.2 | — | 2027-05-16 |

Three compatibility facts constrain the choice:

- **Cilium tested matrix.** Cilium 1.19 lists Kubernetes 1.32–1.35.
  Cilium 1.20 lists Kubernetes 1.33–1.36. No released Cilium version lists
  Kubernetes 1.37.
- **containerd support matrix.** Kubernetes 1.36 is supported on
  containerd 2.2.0+ and 2.3.0+. The previous pin, containerd 2.1.5, is
  both End of Life and outside that set.
- **kubeadm.** `kubeadm.k8s.io/v1beta4` is the current config API in 1.36,
  so ADR-0016's config file needs no migration. kubeadm 1.36 expects
  `registry.k8s.io/pause:3.10.2`.

The hardening floor of Kubernetes 1.32 recorded in ADR-0003 is still met.

## Decision

### Decision 1 — pins

- **Kubernetes 1.36**, apt version `1.36.6-1.1` from the
  `pkgs.k8s.io/core:/stable:/v1.36/deb/` repository.
- **containerd.io 2.3.6** (`2.3.6-1~ubuntu.24.04~noble`), the 2.3 LTS line.
- **Sandbox image** `registry.k8s.io/pause:3.10.2`.

`kubeadm`, `kubelet` and `kubectl` stay pinned via apt and held with
`apt-mark hold`, as in ADR-0003.

### Decision 2 — version lifecycle policy

1. **Target minor.** Pin the newest Kubernetes minor that appears in the
   tested matrix of the current Cilium stable release. Pick the containerd
   line from the containerd support matrix for that minor, preferring an
   LTS line.
2. **Re-baseline trigger.** The pinned Kubernetes minor entering
   maintenance mode (two months before End of Life) opens a re-baseline.
   For 1.36 that date is 2027-04-28. The dates are recorded in a comment
   beside the pin in `bootstrap/group_vars/all/versions.yml`.
3. **Patch refresh.** A patch bump within the pinned minor needs no ADR.
   It is a `chore(versions)` commit made at any rebuild or planned
   maintenance.
4. **Tracking is manual.** The sources are the Kubernetes releases page,
   the Cilium compatibility page and the containerd `RELEASES.md`. No CI
   or automated tracking is added.

### Decision 3 — rebuild or upgrade

- A cluster that carries no workloads is **rebuilt** from `site.yml` on a
  clean OS snapshot.
- A cluster that carries workloads is upgraded in place with
  `kubeadm upgrade`, one minor at a time, with add-on compatibility
  checked before the upgrade starts. The runbook
  (`docs/runbooks/k8s-minor-upgrade.md`) is written the first time this is
  exercised.

This re-baseline is a rebuild.

## Consequences

**Positive:**

- Seven months of patch support from the decision date, against three and
  a half for 1.35.
- The Kubernetes, Cilium and containerd pins are each inside the others'
  published support matrices.
- The rebuild exercises `site.yml` end to end on the new pins.
- ADR-0003's objection to 1.36 (early patch series) no longer applies at
  the sixth patch.

**Negative:**

- The 1.34 → 1.35 upgrade exercise that ADR-0003 wanted did not take
  place. The first in-place upgrade becomes 1.36 → 1.37.
- That upgrade is gated on a Cilium release that lists Kubernetes 1.37.
- Lifecycle tracking depends on someone checking dates by hand.

**Amendment to ADR-0015.** The generate-transform-copy mechanism stands.
Three details change:

- The validated binary is `containerd.io 2.3.6-1~ubuntu.24.04~noble`.
- `containerd config default` on 2.3.6 emits `version = 4`, not the v3
  schema ADR-0015 describes. Both transform targets are still present
  exactly once: `SystemdCgroup` under the runc options stanza, and
  `sandbox` under
  `[plugins.'io.containerd.cri.v1.images'.pinned_images]`. Validated on
  2026-11-17 against the default config of the pinned binary.
- The sandbox image pin is `pause:3.10.2`, matched to kubeadm 1.36.

## Alternatives considered

- **Kubernetes 1.35.** Supported by both Cilium 1.19 and 1.20. Rejected:
  it enters maintenance mode on 2026-12-28 and is End of Life on
  2027-02-28, which repeats the situation this ADR exists to fix.
- **Kubernetes 1.37.** Longest runway. Rejected: no released Cilium
  version lists it as tested.
- **In-place upgrade chain 1.34 → 1.35 → 1.36.** Rejected: the cluster has
  no CNI and no workloads, so there is nothing to preserve, and the
  container runtime line has to change at the same time.
- **containerd 2.4.** Rejected: not an LTS line, End of Life 2027-05-16,
  and not listed for Kubernetes 1.36 in the containerd support matrix.
- **A separate version-lifecycle ADR.** Rejected: ADR-0003 already paired
  the pin with the upgrade strategy, and the policy is four rules.
- **Automated End-of-Life tracking in CI.** Rejected as scope creep for a
  single-maintainer repository.

## References

- ADR-0003 — superseded by this record
- ADR-0015 — containerd config generation; amended by this record
- ADR-0016 — kubeadm config file (`v1beta4`)
- ADR-0030 — Cilium 1.20.x, the release whose tested matrix lists 1.36
- Kubernetes releases: https://kubernetes.io/releases/
- Cilium Kubernetes compatibility:
  https://docs.cilium.io/en/stable/network/kubernetes/compatibility/
- containerd support matrix:
  https://github.com/containerd/containerd/blob/main/RELEASES.md
