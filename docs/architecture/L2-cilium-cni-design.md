# L2 — Cilium CNI: Design

| Field            | Value                                                                                 |
|------------------|---------------------------------------------------------------------------------------|
| **Layer**        | L2 (CNI install — node `NotReady` → `Ready`)                                           |
| **Status**       | Accepted (2026-06-07); amended 2026-11-17 for the version re-baseline (ADR-0029..0031) |
| **Date**         | 2026-06-07                                                                             |
| **Deciders**     | Nusrat Ullah                                                                           |
| **Depends on**   | L1.2 (kubeadm), ADR-0016..0019                                                         |
| **Produces**     | ADR-0022..0028, ADR-0030, ADR-0031 (see §13)                                           |
| **Reconciled**   | Parent CNI design doc read (2026-06-08): adopts native routing, rejects tunnel — inference confirmed. Refinements folded in: pod CIDR `100.64.0.0/14`, Egress Gateway + L2-announcements enabled, `autoDirectNodeRoutes` on all shapes, PodCIDR not BGP-advertised, Multus retirement flagged (§5, §9, §12). |

---

## 1. Purpose & scope

L2 installs **Cilium 1.20.4** as the cluster CNI. kube-proxy was skipped at init (ADR-0017), so Cilium runs in kube-proxy-replacement mode and the node transitions `NotReady` → `Ready` once the agent is healthy.

**In scope**
- Cilium install via Helm, pinned, with committed per-shape values.
- Gateway API CRDs pre-installed (prerequisite for `gatewayAPI.enabled`).
- Feature *enablement*: kube-proxy-replacement, cluster-pool IPAM, native routing, Hubble (relay + UI), Gateway API, BGP control plane.
- The `cilium` GatewayClass and an enabled-but-dormant BGP control plane.
- A `PRIVILEGED_EXCEPTIONS.md` entry for the Cilium agent (§12).

**Out of scope (deferred, with destination)**
- Runtime network objects — `CiliumBGPClusterConfig` / `CiliumBGPPeerConfig` / `CiliumBGPAdvertisement`, `CiliumLoadBalancerIPPool`, `Gateway` / `HTTPRoute`, `CiliumNetworkPolicy` → **`gitops/`, L4a** (Flux), or applied per consuming workload. "Opt-in per workload" = these do not exist until something needs them.
- Multus secondary networks (SR-IOV, IPsec underlay path to an external security gateway) → later layer (§12, forward dependency).
- HA secondary control-plane join + apiserver VIP → deferred (L1.2 carry-forward; affects `k8sServiceHost` for `ha-bare-metal`).
- CI workflow → deferred (flagged industry-standard to add before project end).

**Milestone target.** L2 is exercised and signed off on **`lab-single-node`**. The design is complete for all three shapes; `edge-site` and `ha-bare-metal` are deployed when their environments exist.

---

## 2. Definition of Done

Verified on `lab-single-node` (`192.0.2.10`):

| Check | Command | Expected |
|-------|---------|----------|
| Node Ready | `kubectl get nodes` | `lab-node-01 Ready control-plane <age> v1.36.6` |
| Agent healthy | `kubectl -n kube-system get pods -l k8s-app=cilium` | `Running 1/1` |
| Operator healthy | `kubectl -n kube-system get pods -l io.cilium/app=operator` | `Running` (replicas=1 this shape) |
| Hubble relay | `kubectl -n kube-system get pods -l k8s-app=hubble-relay` | `Running` |
| Hubble UI | `kubectl -n kube-system get pods -l k8s-app=hubble-ui` | `Running` |
| GatewayClass | `kubectl get gatewayclass cilium` | `ACCEPTED=True` |
| Datapath | `kubectl -n kube-system exec ds/cilium -- cilium-dbg status \| grep -E 'KubeProxyReplacement\|Routing\|Masquerading\|BGP'` | KPR `True`; Routing `Native`; Masquerading `BPF ... 100.64.0.0/14`; BGP Control Plane `enabled` (no peers) |
| Connectivity | two test pods + `kubectl exec` ping + DNS lookup | success |

