# ADR-0030: Adopt Cilium 1.20.x with veth datapath mode pinned

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** M Nusrat Ullah
- **Layer:** L2
- **Supersedes:** ADR-0028
- **Superseded by:** none
- **Amends:** ADR-0027 (drops the `egressGateway.installRoutes` value)

## Context

ADR-0028 pinned Cilium 1.19.x and deferred 1.20 until a deliberate upgrade
ADR. ADR-0029 moves the platform to Kubernetes 1.36. Cilium 1.19 lists
Kubernetes 1.32–1.35 as tested; Cilium 1.20 lists 1.33–1.36. Cilium 1.20
became generally available on 2026-07-29 and its current patch is 1.20.4.

Cilium has never been installed on this platform, so this is a fresh
install on 1.20, not an upgrade from 1.19.

The L2 design was reviewed against the Cilium 1.20 upgrade notes and
against the 1.20.4 chart:

- **Helm values.** No key used by the design was removed, renamed or given
  a different default between chart 1.19.10 and chart 1.20.4. This covers
  kube-proxy replacement, BGP control plane, LB-IPAM, L2 announcements,
  Egress Gateway and cluster-pool IPAM.
- **Datapath mode.** 1.20 adds `bpf.datapathMode=auto`, which selects
  netkit when the kernel supports it. The default stays `veth`, and the
  upgrade notes say it may change in a future release. netkit needs kernel
  6.8 or later, which the lab node runs.
- **Gateway API.** 1.20 requires Gateway API v1.6.1 or later. That is
  handled in ADR-0031.
- **Policy admission.** A `CiliumNetworkPolicy` or
  `CiliumClusterwideNetworkPolicy` with neither `spec` nor `specs` is now
  rejected at admission.
- **NodePort from pods.** With socket LB disabled, a pod connecting to a
  NodePort service is load-balanced as traffic leaves the client pod.
  Network policies must allow the client pod to reach the backends
  directly.
- **BGP tooling.** Listing peers and routes with `cilium-dbg bgp` is
  deprecated in favour of `cilium shell -- bgp/*`. BGP metrics replace the
  `vrouter` label with `instance_name`.

A render gate was run against chart 1.20.4: `helm template` with the
design's values, then one render per key with that key changed. Every key
changed the rendered output except two:

- `egressGateway.installRoutes`
- `externalIPs.enabled`

Neither key exists in the chart's `values.yaml` for 1.19.10 or 1.20.4, and
`installRoutes` is absent from the 1.20.4 values schema and config map
template. Helm ignores both silently.

## Decision

1. **Cilium 1.20.x** is the version line. The pin at the
   `chore(versions): pin cilium` commit is **1.20.4**. The chart version
   tracks the Cilium version one to one. The `cilium` and
   `cilium-operator` image digests are captured from a cosign-verified
   pull at pin-time, as ADR-0028 required. `cosign` is pinned in
   `versions.yml` as a control-node tool for that check. Cilium 1.21 and later need a
   new ADR.
2. **`bpf.datapathMode: veth` is set explicitly** in the common values.
   The design was drawn against veth, and an explicit pin stops a future
   default change from switching the datapath on a netkit-capable kernel.
   netkit is left as a later per-shape decision.
3. **`egressGateway.installRoutes` and `externalIPs.enabled` are removed**
   from the design's values. For ADR-0027 this means
   `egressGateway.enabled: true` stands and the `installRoutes` sub-option
   is dropped.
4. **Render gate.** Every key in the committed values files must change
   the `helm template` output of the pinned chart when its value is
   changed. The gate is rerun whenever the chart version changes.

## Consequences

**Positive:**

- The Cilium pin lists the pinned Kubernetes minor as tested.
- The values files carry no silently ignored keys.
- The datapath mode is a recorded choice, not an inherited default.

**Negative:**

- netkit's performance gain is not taken at L2.
- `helm show values cilium/cilium --version 1.20.4` replaces the 1.19
  chart as the authority for keys and defaults. Any value not confirmed
  against it is pinned explicitly, as before.

**Carried to later layers:**

- Runtime BGP runbooks use `cilium shell -- bgp/*`.
- Network policies written at L3 and L4a account for the admission rule
  and the NodePort behaviour above.
- With `hubble.tls.auto.method: helm`, Hubble certificates are valid for
  365 days and are regenerated only when the chart is rendered again.
- Each runtime CR's `apiVersion` is verified against the 1.20 CRD
  manifests when the runtime objects are written (ADR-0025).

## Alternatives considered

- **Cilium 1.19.10 with Kubernetes 1.35.** A supported pair. Rejected in
  ADR-0029: Kubernetes 1.35 is End of Life on 2027-02-28.
- **Cilium 1.19.10 with Kubernetes 1.36.** Rejected: 1.36 is outside the
  1.19 tested matrix.
- **`bpf.datapathMode: auto` or `netkit`.** Deferred. netkit requires eBPF
  host routing and is incompatible with `bpf.tproxy=true`. Adopting it
  before the design has been exercised once adds a variable without a
  workload that needs it.
- **Keep the two dead keys as documentation of intent.** Rejected: a
  values file that names options the chart ignores misleads the reader.

## References

- ADR-0028 — superseded by this record
- ADR-0027 — Egress Gateway and L2 announcements; amended by this record
- ADR-0029 — Kubernetes 1.36 re-baseline
- ADR-0031 — Gateway API CRDs for Cilium 1.20
- L2 design doc §5, §7, §9
- Cilium 1.20 upgrade notes:
  https://docs.cilium.io/en/v1.20/operations/upgrade/
- Cilium Kubernetes compatibility:
  https://docs.cilium.io/en/v1.20/network/kubernetes/compatibility/
