# ADR-0027: Egress Gateway + L2 announcements enabled at install, dormant

- **Status** — Accepted
- **Date** — 2026-06-07
- **Deciders** — Nusrat Ullah
- **Layer** — L2
- **Supersedes** — none
- **Superseded by** — none
- **Amended by** — ADR-0030

## Context

Two Cilium features require both a Helm flag (set at install) and runtime CRs
(applied later) to be useful: **Egress Gateway** and **L2 announcements**.
The same enable-dormant reasoning from ADR-0025 (BGP) applies.

**Egress Gateway** (`egressGateway.enabled: true`, `installRoutes: true`).
The parent CNI design doc removes Multus from the stack and routes
VLAN-pinned pod egress via Cilium Egress Gateway instead
(`CiliumEgressGatewayPolicy`). This replaces the Multus secondary-network
pattern for pods that must originate traffic on a specific network segment
(e.g., pod-originated IPsec/ESP to an external security gateway). The
`installRoutes: true` sub-option is required so Cilium programs kernel
routes for egress traffic; without it the feature silently does nothing.

**L2 announcements** (`l2announcements.enabled: true`). Used as a per-segment
LB-IP fallback where BGP is unavailable (flat segments without a BGP
speaker). The feature is enabled globally; `CiliumL2AnnouncementPolicy` CRs
select which services and interfaces are announced. Without CRs, the feature
is dormant.

**PodCIDR advertisement policy.** PodCIDR (`100.64.0.0/14`) is
**never** BGP-advertised. Only per-segment `CiliumLoadBalancerIPPool`
ranges are advertised, and only once the BGP runtime CRs exist (L4a). This
is a deliberate security property: pods are not reachable or scannable from
the fabric.

## Decision

Common Helm values include:

```yaml
egressGateway:
  enabled: true
  installRoutes: true
l2announcements:
  enabled: true
```

**Zero runtime CRs** (`CiliumEgressGatewayPolicy`, `CiliumL2AnnouncementPolicy`)
are applied at L2. They are deferred to GitOps/L4a or applied per workload.

**PodCIDR is never BGP-advertised.** BGP carries LoadBalancer IP pool
prefixes only (per ADR-0025).

## Consequences

- `egressGateway.enabled` adds a small eBPF program overhead even with no
  policies. This is acceptable — the feature is production-standard on this
  platform, not experimental.
- `installRoutes: true` requires the Cilium agent to have the necessary
  capabilities to manage kernel routes. This is subsumed by the agent's
  existing privileged exception (§12 of the design doc; to be documented in
  `PRIVILEGED_EXCEPTIONS.md`).
- On `lab-single-node`, neither feature activates (no egress policy, no L2
  announcement policy). The DoD gate does not check for active policies;
  it checks only feature-plane health.
- If Multus is reintroduced for a future SR-IOV/DPDK user-plane workload, it
  does not conflict with Egress Gateway — they serve different traffic paths.

## Alternatives considered

**Disable at L2; Helm upgrade at L4a.** Rejected for the same reason as
ADR-0025: a Helm upgrade on a live cluster is avoidable churn. Enable at
install, apply CRs when needed.

**Keep Multus for VLAN-pinned egress.** Deferred: the parent design removes
Multus in favour of Egress Gateway for control/management-plane workloads.
Multus may be reconsidered only if a line-rate DPDK user-plane workload
appears (see §12 and §15 of the design doc). Until then, Egress Gateway
is the decided mechanism.

## References

- L2 design doc §5 (masquerade + PodCIDR not BGP-advertised)
- L2 design doc §7.1 (common Helm values)
- L2 design doc §12 (Multus retirement decision)
- ADR-0025 (BGP control plane — companion dormant enablement)
- ADR-0026 (pod CIDR — PodCIDR not advertised)