**Failure modes to expect:** agent `CrashLoopBackOff` with API-server connectivity errors → `k8sServiceHost`/`k8sServicePort` wrong (the kube-proxy-free bootstrap trap). Operator `Pending` → `replicas` > node count without enough nodes (lab must be `1`). GatewayClass absent → Gateway API CRDs not present *before* the operator booted (§8 ordering). DNS failures → CoreDNS rescheduled but masquerade/native-CIDR mismatch.

---

## 3. Context & binding constraints

Confirmed inputs (re-baselined 2026-11-17, ADR-0029): K8s `1.36.6`; containerd `2.3.6`; node subnet `192.0.2.0/24`; service CIDR `10.96.0.0/12`; kube-proxy skipped (ADR-0017); `podSubnet` omitted from `ClusterConfiguration` (ADR-0019); cgroup driver from CRI (ADR-0018); pause `registry.k8s.io/pause:3.10.2`.

Constraints from the reference workload's internal design docs (a telco reverse-proxy and its backend gateway; kept local, not committed) that shaped the datapath decision:
- LoadBalancer service VIPs are **BGP-advertised** to the network; rollback withdraws the route via BGP.
- Cilium **≥1.16 with BGP + Gateway API + NetworkPolicy** is a stated prerequisite.
- **Multi-AZ** pod placement is required.
- Application pods **originate IPsec/ESP directly to an external security gateway**, bypassing the north-south proxy.
- East-west service load-balancing across ≥3 backend pods runs through Cilium kube-proxy-replacement; it can be stateless because a distributed session registry removes the need for session affinity.

**Reconciliation — resolved.** The parent CNI design doc has now been read. It **adopts native routing and explicitly rejects tunnel/overlay** (double-encapsulation, hidden pod identity, MTU cost on large transfers) — the same reasoning given here, so the inference is confirmed, not overturned. The parent doc also pins specifics folded into this revision: a single cluster-wide pod CIDR (no Multi-Pool), per-segment LB pools advertised by BGP, **PodCIDR kept cluster-internal (not BGP-advertised)**, Cilium **Egress Gateway** for VLAN-pinned pod egress (replacing Multus), and L2 announcements as a per-segment fallback. Its version baseline (Cilium 1.16 LTS, K8s 1.28–1.30) is older than ours; we track the current Cilium stable line (ADR-0030).

---

## 4. Integration model — two-plane split

**Bootstrap (Ansible) owns the install; `gitops/` (Flux, L4a) owns runtime objects.**

| Plane | Owns | Why |
|-------|------|-----|
| **Bootstrap** (`bootstrap/roles/cilium_install`) | Gateway API CRDs; Cilium Helm release + all feature-flag values | The CNI is a day-0 dependency of the cluster being usable *and* of Flux running at all (Flux pods need a CNI to get IPs). It cannot live in Flux. |
| **GitOps** (`gitops/`, L4a) | BGP CRs, LB-IPAM pools, Gateways/Routes, NetworkPolicies | These churn and benefit from reconciliation/drift-detection; they are not bootstrap-critical. |

**Mechanism:** `kubernetes.core.helm` (collection pinned at `6.6.0`; Helm 4 needs 6.5.0 or later), committed per-shape values files (no `--set` soup), chart pinned to `1.20.4`, image digests pinned in `versions.yml`. **Helm runs from the first control-plane node** (kubeconfig already at `~/.kube/config`; `run_once`). `cilium-cli` is rejected — it obscures what is deployed and is awkward to template per shape.

**Trade given up:** Cilium's own feature-flag config is not GitOps-reconciled — changes are an Ansible run, not a git commit. Accepted: this is the standard bare-metal pattern, and for Kubernetes minor upgrades (ADR-0029), a deliberate documented bootstrap operation is preferable to a silent HelmRelease bump. → **ADR-0023.**

---

## 5. Datapath architecture — native routing (headline)

**Decision: `routingMode: native` on every shape**, with `autoDirectNodeRoutes` and BGP activation as per-shape additive knobs. → **ADR-0022.**

