# os_prep real-host smoke test (L1.1.7)

The Molecule container scenario proves `os_prep` writes the right files and
packages, but it cannot execute the role's live half — kernel-module loads,
runtime sysctls, systemd unit state — which is guarded out of containers, nor
prove any of it survives a reboot. This runbook closes that gap: it applies
`os_prep` to a real Ubuntu 24.04 host, verifies the live state, reboots, and
verifies again. The second verify is the point — it proves the *persisted
artifacts* (`modules-load.d`, the `sysctl.d` drop-in, `fstab`, the chrony unit,
the timesyncd mask, `modprobe.d`) re-establish the correct state on their own at
boot, with the role not re-running.

See [ADR-0013](../../../docs/adr/0013-real-host-smoke-test-harness.md) for the
design rationale and the alternatives rejected.

## What this is not

This is an **operator-run** harness, not CI. It needs a real VM, a reboot, and
manual preconditions. It does not run on every push; run it when the `os_prep`
role's live behaviour changes, or to re-validate on a new kernel.

## Preconditions

A dedicated, disposable noble (Ubuntu 24.04) host. **Not your workstation** —
the role disables swap, masks `systemd-timesyncd`, blacklists kernel modules,
purges `snapd`, and this harness reboots the machine.

1. **Reachable, clean host.** A noble VM with `sshd` running and no Kubernetes
   or container runtime installed (a clean baseline is what `os_prep` is
   designed to prepare; a node already running containerd/docker would mask
   what the test attributes to the role).
2. **Key-based SSH** from the controller to the host:
   ```bash
   ssh-copy-id <user>@<host>
   ssh <user>@<host> true        # must succeed with no password prompt
   ```
3. **Passwordless sudo** for that user (the apply and reboot escalate, and the
   reboot reconnects unattended):
   ```bash
   sudo visudo -f /etc/sudoers.d/90-<user>-nopasswd
   #   add:  <user> ALL=(ALL) NOPASSWD:ALL
   ssh <user>@<host> sudo -n true && echo "sudo nopasswd"
   ```
4. **A stable address.** Pin the host's IP (DHCP reservation or static): the
   harness reboots mid-run, and a lease change across the reboot makes the
   post-reboot verify fail to reconnect. This is environment config, not repo
   config — keep it out of the committed inventory.
5. **Inventory populated.** Put the host in `inventory/lab-single-node/hosts.yml`
   (both `control_plane` and `workers`). Keep real `ansible_host` / `ansible_user`
   values local; the committed file ships placeholders.

Confirm reachability and that the host is not a container (so the guarded checks
actually run):

```bash
ansible -i inventory/lab-single-node/ all -m ping
ansible -i inventory/lab-single-node/ all -m setup -a 'filter=ansible_virtualization_type'
```

`ping: pong`, and `ansible_virtualization_type` reporting a VM type (`kvm`,
`qemu`, …) — anything other than `docker`/`podman`/`container`.

## Run

All commands from `bootstrap/`.

```bash
# 1. Apply os_prep via the real deployment path
ansible-playbook -i inventory/lab-single-node/ site.yml

# 2. Verify the LIVE state (the role just ran)
ansible-playbook -i inventory/lab-single-node/ roles/os_prep/molecule/default/verify.yml

# 3. Reboot and wait for the host to return
ansible-playbook -i inventory/lab-single-node/ tests/smoke/reboot.yml

# 4. Verify the PERSISTED state (nothing re-applied since boot) — the proof
ansible-playbook -i inventory/lab-single-node/ roles/os_prep/molecule/default/verify.yml
```

`verify.yml` is the same file the Molecule scenario uses; it runs verbatim here
because it is `hosts: all` and loads role defaults via a playbook-relative
`vars_files`. No smoke-specific copy of the assertions exists — one source of
truth.

## Expected output

- **Step 1 (apply):** first run `changed` for most tasks; `failed=0`. On a
  freshly booted host, `unattended-upgrades` may briefly hold the dpkg lock and
  the chrony install can collide with it — wait for the background upgrade to
  finish and re-run (`os_prep` is idempotent, so the re-run resumes cleanly).
- **Steps 2 and 4 (verify):** identical results — `ok=40, changed=0, failed=0,
  skipped=1`. The single skip is the swap-decoy assert, which is gated to the
  Molecule container context and correctly skips on a real host. Every
  previously-guarded check now runs and passes: runtime swap 0; `overlay` and
  `br_netfilter` in `/proc/modules`; the three sysctls live in `/proc/sys`;
  chrony running + enabled; `systemd-timesyncd` masked to `/dev/null`; AppArmor
  LSM enabled (`Y`); and the blacklist proof — on the noble generic kernel
  `squashfs` is built in (`=y`) and passes as such, the other seven resolve to
  `/bin/false`.
- **Step 3 (reboot):** one task, `changed`; a long wait while the host boots
  (slow on an HDD VM) is expected, not a hang. Timeouts are tuned in
  `reboot.yml` (`reboot_timeout: 900`, `post_reboot_delay: 30`).

The meaningful result is that **step 4 matches step 2** — the artifacts survive
a cold boot with `os_prep` not having run since.

## Failure modes

- `failed` at the chrony `apt` task → dpkg lock held by `unattended-upgrades`;
  wait and re-run step 1.
- `state: stopped` errors on a unit → not expected post-fix; report it.
- Post-reboot verify cannot connect → the host's address changed across the
  reboot; pin it (precondition 4).
- A verify assert fails → paste the full task; the blacklist branch is the
  newest logic and the first place a different kernel would surface a
  difference.
