# ADR-0025: BGP control plane enabled but dormant at L2

- **Status** — Accepted
- **Date** — 2026-06-07
- **Deciders** — Nusrat Ullah
- **Layer** — L2
- **Supersedes** — none
- **Superseded by** — none

## Context

The platform's production reference design requires BGP-advertised
LoadBalancer VIPs. The BGP control plane must therefore be present in the
cluster; the question is when to activate peering and what CRD API version
to use.

**Activation timing:** enabling BGP at L2 but deferring the runtime CRs
(peer configs, advertisements, LB-IP pools) to GitOps/L4a is the standard
"enable-dormant" pattern. The feature flag must be set at Helm install time
and cannot be toggled without a Helm upgrade. Runtime CRs, by contrast,
can be applied at any time after the control plane is running.

**API version:** Cilium has two BGP CR generations:
- `v2alpha1` — `CiliumBGPPeeringPolicy` (Cilium ≤1.16 primary)
- `cilium.io/v2` — `CiliumBGPClusterConfig`, `CiliumBGPPeerConfig`,
  `CiliumBGPAdvertisement` (graduated in Cilium 1.17+; authoritative on 1.19)

The parent CNI design doc targets Cilium 1.16 and shows `v2alpha1` examples.
Those examples are **not** safe to copy for Cilium 1.19 without verifying
that the specific CR kind has graduated. The verified apiVersion for each CR
must be confirmed against the 1.19 CRD manifest at runtime-object write time.

**Scope on `lab-single-node`:** with no upstream BGP speaker (ToR), peering
never activates on the lab shape regardless of the feature flag. The control
plane is genuinely dormant until an environment with a BGP fabric exists.

## Decision

`bgpControlPlane.enabled: true` is set in the common Helm values for all
shapes. **Zero BGP CRs are applied at L2.**

Runtime objects (`CiliumBGPClusterConfig`, `CiliumBGPPeerConfig`,
`CiliumBGPAdvertisement`, `CiliumLoadBalancerIPPool`) are deferred to
GitOps/L4a or applied per-environment when the BGP fabric is available.

The `cilium.io/v2` API is authoritative for Cilium 1.19. When runtime
objects are written, each CR's `apiVersion` must be verified against the
actual 1.19 CRD manifest — do not copy `v2alpha1` from the parent doc.

## Consequences

- BGP-related errors (no peers configured) are expected and benign at L2.
  The DoD gate checks `BGP Control Plane: enabled (no peers)` in
  `cilium-dbg status`, not that peers are established.
- On `ha-bare-metal` (with a real ToR), the control plane transitions from
  dormant to active when `CiliumBGPClusterConfig`/`PeerConfig` CRs are
  applied at L4a. No Helm upgrade needed.
- If a future Cilium upgrade graduates another CR kind from `v2alpha1` to
  `v2`, existing `v2alpha1` CRs may continue working during a deprecation
  window but must be migrated. Keep CR versions auditable.

## Alternatives considered

**Disable BGP at L2; add a Helm upgrade at L4a.** Rejected: a Helm upgrade
is a disruptive operation that requires re-converging the role on a live
cluster. Setting the feature flag at install and deferring only the CRs
avoids that churn.

**Apply BGP peering CRs at L2.** Rejected: no BGP fabric exists on
`lab-single-node`; the CRs would be unapplied (no-op on lab) and would
clutter the install with runtime concerns that belong in GitOps.

## References

- L2 design doc §9 (BGP control plane)
- Cilium BGP control plane documentation (v2 CRDs): https://docs.cilium.io/en/stable/network/bgp-control-plane/
- ADR-0027 (Egress Gateway + L2 announcements — companion dormant enablement)
- ADR-0028 (Cilium version — 1.19.x)
