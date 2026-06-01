# ADR-0007: Kernel module strategy for `os_prep`

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1
- **Supersedes:** none
- **Superseded by:** none

## Context

The `os_prep` role (ADR-0004) loads kernel modules as one of its
per-concern slices (L1.1.2). The question is narrow but easy to get wrong
by copying conventional guidance: **which modules, and why.**

Every kubeadm bring-up guide prescribes the same two modules — `overlay`
and `br_netfilter` — written into `/etc/modules-load.d/k8s.conf` and
loaded with `modprobe`. The near-universal justification given is
"load `br_netfilter` so that iptables can see bridged traffic, which
kube-proxy and NetworkPolicy depend on."

That justification does not hold for this cluster, and two facts make the
copied rationale actively misleading here:

1. **This cluster runs Cilium in kube-proxy-replacement mode with the eBPF
   datapath (L0).** There is no kube-proxy iptables datapath that needs to
   observe bridged traffic. Cilium's datapath does not depend on
   `br_netfilter`.

2. **kubeadm no longer performs the bridge-netfilter preflight check.**
   The `FileContent--proc-sys-net-bridge-bridge-nf-call-iptables` and
   `-ip6tables` checks were removed from kubeadm (upstream PR #123464) on
   the grounds that not all network implementations require the setting and
   that CNI plugins are responsible for it. So "load it to pass preflight"
   is not a valid reason on the pinned 1.34 line either.

If the role shipped the conventional comment, a reviewer who knows this
stack would correctly flag it as cargo-culted. The modules are still the
right ones to load — but for reasons that have to be stated correctly.

## Decision

Load exactly two modules — `overlay` and `br_netfilter` — via a single
templated `/etc/modules-load.d/k8s.conf` (boot persistence) and a guarded
`community.general.modprobe` loop (runtime load), driven by the
`os_prep_kernel_modules` list variable. Deliberately **exclude** the
`ip_vs*` family.

Rationale, per module:

- **`overlay`** — required by containerd's `overlayfs` snapshotter, the
  default storage driver, which is independent of CNI choice. On modern
  kernels (5.x+) overlayfs is frequently built in, so the `modprobe` is
  often a no-op; loading it explicitly guarantees the dependency is
  satisfied on minimal kernels and is idempotent where it is already
  present. This is the one unambiguously load-bearing module.

- **`br_netfilter`** — loaded as part of the conventional containerd +
  kubeadm baseline, with a precise local reason: the L1.1.3 sysctl slice
  sets `net.bridge.bridge-nf-call-iptables` and
  `net.bridge.bridge-nf-call-ip6tables`, and **those sysctl keys do not
  exist in `/proc/sys` until `br_netfilter` is loaded.** Setting them
  without the module present fails. This is why the `kernel_modules` import
  is ordered *before* any sysctl import in `tasks/main.yml`, and why that
  ordering carries a do-not-reorder comment.

  Whether those bridge sysctls are themselves strictly necessary under a
  kube-proxy-free Cilium datapath is a separate question (see below); the
  decision here is that, given the role *does* set them as part of the
  standard baseline, `br_netfilter` must be loaded first.

### Why keep the bridge-netfilter baseline at all under Cilium

A tempting "improvement" is to drop both `br_netfilter` and the bridge
sysctls entirely, since Cilium's eBPF datapath does not route pod traffic
through the bridge-netfilter hooks. This is rejected as untested
cleverness:

- The overlay + br_netfilter + bridge-sysctl trio is the baseline every
  kubeadm node-bringup path assumes. Diverging from it makes this node
  subtly different from every reference configuration, which is a debugging
  liability disproportionate to the near-zero cost of the modules.
- The modules and sysctls are harmless when unused: a loaded module and a
  set-but-unconsulted sysctl impose no measurable cost and create no
  attack surface relevant to this stack.
- Removing them would itself be a decision requiring its own
  justification, a real-host test that nothing in the bring-up path
  regresses, and ongoing vigilance against Cilium or kubeadm behaviour
  changes. The payoff does not justify that.

The defensible position is therefore: keep the conventional baseline,
but document precisely why each element is present and explicitly retire
the obsolete "iptables sees bridged traffic" rationale.

### Why `ip_vs*` is excluded

The `ip_vs`, `ip_vs_rr`, `ip_vs_wrr`, `ip_vs_sh`, and `nf_conntrack`
modules are prerequisites for kube-proxy's IPVS mode. This cluster runs
no kube-proxy at all — Cilium replaces it. Loading the IPVS family would
be dead weight loaded for a component that does not exist, the exact
cargo-culting this ADR exists to avoid. They are omitted, and the
`os_prep_kernel_modules` default carries a comment stating that workload-
or component-specific modules do not belong in the host baseline.

### Mechanism

- **Persistence:** one templated file, `/etc/modules-load.d/k8s.conf`,
  rendered from `os_prep_kernel_modules` (not one file per module, and not
  `modprobe`'s `persistent:` option, which writes to `/etc/modprobe.d/`
  with different semantics). systemd-modules-load reads this at boot.
- **Runtime:** a `community.general.modprobe` loop over the same variable,
  guarded by the role's container check
  (`ansible_facts['virtualization_type'] not in [...]`) so it skips inside
  the Molecule Docker container, which shares the host kernel and cannot
  load modules.
- **Single source of truth:** both the persisted file and the runtime
  loop iterate the one `os_prep_kernel_modules` list; the Molecule verify
  assertions iterate it too (via `vars_files`), so the file content, the
  runtime load, and the test can never drift from one another.

## Consequences

**Positive:**

- The module set is minimal and every entry has a stated, correct reason.
- The obsolete bridge-netfilter rationale is explicitly corrected, so the
  repo does not propagate a misconception.
- The `br_netfilter`-before-sysctl ordering has a documented cause, not
  an accidental one.
- Adding or removing a baseline module is a one-line change to
  `os_prep_kernel_modules`, picked up by persistence, runtime, and tests
  together.

**Negative:**

- The role carries `br_netfilter` and (in L1.1.3) bridge sysctls that are
  not on Cilium's critical datapath — a small, deliberate amount of
  conventional baseline kept for compatibility rather than strict
  necessity. Accepted as the cheaper, lower-risk choice over divergence.
- Real module-load behaviour (overlay/br_netfilter actually appearing in
  `/proc/modules`) cannot be verified under Molecule's Docker driver; it
  is deferred to a real-host reboot smoke test in a later layer, alongside
  the swap `swapon --show` check.

## Alternatives considered

- **Ship the conventional "iptables sees bridged traffic" rationale.**
  Rejected: factually wrong for a kube-proxy-replacement Cilium datapath,
  and tied to a kubeadm preflight check that no longer exists.
- **Drop `br_netfilter` and the bridge sysctls entirely under Cilium.**
  Rejected as untested divergence from the assumed baseline; see "Why keep
  the bridge-netfilter baseline at all" above.
- **Include the `ip_vs*` family "for completeness."** Rejected: prerequisites
  for a kube-proxy IPVS mode this cluster does not run.
- **One file per module under `/etc/modules-load.d/`.** Rejected: more files
  to manage for no benefit; a single `k8s.conf` rendered from the list is
  simpler and keeps the module set in one place.

## References

- ADR-0004 — `os_prep` role structure; this ADR fills in the L1.1.2 slice
- kubernetes/kubernetes PR #123464 — removal of the bridge-nf-call preflight checks
- Kubernetes container-runtimes documentation — overlay + br_netfilter prerequisite baseline
- Cilium documentation — kube-proxy replacement and eBPF datapath
