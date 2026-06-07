# ADR-0017: kube-proxy skipped at kubeadm init

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.2
- **Supersedes:** none
- **Superseded by:** none

## Context

The locked stack runs Cilium in `kubeProxyReplacement=true` mode, where
Cilium's eBPF dataplane fully replaces kube-proxy for service routing.
kubeadm installs kube-proxy as an addon by default. Having both kube-proxy
and Cilium kube-proxy-replacement active simultaneously is unsupported and
produces undefined service routing behaviour. The choice is when to remove
kube-proxy: never install it, or install it at init and remove it after
Cilium is up.

## Decision

`skipPhases: [addon/kube-proxy]` is set in `InitConfiguration` so
kube-proxy is never installed during `kubeadm init`. It is not installed
and subsequently removed — it is never present.

## Consequences

**Positive:**

- No teardown churn. Installing kube-proxy and removing it creates a window
  where service routing is in an intermediate state.
- The absence of kube-proxy is self-documenting: visible in the config file
  and confirmed via `kubectl -n kube-system get ds kube-proxy` (returns not
  found).
- Aligns with Cilium's documented greenfield path, which prescribes
  `--skip-phases=addon/kube-proxy` for new clusters.

**Negative:**

- L1.2 definition-of-done shifts. After `kubeadm init` the node is
  `NotReady`, CoreDNS pods are `Pending`, and there is no kube-proxy
  DaemonSet. This is the correct and expected state until Cilium is
  installed in L2. It is not a failure.
- Service networking is fully absent between init and CNI install. Any
  tooling that probes service endpoints in that window will fail by design.
- `kubeadm upgrade` for the 1.34→1.35 upgrade must also carry
  `skipPhases: [addon/kube-proxy]` (via `UpgradeConfiguration`) to prevent
  kube-proxy from being re-introduced.

## Alternatives considered

**Install kube-proxy, remove after Cilium.** Avoids the `NotReady`
definition-of-done shift at L1.2. Rejected: creates a transient state
where two service routing implementations coexist; the `ds/kube-proxy`
removal and iptables cleanup is additional churn that achieves the same
end state as skipping at init. Reserved only for managed Kubernetes
services that cannot control init phases.

## References

- Cilium kube-proxy-free documentation — https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/
