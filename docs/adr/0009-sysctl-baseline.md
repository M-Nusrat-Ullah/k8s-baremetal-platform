# ADR-0009: sysctl baseline for `os_prep`

- **Status:** Accepted
- **Date:** 2026-06-02
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1
- **Supersedes:** none
- **Superseded by:** none

## Context

The `os_prep` role (ADR-0004) sets kernel sysctls as one of its per-concern
slices (L1.1.3). ADR-0007 already settled the kernel-module half of this:
which modules load, why `br_netfilter` is kept under a Cilium eBPF datapath
that does not use it, and why the `kernel_modules` import is ordered before
this slice. This record does not revisit that.

What remains to decide is the sysctl set itself — specifically which key is
load-bearing, and which commonly-prescribed sysctls are deliberately left out.
The exclusions are the substance: this is where copied bring-up guidance does
real harm, and a decision that is not written down is a decision a future
tutorial will quietly overturn.

## Decision

Set exactly three keys via `os_prep_sysctl_settings`, written to one drop-in
(`/etc/sysctl.d/99-k8s.conf`) and applied with `ansible.posix.sysctl` per the
ADR-0004 mechanism, with live application guarded out of containers.

- **`net.ipv4.ip_forward = 1`** is the one load-bearing key. It is required
  for pod and cross-node routing, and unlike the bridge-netfilter checks
  (removed from kubeadm in PR #123464), the `ip_forward` preflight check is
  still enforced on the pinned 1.34 line. Cilium also sets forwarding itself,
  but the host baseline owns this key so the value is correct *before* kubeadm
  runs and independent of CNI install ordering.
- **`net.bridge.bridge-nf-call-iptables = 1`** and
  **`net.bridge.bridge-nf-call-ip6tables = 1`** are kept per ADR-0007:
  conventional baseline, inert under the eBPF datapath, dependent on
  `br_netfilter`. Not re-argued here.

The drop-in uses a `99-` prefix so it is applied after the distribution
defaults under `/usr/lib/sysctl.d/` and wins on any overlapping key.

### Deliberately excluded

- **`rp_filter`.** Cilium relaxes reverse-path filtering on its own managed
  interfaces (`lxc*`) by dropping its own sysctl file at agent start. The host
  baseline must not pre-empt that. The near-universal quickstart line
  `net.ipv4.conf.all.rp_filter = 0` (and the IPv6 equivalent) disables
  reverse-path filtering host-wide — a real security downgrade, and broader
  than Cilium itself asks for. Excluded.
- **IPv6 forwarding.** This platform is IPv4-only (L0).
  `net.ipv6.conf.all.forwarding = 1` belongs only in a dual-stack build, per
  the Kubernetes 1.34 dual-stack guide. It is a one-line addition to
  `os_prep_sysctl_settings` if and when dual-stack is adopted.
- **Node-tuning sysctls** (`fs.inotify.max_user_instances`,
  `fs.inotify.max_user_watches`, etc.). Some Cilium guides recommend raising
  these for file-watcher headroom, but they are node capacity tuning, not a
  Kubernetes node prerequisite, and folding them into the prerequisite drop-in
  muddies the slice's purpose. Out of scope; a separate decision if ever
  wanted.

## Consequences

**Positive:**

- The set is minimal and every key has a stated, correct reason.
- The exclusions are on record, so a future tutorial-driven `rp_filter = 0`
  (or a stray IPv6/inotify key) is caught in review rather than shipped.
- `ip_forward` correctness is guaranteed before kubeadm, regardless of when
  the CNI is installed.
- Going dual-stack is a one-line change to the variable.

**Negative:**

- The drop-in is a bare, module-managed file with no header or per-key
  comment, unlike the `kernel_modules` template. `ansible.posix.sysctl`
  (mandated by ADR-0004) owns the file and exposes no way to render comments,
  so the rationale lives in `defaults/main.yml` and this ADR instead. Accepted
  over bolting a second task onto one file.
- The bridge keys remain inert baseline under Cilium — a cost already accepted
  in ADR-0007.

## Alternatives considered

- **Set `rp_filter = 0` globally, as most Cilium quickstarts and gists show.**
  Rejected: a host-wide security downgrade, broader than Cilium needs, and
  redundant because Cilium manages rp_filter on its own interfaces. Pre-empting
  it is both unsafe and pointless.
- **Add IPv6 forwarding now "for completeness."** Rejected: dead config on an
  IPv4-only platform, and trivially added later if dual-stack lands.
- **Hand-render the drop-in from a template (like `kernel_modules`) to get
  per-key comments in the file.** Rejected: contradicts ADR-0004's sysctl
  mechanism and reintroduces the `sysctl -p` command task that ADR-0004 exists
  to forbid. An in-file comment does not justify amending a settled decision.
- **Bundle node-tuning sysctls (inotify) into this slice.** Rejected: not a
  node prerequisite; scope creep against the slice's stated purpose.

## References

- ADR-0004 — `os_prep` role structure and idempotence; the sysctl-mechanism
  prescription (`ansible.posix.sysctl` with `sysctl_file:`)
- ADR-0007 — kernel module strategy; the bridge-nf-call keep-decision and the
  `br_netfilter`-before-sysctl ordering
- kubernetes/kubernetes PR #123464 — removal of the bridge-nf-call preflight
  checks; the `ip_forward` check was retained
- Kubernetes container-runtimes documentation (v1.34) — `net.ipv4.ip_forward`
  as the network prerequisite
- Cilium documentation — rp_filter handling on Cilium-managed interfaces;
  kube-proxy replacement and eBPF datapath
