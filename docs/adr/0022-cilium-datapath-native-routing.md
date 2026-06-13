# ADR-0022: Cilium datapath — native routing on all shapes

- **Status** — Accepted
- **Date** — 2026-06-07
- **Deciders** — Nusrat Ullah
- **Layer** — L2
- **Supersedes** — none
- **Superseded by** — none

## Context

Cilium supports two primary routing modes: `tunnel` (VXLAN/Geneve overlay)
and `native` (direct L3, no encapsulation). The choice is a day-0 cluster
decision; switching `routingMode` later is a disruptive in-place migration.

The platform has three binding constraints that make the choice non-obvious:

1. **BGP LB-IP advertisement** — LoadBalancer service VIPs must be
   BGP-advertised to the fabric. Native routing keeps pod IPs as real L3
   addresses, making the BGP control plane coherent; tunnel mode requires
   routing the overlay and advertising VIPs through a separate mechanism.
2. **Pod-originated IPsec/ESP egress** — application pods open ESP sessions
   (IP proto 50, no port) directly to an external security gateway.
   NAT-T-under-VXLAN stacking is fragile; native gives clean L3 egress.
3. **Parent CNI design doc (confidential; read 2026-06-08)** — explicitly
   adopts native routing and rejects tunnel/overlay: double-encapsulation,
   hidden pod identity, and MTU penalty on large transfers are the
   documented objections. The inference made before reading the doc was
   confirmed, not overturned.

Cross-node pod reachability under native routing is provided by
`autoDirectNodeRoutes: true` — Cilium installs a host route for each
node's pod CIDR via that node's IP. This works on all shapes because every
node shares an L2 node/trunk network (bonded 802.1Q trunk per the parent
design). PodCIDR is not BGP-advertised — it remains cluster-internal, which
is a deliberate security property (pods are not reachable from the fabric).

## Decision

**`routingMode: native` on all shapes.**

`autoDirectNodeRoutes: true` is a common value (cross-node routing via L2
node-adjacency). BGP control-plane activation and XDP/DSR datapath tuning
are per-shape additive knobs (§7.2, §11 of the design doc) that do not
change the routing mode.

Tunnel mode is retained as a documented fallback for a degenerate case
(flat multi-subnet, no router, no BGP), but it is not the trajectory of
this platform and no shape is expected to need it.

## Consequences

- Node L2-adjacency is a hard assumption for `autoDirectNodeRoutes`. A
  future L3-separated topology (nodes on different L3 segments with no
  shared node L2) would require BGP-distributed pod routes as a fallback;
  that is recorded but not designed here.
- `bpf.masquerade: true` (eBPF masquerade, requires kube-proxy-replacement).
  Traffic inside `ipv4NativeRoutingCIDR` routes direct; traffic leaving it
  SNATs to the node IP.
- `bpf.hostLegacyRouting: false` (BPF host routing) — pinned explicitly
  even if it becomes the 1.19 default.
- XDP acceleration (`loadBalancer.acceleration: native`) requires NIC driver
  support; it is only added for `ha-bare-metal` and must be verified per
  environment (omit on VMs).

## Alternatives considered

**Tunnel (VXLAN/Geneve).** Rejected: incoherent with BGP-advertised pod
routes across AZs; a later routingMode switch would be disruptive; overhead
hurts latency; ESP-under-VXLAN+SNAT is operationally fragile. The parent
design explicitly rejects it.

**Hybrid (native for same-node, tunnel for cross-node).** Not a Cilium
option; Cilium's mode is cluster-wide.

## References

- L2 design doc §5 (datapath rationale)
- L2 design doc §11 (per-shape matrix)
- Parent CNI design doc (confidential; kept local)
