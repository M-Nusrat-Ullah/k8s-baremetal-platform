# ADR-0019: Cilium cluster-pool IPAM; podSubnet omitted from ClusterConfiguration

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.2
- **Supersedes:** none
- **Superseded by:** none

## Context

`ClusterConfiguration.networking.podSubnet` controls whether
kube-controller-manager allocates per-node pod CIDRs
(`--allocate-node-cidrs=true`). Cilium's IPAM mode determines whether
those allocations are used.

**Kubernetes IPAM** — Cilium reads `node.spec.podCIDR` allocated by
kube-controller-manager. Requires `podSubnet` to be set in kubeadm.

**Cluster-pool IPAM** (Cilium default) — Cilium manages a cluster-wide
pod CIDR pool and allocates per-node ranges itself.
`node.spec.podCIDR` is not used. `podSubnet` must be omitted so the
controller-manager does not attempt conflicting allocation.

The IPAM direction must be chosen at init time: changing from cluster-pool
to Kubernetes IPAM after the cluster is up requires recreation.

## Decision

Cilium will be deployed with cluster-pool IPAM. `podSubnet` is
intentionally omitted from `ClusterConfiguration`. `serviceSubnet` is set
explicitly to `10.96.0.0/12` (the kubeadm default, made explicit for
reviewability). The pod CIDR range is configured in Cilium's Helm values
at L2 via `ipam.operator.clusterPoolIPv4PodCIDRList`.

## Consequences

**Positive:**

- Cilium is the sole authority on pod addressing; no risk of CIDR
  allocation races between kube-controller-manager and Cilium.
- `--allocate-node-cidrs` is not set in the controller-manager, reducing
  its surface area.
- Compatible with Cilium BGP control plane (part of the locked stack):
  Cilium advertises pod CIDRs it allocated itself.

**Negative:**

- `node.spec.podCIDR` is not populated. Any tooling that reads this field
  will find it empty. Acceptable given the locked CNI stack.
- Changing to Kubernetes IPAM post-init requires cluster recreation.
  This ADR commits the IPAM direction.
- L2 Cilium Helm values must explicitly set
  `ipam.operator.clusterPoolIPv4PodCIDRList`; there is no kubeadm-provided
  default to fall back on.

## Alternatives considered

**Kubernetes IPAM (`podSubnet` set in kubeadm).** Populates
`node.spec.podCIDR` for tooling compatibility. Rejected: requires
kube-controller-manager involvement in pod CIDR allocation, which couples
two components unnecessarily; cluster-pool is Cilium's default and the
simpler path.

## References

- Cilium IPAM documentation — https://docs.cilium.io/en/stable/network/concepts/ipam/
