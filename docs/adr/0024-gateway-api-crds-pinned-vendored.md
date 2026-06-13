# ADR-0024: Gateway API CRDs pinned (v1.4.1, standard channel), vendored

- **Status** — Accepted
- **Date** — 2026-06-07
- **Deciders** — Nusrat Ullah
- **Layer** — L2
- **Supersedes** — none
- **Superseded by** — none

## Context

`gatewayAPI.enabled: true` is set in the Cilium Helm values (L2 design doc
§7.1). The Cilium operator checks for Gateway API CRDs at startup and
creates the `cilium` GatewayClass only when they are present. If the CRDs
arrive after the operator has already started, the GatewayClass is not
created — the operator must be restarted, which is avoidable toil
(cilium/cilium#42179).

Therefore, Gateway API CRDs must be applied and in `Established` state
before the Cilium Helm release is installed.

**Version selection:** Gateway API v1.4.1, standard channel
(`standard-install.yaml`). Standard channel provides: `GatewayClass`,
`Gateway`, `HTTPRoute`, `GRPCRoute`, `ReferenceGrant`. `TLSRoute` is
experimental-channel only; it is not installed here and can be added later
if a workload requires it. The version must be confirmed against what Cilium
1.19.x expects at pin-time (`helm show values cilium/cilium --version <pin>`
lists the expected CRD versions).

**Manifest sourcing:** applying a live release URL in a task is rejected —
the URL content can change between runs, making the deployment non-idempotent
and unreproducible. The manifest is vendored into the repo.

## Decision

Gateway API CRDs are pinned at **v1.4.1, standard channel**, and the
manifest is **vendored** at
`bootstrap/files/gateway-api/v1.4.1/standard-install.yaml`.

A `gateway_api` entry is added to `versions.yml` (version + manifest SHA256).

Role task order: apply CRDs → wait for `Established` condition on each CRD →
then install Cilium via Helm. The wait uses `kubernetes.core.k8s_info` with
a retrying condition check, not a bare sleep.

The L2 deliverable is the `cilium` GatewayClass (`ACCEPTED=True`). Actual
`Gateway` and `HTTPRoute` objects are runtime objects, deferred to gitops/L4a.

## Consequences

- The vendored manifest must be re-evaluated when upgrading Cilium; the CRD
  version expected by the operator may change between Cilium minor versions.
  A version mismatch leaves the GatewayClass absent; the `kubectl get
  gatewayclass cilium` DoD gate will catch it.
- Vendoring adds ~100 KB to the repository but eliminates external-URL
  fragility and makes every deployment auditable from git.
- A `Gateway` object needs a routable external IP (L2 announcements on flat
  shapes, BGP on routed shapes). That is the runtime half, deferred.

## Alternatives considered

**Apply the live release URL.** Rejected: non-idempotent, unreproducible,
breaks in air-gapped environments, and fails silently if the URL content
changes.

**Skip Gateway API at L2; enable later.** Rejected: `gatewayAPI.enabled`
forces the operator to create the GatewayClass at startup; retrofitting
CRDs after the operator booted requires an operator restart. Cleaner to do
it right at day-0.

**Experimental channel.** Rejected: adds TLSRoute and other alpha-grade
CRDs not required by any current workload; standard channel is sufficient
and more stable.

## References

- L2 design doc §8 (Gateway API prerequisite and ordering)
- Cilium issue #42179 (operator timing dependency)
- Gateway API releases: https://github.com/kubernetes-sigs/gateway-api/releases