**Rationale.** BGP is in the production reference design, not "later." With native routing, adding BGP is purely additive (apply CRs; the datapath never changes) — directly satisfying the "internal routing + BGP with minimal changing/debugging" requirement. Native is also the telco-standard primary datapath (Cilium native+BGP primary, Multus/SR-IOV secondary for the user plane) and the BGP-coherent choice: advertising pod/LB prefixes over BGP only makes sense without encapsulation. The pod-originated IPsec/ESP egress to an external security gateway reinforces it — ESP (IP proto 50, no ports) through a VXLAN overlay + SNAT requires stacking NAT-T under encapsulation, which is fragile to operate and capture; native gives clean L3 egress.

**Tunnel rejected.** Incoherent with BGP-advertised pod routes across AZs; starting flat-on-tunnel and later needing BGP pod routing is a *disruptive* `routingMode` switch (the churn we want to avoid); encapsulation overhead/reduced MTU hurts signaling latency; pod IPs not natively routable, which fights external network-element integration. Tunnel is retained only as a documented fallback for a degenerate case (flat, multi-subnet, no router, no BGP) — not the trajectory.

**Cross-node reachability** under native routing is satisfied two ways, and this is the crux of "flat + telco-grade from one design":
- **Cross-node pod routing** uses `autoDirectNodeRoutes: true` — Cilium installs a route to each node's pod CIDR via that node's IP. This works when nodes share an L2 node/trunk network, which the parent design assumes (all nodes on a bonded 802.1Q trunk). No overlay, and **the PodCIDR is *not* advertised by BGP** — it stays cluster-internal, a deliberate security property (pods are not reachable or scannable from the fabric).
- **BGP advertises LoadBalancer IP pools only** (per-segment), never the PodCIDR. So on multi-node shapes the BGP control plane is *active for LB-IP advertisement*, not for pod routing. If a future deployment ever places nodes on genuinely L3-separated segments with no shared node L2, pod routing would then need BGP-distributed pod routes — recorded as a fallback, not the default.

**Masquerade.** `bpf.masquerade: true` (eBPF; requires kube-proxy-replacement). Traffic staying inside `ipv4NativeRoutingCIDR` routes direct; traffic leaving it SNATs to the node IP. `bpf.hostLegacyRouting: false` (BPF host routing — the 1.20.4 chart leaves the key unset and documents `false` as the default; pinned explicitly regardless).

**Datapath mode.** `bpf.datapathMode: veth`, set explicitly (ADR-0030). Cilium 1.20 adds an `auto` mode that selects netkit on kernel 6.8 or later, which the lab node runs. The chart default is still `veth`, but the 1.20 notes say it may change, so the mode is pinned. netkit is a later per-shape decision.

---

## 6. IPAM & addressing

Cluster-pool IPAM (ADR-0019). → CIDR selection is **ADR-0026.**

| Setting | Value | Note |
|---------|-------|------|
| `ipam.mode` | `cluster-pool` | ADR-0019 |
| `ipam.operator.clusterPoolIPv4PodCIDRList` | `[100.64.0.0/14]` | RFC 6598 shared-address space (authority-aligned); disjoint from the RFC 1918 fabric; clear of lab service `10.96.0.0/12` and node `192.0.2.0/24` |
| `ipam.operator.clusterPoolIPv4MaskSize` | `24` | 254 pods/node |
| `ipv4NativeRoutingCIDR` | `100.64.0.0/14` | **must equal** the pod supernet; case-sensitive key |

Single-node note: with one node, only one `/24` is carved; cross-node routing is moot.

---

## 7. Helm values (designed)

> Version/digest fields are filled at the `chore(versions): pin cilium` commit (see §14). Do not invent digests — capture via a cosign-verified `helm pull` / image inspection at pin-time. Reconfirm the latest `1.20.x` patch and that every key/default below matches `helm show values cilium/cilium --version <pin>` before writing the role.
>
> **Render gate (ADR-0030).** Every key below changed the `helm template` output of chart `1.20.4` when its value was changed (run 2026-11-17). Two keys from the earlier revision did not and were removed: `egressGateway.installRoutes` and `externalIPs.enabled`. Rerun the gate whenever the chart version changes.

### 7.1 Common (all shapes)

