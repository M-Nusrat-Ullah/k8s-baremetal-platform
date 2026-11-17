# ADR-0028: Adopt Cilium 1.19.x over parent design's 1.16 LTS

- **Status** — Superseded by ADR-0030
- **Date** — 2026-06-07
- **Deciders** — Nusrat Ullah
- **Layer** — L2
- **Supersedes** — none
- **Superseded by** — ADR-0030

## Context

The platform's parent CNI design doc (confidential; read 2026-06-08) targets
**Cilium 1.16 LTS** (released 2024). The platform uses **Kubernetes 1.34.8**
(ADR-0003). Two questions arise:

1. Is Cilium 1.16 compatible with K8s 1.34?
2. Do the capabilities required by this platform's design (BGP v2 CRDs,
   mature Egress Gateway) exist in 1.16?

**K8s 1.34 compatibility.** Cilium's support matrix ties each Cilium minor
to a set of K8s minors. Cilium 1.16 was released against K8s 1.28–1.30;
K8s 1.34 is outside its supported range. Running unsupported K8s versions
risks undocumented behaviour in the kube-proxy-replacement path, CRD
schema drift, and missed bug fixes. Cilium 1.19.x is the version whose
support matrix covers K8s 1.34.

**BGP CRD graduation.** The `cilium.io/v2` BGP CRDs
(`CiliumBGPClusterConfig`, `CiliumBGPPeerConfig`, `CiliumBGPAdvertisement`)
graduated from `v2alpha1` in Cilium 1.17. ADR-0025 uses the `v2` API;
this requires at least Cilium 1.17.

**Egress Gateway maturity.** Egress Gateway reached GA status in Cilium 1.17
(`egressGateway.enabled`, `installRoutes` sub-option). ADR-0027 depends on
this. Cilium 1.16 has the feature but at an earlier maturity level.

**Parent doc compatibility.** The parent doc's design principles (native
routing, cluster-pool IPAM, BGP for LB-IP advertisement) are fully preserved
in 1.19. The `v2alpha1` CR examples in the doc remain valid as a baseline
conceptual reference; specific apiVersions must be verified against the 1.19
CRD manifests when runtime objects are written (ADR-0025).

## Decision

**Cilium 1.19.x** is the version pin for this platform. The exact patch
(`1.19.x`) is determined at the `chore(versions): pin cilium` commit by
fetching the latest patch available on the `cilium/cilium` Helm repo at that
time. **1.20.x and above are not used** until a deliberate upgrade ADR is
written — the design was drawn against 1.19 behaviour and defaults.

The patch version pinned in `versions.yml` must be accompanied by:
- The Helm chart version (tracks the Cilium version 1:1 for Cilium's repo)
- The `cilium` and `cilium-operator` image digests (cosign-verified pull)

## Consequences

- The parent doc's `v2alpha1` BGP CR examples cannot be used verbatim.
  Each CR's `apiVersion` is verified against the 1.19 CRD manifest before
  the runtime objects are written.
- `helm show values cilium/cilium --version <1.19.x-pin>` is the authority
  for all key/default behaviour. Any value in the design doc §7 that is not
  confirmed against the 1.19 chart defaults must be pinned explicitly rather
  than assumed to be the default.
- When K8s is upgraded to 1.35, the Cilium support matrix must be checked
  again. If 1.19.x does not cover 1.35, a Cilium upgrade ADR is written
  before the K8s upgrade proceeds.

## Alternatives considered

**Cilium 1.16 LTS (parent doc baseline).** Rejected: outside the K8s 1.34
support window; `cilium.io/v2` BGP CRDs not available; Egress Gateway at
earlier maturity. Following the parent doc's version baseline would require
running unsupported combinations.

**Cilium 1.20.x or main.** Rejected: the design and Helm value analysis
were done against 1.19 behaviour. Adopting an untested version before the
design is exercised increases risk without benefit.

## References

- L2 design doc §3 (context and binding constraints; reconciliation note)
- L2 design doc §13 (ADR register — this ADR)
- Cilium compatibility matrix: https://docs.cilium.io/en/stable/network/kubernetes/compatibility/
- ADR-0003 (Kubernetes version — 1.34.8)
- ADR-0025 (BGP control plane — v2 CRD dependency)
- ADR-0027 (Egress Gateway — GA dependency)
