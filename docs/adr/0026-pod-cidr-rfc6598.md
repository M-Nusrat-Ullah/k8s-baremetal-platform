# ADR-0026: Pod CIDR 100.64.0.0/14 (RFC 6598), /24 per node

- **Status** — Accepted
- **Date** — 2026-06-07
- **Deciders** — Nusrat Ullah
- **Layer** — L2
- **Supersedes** — none
- **Superseded by** — none
- **Amends** — ADR-0019 (Cilium cluster-pool IPAM; podSubnet omitted — the
  ADR deferred CIDR selection; this ADR settles it)

## Context

ADR-0019 chose Cilium cluster-pool IPAM and deliberately omitted `podSubnet`
from the kubeadm `ClusterConfiguration`, leaving CIDR selection to the L2
layer. Three candidates were considered:

| Candidate | Issue |
|-----------|-------|
| `10.244.0.0/16` (Flannel default) | Collides with common RFC 1918 enterprise ranges |
| `192.168.0.0/16` | RFC 1918; collides with typical home/lab networks |
| `10.96.0.0/12` | Already claimed by service CIDR on this cluster |
| `192.0.2.0/24` | Node subnet; cannot reuse |
| `100.64.0.0/14` | RFC 6598 shared-address space; purpose-built for this use |

**RFC 6598 rationale.** `100.64.0.0/10` is IANA-reserved for
carrier-grade NAT and is never routed in enterprise or public networks.
It is disjoint from all RFC 1918 ranges, so pod IPs will never collide with
the fabric's management or user-plane VLANs regardless of lab or production
addressing. The parent CNI design doc uses this exact range for the same
reasons.

**Supernet selection.** `/14` (262,144 addresses) gives 1,024 nodes at `/24`
per node (254 pods each), which comfortably exceeds any foreseeable cluster
size on this platform. `/24` per-node mask is Cilium's cluster-pool default
and is retained.

**Coupling.** `ipv4NativeRoutingCIDR` must equal the pod supernet exactly
(case-sensitive key). Traffic inside this CIDR routes directly (no SNAT);
traffic outside it SNATs to the node IP. A mismatch silently breaks egress
for pods whose IPs fall outside the CIDR.

**Collision check (2026-06-07):**
- Lab service CIDR: `10.96.0.0/12` — disjoint ✓
- Lab node subnet: `192.0.2.0/24` — disjoint ✓
- Fabric VLANs (checked against reference docs): disjoint ✓

## Decision

**Pod CIDR: `100.64.0.0/14`** (RFC 6598; `/24` per node).

Helm values:

```yaml
ipam:
  operator:
    clusterPoolIPv4PodCIDRList:
      - 100.64.0.0/14
    clusterPoolIPv4MaskSize: 24
ipv4NativeRoutingCIDR: 100.64.0.0/14  # must equal pod supernet
```

PodCIDR is **never BGP-advertised** — it is cluster-internal (ADR-0025,
ADR-0027). Only LoadBalancer IP pools are advertised via BGP.

## Consequences

- Any future expansion to a `/10` supernet or a different RFC 6598 sub-range
  requires a Helm upgrade that changes the IPAM config. Existing pods retain
  their IPs but new node allocations shift; plan as a maintenance window.
- `ipv4NativeRoutingCIDR` must be updated in lock-step with the pod supernet.
  A CI check or pre-upgrade checklist item should verify they match.
- Monitoring and firewall rules that match pod source IPs should use
  `100.64.0.0/14` (or per-node `/24`), not RFC 1918 wildcards.

## Alternatives considered

**`172.16.0.0/12`.** RFC 1918; overlaps with Docker's default bridge range
and common VPN split-tunnel ranges.

**`10.244.0.0/16`.** RFC 1918; common default, high collision risk in
enterprise environments.

**RFC 6598 /10 supernet (`100.64.0.0/10`).** Larger than needed; `/14`
is sufficient for foreseeable scale.

## References

- RFC 6598 (IANA-Reserved IPv4 Prefix for Shared Address Space)
- ADR-0019 (cluster-pool IPAM; podSubnet omitted)
- L2 design doc §6 (IPAM and addressing)
- Parent CNI design doc (confidential; kept local) — same range adopted