```yaml
kubeProxyReplacement: true            # kube-proxy skipped at init (ADR-0017)

ipam:
  mode: cluster-pool                  # ADR-0019
  operator:
    clusterPoolIPv4PodCIDRList:
      - 100.64.0.0/14                 # RFC 6598; disjoint from RFC 1918 fabric (ADR-0026)
    clusterPoolIPv4MaskSize: 24

# Datapath — native routing (ADR-0022)
routingMode: native
ipv4NativeRoutingCIDR: 100.64.0.0/14  # == pod supernet; PodCIDR is NOT BGP-advertised (§5/§9)
autoDirectNodeRoutes: true            # cross-node routing via node L2-adjacency (all shapes)
bpf:
  masquerade: true
  hostLegacyRouting: false
  datapathMode: veth                  # explicit; 1.20 adds auto/netkit (ADR-0030)

l7Proxy: true                         # required by Gateway API (default on; pinned explicit)

loadBalancer:
  algorithm: maglev                   # consistent hashing (authority default); DSR/XDP are per-shape (§7.2)

gatewayAPI:
  enabled: true                       # CRDs pre-installed before this runs (§8)

# Feature control planes ON, runtime CRs deferred (enable-dormant; ADR-0025, ADR-0027)
bgpControlPlane:
  enabled: true                       # advertises LB-IP pools only; zero CRs = dormant
egressGateway:
  enabled: true                       # VLAN-pinned pod egress; CiliumEgressGatewayPolicy CRs deferred
l2announcements:
  enabled: true                       # LB-IP fallback for BGP-less segments; CRs deferred

hubble:
  relay:
    enabled: true
  ui:
    enabled: true
  metrics:
    enableOpenMetrics: true
    enabled: [dns:query;ignoreAAAA, drop, tcp, flow, icmp, http]   # to Prometheus at a later layer
  tls:
    auto:
      enabled: true
      method: helm                    # self-signed at install (lab-grade)

image:
  # repository + digest pinned via versions.yml (cilium.*); cosign-verified pull
  pullPolicy: IfNotPresent
```

### 7.2 Per-shape overrides

```yaml
# lab-single-node
k8sServiceHost: "192.0.2.10"
k8sServicePort: 6443
operator:
  replicas: 1
# autoDirectNodeRoutes is common (true) — no-op at 1 node
```
```yaml
# edge-site  (1 CP + 2–3 workers)
k8sServiceHost: "<control-plane node IP>"
k8sServicePort: 6443
operator:
  replicas: 2
```
```yaml
# ha-bare-metal  (3 CP + 3+ workers, production fabric)
k8sServiceHost: "<apiserver VIP>"      # HA front-end for the API (HA/L6 concern; deferred)
k8sServicePort: 6443
operator:
  replicas: 2
# Production LB datapath tuning (authority §7.5) — add when this shape is built:
loadBalancer:
  mode: dsr                           # Direct Server Return — preserves client source IP
  dsrDispatch: opt                    # IP-option dispatch
  acceleration: native                # XDP — REQUIRES NIC driver support; verify (omit on VMs)
  l7:
    backend: envoy
```

---

## 8. Gateway API — prerequisite & ordering

