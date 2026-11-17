# ADR-0031: Gateway API CRDs pinned at v1.6.3, standard channel, fetched with a checksum

- **Status:** Accepted
- **Date:** 2026-11-17
- **Deciders:** M Nusrat Ullah
- **Layer:** L2
- **Supersedes:** ADR-0024
- **Superseded by:** none

## Context

ADR-0024 pinned Gateway API v1.4.1, the version Cilium 1.19 supports.
ADR-0030 moves the platform to Cilium 1.20.

Cilium 1.20 requires Gateway API v1.6.1 or later, because `TLSRoute` moved
from `v1alpha2` to `v1` in that release and Cilium needs the `v1` version
served. Cilium 1.20.4 is built and documented against Gateway API v1.6.3.

The set of CRDs that Cilium 1.20 requires is larger than under 1.19:

| CRD | Cilium 1.20 |
| --- | ----------- |
| `GatewayClass`, `Gateway`, `HTTPRoute`, `GRPCRoute`, `ReferenceGrant` | required |
| `BackendTLSPolicy`, `TLSRoute` | required (new since ADR-0024) |
| `ListenerSet`, `TCPRoute`, `UDPRoute` | optional; support is enabled only when the CRD is present |

The v1.6.3 `standard-install.yaml` contains all ten CRDs. It also contains
a `ValidatingAdmissionPolicy` and binding named
`safe-upgrades.gateway.networking.k8s.io`.

Gateway API v1.7.0 was released on 2026-10-29. Cilium 1.20 does not target
it.

No Gateway API objects exist on the platform. The upgrade-note warning
about existing `v1alpha2` `TLSRoute` objects becoming unreadable does not
apply to a fresh install.

ADR-0024 vendored the manifest so the bootstrap would not depend on a live
URL. The v1.6.3 bundle is about 1.2 MB, over the 500 KB limit of the
repository's large-file hook, and lint hooks would also need path
exclusions for a file this repository does not author. A pinned checksum
gives the same integrity guarantee without storing the file.

## Decision

Gateway API CRDs are pinned at **v1.6.3, standard channel**. The manifest is
**not vendored**: the role fetches it from the upstream release at install
time and verifies it against a pinned checksum.

- The `gateway_api` entry in `versions.yml` records `version`,
  `manifest_url` and `checksum` (`sha256:` of `standard-install.yaml`).
- The role downloads the manifest to the first control-plane node with
  `ansible.builtin.get_url` and the `checksum` parameter. A tampered or
  truncated download fails the task; nothing is applied from an unverified
  file.
- The whole bundle is applied as one artifact, including the optional CRDs
  and the admission policy, with **server-side apply**, as the Cilium 1.20
  installation instructions do. It is not split into per-CRD files.
- Role task order: fetch the manifest with its checksum, apply the CRDs,
  wait for the `Established` condition on each CRD with a retrying
  `kubernetes.core.k8s_info` check, then install Cilium with Helm.
- **Version coupling.** The Gateway API pin follows the Cilium pin. It is
  the version the pinned Cilium patch is built against. Changing either
  pin means rechecking the other.

The L2 deliverable is unchanged: the `cilium` GatewayClass with
`ACCEPTED=True`. `Gateway` and route objects remain runtime objects,
deferred to gitops/L4a.

## Consequences

**Positive:**

- The applied manifest is bit-exact and pinned by checksum, the same
  guarantee a vendored copy gave.
- No 1.2 MB file in the repository, and no exclusions for the large-file,
  yamllint or ansible-lint hooks.
- A Gateway API bump is three values in `versions.yml`.
- `TLSRoute` is available from the standard channel, so the experimental
  channel is not needed for it.

**Negative:**

- The first bootstrap needs the release host reachable from the
  control-plane node. A vendored copy did not. An air-gapped install needs
  a mirror and a changed `manifest_url`.
- If upstream replaces the release asset, the checksum fails the task; if
  it removes the asset, the fetch fails. Either stops the bootstrap before
  anything is applied.
- The optional `ListenerSet`, `TCPRoute` and `UDPRoute` CRDs are present,
  so Cilium enables support for them although nothing uses them yet.
- The bundle installs an admission policy that this platform did not
  author.

## Alternatives considered

- **Vendor the manifest in the repository** (ADR-0024). Rejected: about
  1.2 MB, over the large-file hook, and the lint hooks would need
  exclusions. The checksum already gives the integrity benefit.
- **Fetch without a checksum.** Rejected: an unverifiable download applied
  to the cluster.
- **Gateway API v1.6.1**, the stated minimum. Rejected: the pinned Cilium
  patch is built against v1.6.3, and the later patch carries fixes.
- **Gateway API v1.7.0.** Rejected: Cilium 1.20 does not target it.
- **Experimental channel.** Rejected: no workload needs an experimental
  resource or field.
- **Apply only the seven required CRDs from per-CRD files.** Rejected:
  seven downloads and seven checksums in place of one, to avoid three
  unused CRDs.

## References

- ADR-0024 — superseded by this record
- ADR-0030 — Cilium 1.20.x
- L2 design doc §8
- Cilium 1.20 Gateway API support:
  https://docs.cilium.io/en/v1.20/network/servicemesh/gateway-api/gateway-api/
- Gateway API v1.6.3:
  https://github.com/kubernetes-sigs/gateway-api/releases/tag/v1.6.3
