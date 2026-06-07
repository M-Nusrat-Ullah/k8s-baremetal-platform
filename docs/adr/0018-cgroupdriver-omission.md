# ADR-0018: cgroupDriver omitted from KubeletConfiguration

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.2
- **Supersedes:** none
- **Superseded by:** none

## Context

The kubelet must use the `systemd` cgroup driver to match containerd's
`SystemdCgroup = true` (set in L1.1.8, ADR-0007). The conventional
approach is to set `cgroupDriver: systemd` explicitly in
`KubeletConfiguration`. Two Kubernetes 1.34 developments change the
calculus.

**KubeletCgroupDriverFromCRI went GA in 1.34.** When active (on by
default in 1.34+), the kubelet queries the CRI for the cgroup driver
rather than reading `cgroupDriver`. containerd 2.x (this stack runs
2.1.5) supports this protocol and reports `systemd` because
`SystemdCgroup = true` is set. The field is ignored when CRI detection
is active.

**`cgroupDriver` deprecated in 1.34.** The field in KubeletConfiguration
(and the `--cgroup-driver` flag) is deprecated as of 1.34, with removal
scheduled no earlier than Kubernetes 1.36.

The 1.32 Grameenphone floor must also be covered. On 1.32 the gate is
alpha (off by default), so CRI detection is not the active mechanism.

## Decision

`cgroupDriver` is intentionally omitted from `KubeletConfiguration`. No
`KubeletConfiguration` document is included in the kubeadm config in
L1.2; that document is deferred to a CIS kubelet hardening slice. The
cgroup driver outcome is `systemd` via two independent mechanisms: CRI
auto-detection on 1.34, and kubeadm's own systemd default (in force
since v1.22) on older minors.

Before relying on this, confirm kubeadm 1.34's generated default:

```bash
kubeadm config print init-defaults --component-configs KubeletConfiguration \
  | grep cgroupDriver
# Expected: cgroupDriver: systemd
```

## Consequences

**Positive:**

- Correct on 1.34: CRI detection (GA) reports systemd from containerd.
- Correct on the 1.32 floor: kubeadm's systemd default covers the gap.
- Forward-clean: the field is removed no earlier than 1.36; omitting it
  now means nothing to migrate when the upgrade crosses that boundary.
- The omission is documented here and in the template header, so it reads
  as intentional rather than an oversight.

**Negative:**

- Relies on kubeadm's implicit default for the 1.32 floor rather than an
  explicit setting. Mitigated by the verification command above and this
  ADR.
- Any future `KubeletConfiguration` additions (CIS hardening slice) must
  not re-introduce `cgroupDriver`.

## Alternatives considered

**Set `cgroupDriver: systemd` explicitly.** Conventional. Rejected:
the field is deprecated in 1.34 and scheduled for removal at 1.36, which
is within the repo's planned upgrade horizon (1.34→1.35→…). Setting it
explicitly puts a removal liability on the upgrade path without providing
any functional benefit on 1.34 (field is ignored by the kubelet due to
CRI detection).

## References

- KEP-4033: KubeletCgroupDriverFromCRI — https://github.com/kubernetes/enhancements/issues/4033
- Kubernetes 1.34 release notes — cgroupDriver deprecation