Gateway API CRDs **must be present before the Cilium operator starts**, or the operator errors and never creates the `cilium` GatewayClass (cilium/cilium#42179). → **ADR-0031** (supersedes ADR-0024).

- Pin **Gateway API v1.6.3**, standard channel (`standard-install.yaml`). Cilium 1.20 requires v1.6.1 or later and 1.20.4 is built against v1.6.3. Required CRDs: `GatewayClass`, `Gateway`, `HTTPRoute`, `GRPCRoute`, `ReferenceGrant`, `BackendTLSPolicy`, `TLSRoute` (`TLSRoute` is `v1` and in the standard channel from v1.6.1). The bundle also carries the optional `ListenerSet`, `TCPRoute` and `UDPRoute` CRDs and a `safe-upgrades` ValidatingAdmissionPolicy; the whole bundle is applied.
- **Fetch the pinned manifest at install time; do not vendor it** (ADR-0031). `ansible.builtin.get_url` downloads `gateway_api.manifest_url` to the first control-plane node with `checksum: gateway_api.checksum` (sha256, pinned in `versions.yml`), then `kubernetes.core.k8s` applies it with server-side apply. The bundle is about 1.2 MB, over the repo's 500 KB large-file hook, and the checksum gives the integrity a vendored copy would. Trade: the first bootstrap needs GitHub reachable from the node.
- Role ordering: apply CRDs → wait for `Established` → then the Cilium Helm release.
- L2 deliverable is the `cilium` GatewayClass (`ACCEPTED=True`). Actual `Gateway`/`HTTPRoute` objects are deferred (gitops/L4a). A `Gateway` needs a routable external IP — on flat shapes via LB-IPAM + L2 announcements, on routed shapes via BGP — that is the runtime half, deferred (§12).

---

## 9. BGP control plane — enabled, dormant

`bgpControlPlane.enabled: true`, **zero CRs at L2**. → **ADR-0025.**

- API is **`cilium.io/v2`** (`CiliumBGPClusterConfig`, `CiliumBGPPeerConfig`, `CiliumBGPAdvertisement`); `v2alpha1 CiliumBGPPeeringPolicy` (v1) is deprecated and not used. The parent doc's listings show `v2alpha1` because it targets Cilium 1.16; on 1.20 several of these CRDs have graduated to `v2` — **verify each CR's apiVersion against 1.20 when the runtime objects are written**, don't copy the doc's v2alpha1 verbatim.
- BGP advertises **LoadBalancer IP pools only** (per-segment, label-selected, typically one advertisement per segment with a distinguishing BGP community). **PodCIDR is never advertised** (§5). Runtime objects — per-segment `CiliumLoadBalancerIPPool` + `CiliumBGPClusterConfig`/`PeerConfig`/`Advertisement` — are GitOps/L4a or per-workload, not built here.
- So on multi-node shapes the control plane is *active for LB-IP advertisement*; it is dormant only where there is nothing to advertise (e.g. `lab-single-node`). Peering needs an upstream BGP speaker (ToR), so it activates when that fabric exists.
- Inspect BGP state with `cilium shell -- bgp/*`. Listing peers and routes with `cilium-dbg bgp` is deprecated in 1.20 (ADR-0030).

---

## 10. Bootstrap role & sequence

New role `bootstrap/roles/cilium_install` (same structure as existing roles: `defaults/`, `meta/`, `tasks/`, `templates/`, `molecule/`, `README.md`). New play in `site.yml` after `kube_bootstrap`.

Task flow (run on first control-plane node, `run_once`):
1. **Install Helm 4.x** (pinned tarball + SHA256 from `versions.yml:helm`) if absent. `kubernetes.core.helm` requires the binary present on the target.
2. **Apply Gateway API CRDs** (fetched with a pinned checksum) via `kubernetes.core.k8s` with server-side apply; wait for `Established`.
3. **`kubernetes.core.helm`** install/upgrade `cilium` `1.20.4` — values = common + shape file; namespace `kube-system`.
4. **Wait** for `cilium` DaemonSet + `cilium-operator` rollout (generous timeouts — HDD VM, large image pulls).
5. **Assert** the §2 DoD gates.

HDD accommodation: optionally pre-pull the Cilium agent/operator images on the node (mirrors the `kube_install` image pre-pull pattern) to keep the Helm wait inside its timeout on slow disk.

Tag hygiene: use scoped tags (`cilium_install`, `cilium_config`) — do not reuse the generic `config`/`install` tags (the L1.2 tag-bleed carry-forward).

---

## 11. Per-shape matrix

| | `lab-single-node` | `edge-site` | `ha-bare-metal` |
|---|---|---|---|
| `routingMode` | native | native | native |
| `autoDirectNodeRoutes` | true (no-op) | true | true |
| BGP control plane | enabled, dormant | enabled, dormant | enabled; **active — LB-IP advertisement** |
| Egress Gateway / L2-announce | enabled, dormant | enabled, dormant | enabled; runtime CRs at L4a |
| `k8sServiceHost` | `192.0.2.10` | CP node IP | apiserver VIP (deferred) |
| `operator.replicas` | 1 | 2 | 2 |
| LB datapath | defaults | defaults | maglev + DSR + XDP\* |
| Cross-node pods | n/a | autoDirectNodeRoutes | autoDirectNodeRoutes (node L2-adjacency) |
| Deploy status | **milestone** | when env exists | when env exists |

**Decided (per the parent design):** all shapes use `autoDirectNodeRoutes: true` (nodes share an L2 node/trunk network); PodCIDR is never BGP-advertised; BGP carries LB-IP pools only. `\*` `loadBalancer.acceleration: native` (XDP) requires NIC driver support — verify per environment; omit on VMs.

---

## 12. Hardening & forward dependencies

**Privileged exception (a deliverable of L2).** The Cilium **agent** requires `privileged: true` + `hostNetwork: true` + `NET_ADMIN`/`SYS_MODULE` to program the eBPF datapath — the canonical exception in HARDENING.md (§4 / Example A). Add a `PRIVILEGED_EXCEPTIONS.md` entry: component, namespace (`kube-system`), capabilities, **pinned image digest**, justification. The `cilium-operator`, `hubble-relay`, and `hubble-ui` are **not** privileged. Enforcement (Kyverno) lands at L3; the documented exception is created now.

**Forward dependencies (logged, owned by later layers):**
- **CNI design doc reconciliation** — native is decided on constraints; confirm against the parent doc (§3, §5).
- **Multus retirement (decision needed).** The parent design **removes Multus entirely** — single-CNI Cilium, with VLAN-pinned pod egress handled by **Cilium Egress Gateway** (`CiliumEgressGatewayPolicy`, SNAT on designated gateway nodes) and ingress by per-segment LB Services. This **conflicts with the locked-stack "Multus thick daemonset"** assumption. Decision: drop Multus from the roadmap, or keep it only for a hypothetical SR-IOV/DPDK *user-plane* the current workload does not have (its traffic is control/management-plane). My read: follow the authority and drop Multus unless a line-rate dataplane workload appears.
- **Pod-originated IPsec/ESP egress** — resolved by the above: it egresses via Egress Gateway pinned to the correct segment (not a Multus secondary). Runtime `CiliumEgressGatewayPolicy` + designated egress nodes → L4a/runtime.
- **HA secondary control-plane join + apiserver VIP** — `kubeadm join --control-plane` for cp2/cp3 and the API VIP that `k8sServiceHost` points to for `ha-bare-metal`. → HA work (L1.2 carry-forward).
- **Runtime network objects** (BGP peering/advertisements, LB-IPAM pools, Gateways/Routes, NetworkPolicies) → gitops/L4a.
- **LB-IP delivery for Gateways** — L2 announcements (flat) vs BGP (routed). → with the Gateway objects.

---

## 13. ADR register (this layer)

Numbers continue from ADR-0021. Each ADR is written with its implementation slice (§14), in the ADR-0006 format.

| ADR | Decision |
|-----|----------|
| **0022** | Cilium datapath: native routing on all shapes; `autoDirectNodeRoutes`/BGP activation as per-shape additive knobs. Tunnel retained as documented fallback. |
| **0023** | Cilium delivery: Helm via `kubernetes.core.helm` from the first CP node; two-plane split (install in bootstrap, runtime CRs in gitops/L4a); `cilium-cli` rejected. |
| **0024** | Gateway API CRDs pinned (v1.4.1, standard channel), vendored, applied before the Cilium operator boots. **Superseded by ADR-0031.** |
| **0025** | BGP control plane enabled but dormant at L2; `cilium.io/v2` API; runtime peering deferred. |
| **0026** | Pod CIDR `100.64.0.0/14` (RFC 6598, `/24` per node), `ipv4NativeRoutingCIDR` coupled; disjoint from the RFC 1918 fabric; collision-checked vs lab service `10.96.0.0/12` and node `192.0.2.0/24`. |
| **0027** | Egress Gateway + L2 announcements enabled at install (dormant); runtime CRs deferred. PodCIDR not BGP-advertised; BGP carries LB-IP pools only. **Amended by ADR-0030** (no `installRoutes` key). |
| **0028** | Adopt Cilium **1.19.x** over the parent design's 1.16 LTS — strict capability superset (BGP v2 GA CRDs, mature Egress Gateway), required for K8s 1.34; the doc's 1.16+ examples remain valid as a baseline. **Superseded by ADR-0030.** |
| **0030** | Adopt Cilium **1.20.x**, the line whose tested matrix lists K8s 1.36. `bpf.datapathMode: veth` pinned; dead keys `egressGateway.installRoutes` and `externalIPs.enabled` removed; render gate on values keys. Supersedes 0028; amends 0027. |
| **0031** | Gateway API CRDs pinned (v1.6.3, standard channel), fetched at install time with a pinned checksum (not vendored), server-side applied before the Cilium operator boots. Supersedes 0024. |

ADR-0029 (Kubernetes 1.36 re-baseline, containerd 2.3 LTS, version lifecycle policy) is repo-wide and is not an L2 record; it sets the inputs in §3.

---

## 14. Implementation slices (preview)

Built slice-by-slice after sign-off; each = code + its ADR, approved individually. The file-writing turns are mechanical → **drop to Sonnet**; design/correctness calls stay on the higher-capability model.

| Slice | Content | Commit type |
|-------|---------|-------------|
| A | Pin `cilium` (1.20.4 + chart + cosign-verified image digests) in `versions.yml`. `helm` (4.3.2), `cosign` (3.1.4) and `gateway_api` (v1.6.3) were pinned on 2026-11-17 | `chore(versions)` |
| B | `cilium_install` role scaffold + Helm-binary prereq task | `feat(cilium)` |
| C | Gateway API CRD apply task (pinned manifest, wait-for-Established) | `feat(cilium)` |
| D | Values templates (common + per-shape) + `kubernetes.core.helm` task | `feat(cilium)` |
| E | Verification gates + Molecule scenario (testable half) + `site.yml` play composition | `feat(cilium)` / `test` |
| F | `PRIVILEGED_EXCEPTIONS.md` Cilium-agent entry + ADR-0022..0026 | `docs(adr)` |

**Pre-flight before Slice A:** restore the user kubeconfig on the VM (`~/.kube/config` from `/etc/kubernetes/admin.conf`), and — if reachable — confirm the parent CNI doc does not contradict §5.

---

## 15. Roadmap gaps surfaced by the reference workload (beyond L2)

The reference workload's design docs name platform capabilities its modules hard-depend on that are **not on the current locked roadmap**. Recorded here for scoping — none are L2 work. "In-repo?" is a scope decision (flagged because the same engineer owns both platform and application); not added to L2.

| Capability | Driven by | In-repo? (recommendation) |
|---|---|---|
| **Observability stack** — Prometheus + Loki + Tempo, ServiceMonitor/PodMonitor CRDs | workload metrics/logs/traces requirements; Hubble metrics also target Prometheus | Likely yes, own layer — the workload can't meet its observability requirements without it. |
| **`metrics-server`** | HPA needs resource metrics | Yes — small, near-universal; pin like everything else. |
| **Certificate management / PKI** — cert-manager + issuer, or SOPS-managed certs | inter-module mTLS; cert-rotation runbook | Yes — decide cert-manager vs SOPS-managed. The mTLS mesh assumes it exists. |
| **Node topology/zone labels** (`topology.kubernetes.io/zone`) | multi-AZ anti-affinity / spread | Yes — fold into `ha-bare-metal` bring-up; trivial. |
| **SR-IOV / QAT device plugins + Multus** | only if a line-rate *user-plane* workload appears (the parent design retires Multus; current workload is control/management-plane, served by Egress Gateway) | **Likely drop** — revisit only for a future DPDK/SR-IOV dataplane. QAT needs kernel ≥5.17 (node runs 6.8 ✓). |
| **Stateful substrate** (Redis Cluster / etcd / Kafka) | distributed session registry, message bus | Mostly app-owned. Platform provides storage; note local-path-provisioner has no replication (already deferred to L4a). |

Suggested sequencing if adopted: PKI + observability + `metrics-server` are general-platform → their own layer(s) after Flux (L4a); SR-IOV/QAT → with Multus; node labels → with HA.
