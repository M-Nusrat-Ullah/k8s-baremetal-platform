# ADR-0005: Swap disable strategy

- **Status:** Accepted
- **Date:** 2026-05-29
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1
- **Supersedes:** none
- **Superseded by:** none
- **Amends:** ADR-0004 (Decision 2 swap module prescription)

## Context

kubeadm's default kubelet posture is `failSwapOn: true` with the `NodeSwap`
feature gate off. Through the current release line, `NodeSwap` is beta,
disabled by default, and cgroup-v2 only. kubeadm downgraded the swap preflight
from a hard error to a warning, so "kubelet won't start" is no longer precise;
the accurate statement is that a node with swap active and default kubelet
config is unsupported and behaves incorrectly. We are not enabling `NodeSwap`.

Swap-off is also a hardening control, not only a kubeadm checkbox. With swap
enabled, memory-backed volumes (`emptyDir.medium: Memory`, Secret mounts) can
be paged to disk; upstream explicitly warns these are no longer secure. This
directly protects the `emptyDir.medium: Memory` pattern HARDENING.md §3.3
mandates.

Constraints: the role targets three shapes whose swap `src` is not uniform, and
Molecule (Docker) cannot validate real swap removal because a container reads
the host's `/proc/meminfo`. Ubuntu 24.04 (subiquity) provisions a `/swap.img`
swapfile by default.

ADR-0004's Decision 2 prescribed `ansible.posix.mount` for the fstab half of
swap disable. Sourced investigation (this ADR) showed the module manages fstab
only — it does not call `swapoff`, and it keys swap entries by `src` — so the
runtime half requires a guarded command. This ADR corrects that prescription;
ADR-0004 carries an `Amended by: ADR-0005` annotation.

## Decision

`os_prep` disables swap, gated by a single `os_prep_swap_disable` toggle:

1. **Persistent:** `ansible.builtin.replace` comments out any `/etc/fstab` line
   whose third field is `swap`, prefixed with
   `# [os-prep] swap disabled - see ADR-0005`. Anchored on the fstype column,
   not a substring, and src-agnostic (covers swapfile, partition, multiple
   entries). Commenting (not deleting) keeps the change reversible and
   auditable.
2. **Runtime:** a guarded `swapoff -a`, run only when swap is active and the
   host is not a container runtime.

cloud-init drop-ins and `systemd-gpt-auto-generator` handling are **out of
scope**. On the swapfile default, the fstab change covers fstab and the
systemd-generated swap unit transitively. The only uncovered mechanism is GPT
swap-type partition auto-activation, which applies solely to partition-based
swap and is gated by a real-host reboot smoke test (`swapon --show` after
reboot) rather than speculative, untested code.

## Alternatives considered

- **`ansible.posix.mount` `state: absent`** — rejected. It keys swap entries by
  `src` (mount point is `none`), so removal requires discovering each src per
  shape; it does not call `swapoff` (the upstream swap-management PR is
  unmerged); and `absent` no-ops when the line is not already in fstab.
- **Deleting swap lines** — rejected in favour of commenting, for auditability
  and reversibility in a system file.
- **Speculative cloud-init / GPT-auto tasks now** — rejected as untested
  defensive code; the reboot smoke test decides whether any is needed.

## Consequences

- Aligns with kubeadm defaults and the HARDENING.md §3.3 memory-volume control.
- Idempotent and shape-agnostic; Molecule validates wiring and idempotence.
- Molecule cannot prove real removal (container limitation), so a real-host
  reboot smoke test is required before production sign-off.
- A GPT swap-type partition would survive this role and need a follow-up
  targeted task — accepted, gated by the smoke test.
