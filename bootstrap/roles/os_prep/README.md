# os_prep

OS-level preparation for Kubernetes control-plane and worker nodes:
swap disable, kernel modules, sysctl tuning, time sync via chrony,
AppArmor verification, and CIS-recommended unused-filesystem-module
blacklist.

This role is idempotent and safe to re-run on existing nodes. It is
the first role applied by `bootstrap/site.yml` against every node,
regardless of deploy shape (`lab-single-node`, `edge-site`,
`ha-bare-metal`).

## Requirements

- Ansible 2.20 or newer (pinned by `bootstrap/requirements.txt`).
- Target hosts: Ubuntu 24.04 LTS (`noble`). Other versions are out of
  scope — see [Platform scope](#platform-scope).
- Privilege escalation: the role uses `become: true`. The connecting
  user needs passwordless sudo, or invocation with `--ask-become-pass`.

## Platform scope

Ubuntu 24.04 only. The repo's reproducibility pillar is at odds with
claiming multi-distro support without testing against each. Broadening
platform coverage requires a matching molecule platform and CI lane;
support is declared in `meta/main.yml` only after both exist.

## Role variables

Variables are populated as each `L1.1.x` slice lands.

| Variable                | Default | Owned by | Description |
| ----------------------- | ------- | -------- | ----------- |
| `os_prep_swap_disable`  | `true`  | `os_prep`| Disable swap: comment swap entries in `/etc/fstab` + runtime `swapoff -a`. Required for the default kubelet posture (`failSwapOn: true`, `NodeSwap` off). Set `false` only on nodes deliberately configured for `NodeSwap`. |
| `os_prep_kernel_modules` | `[overlay, br_netfilter]` | `os_prep` | Kernel modules loaded at boot via `/etc/modules-load.d/k8s.conf` and into the running kernel via `modprobe`. The containerd + kubeadm prerequisite set only; workload modules belong to their workload, not here. See `docs/adr/0007`. |
| `os_prep_sysctl_settings` | `{net.ipv4.ip_forward: "1", net.bridge.bridge-nf-call-iptables: "1", net.bridge.bridge-nf-call-ip6tables: "1"}` | `os_prep` | Kernel sysctls written to `os_prep_sysctl_file` and applied to the running kernel on real hosts. The Kubernetes node-prerequisite set only; `rp_filter`, IPv6 forwarding, and node-tuning sysctls are deliberately excluded. See `docs/adr/0009`. |
| `os_prep_sysctl_file` | `/etc/sysctl.d/99-k8s.conf` | `os_prep` | Drop-in path for the sysctl set. The `99-` prefix applies it after the distribution defaults in `/usr/lib/sysctl.d/`. |
| `os_prep_chrony_servers` | `[{type: pool, address: pool.ntp.org}]` | `os_prep` | Upstream NTP time sources, each rendered into `os_prep_chrony_conf_file` as a `<type> <address> iburst` line (`type` is `pool` or `server`). The public-pool default is a bootstrap value only — override with site or internal NTP servers in `group_vars`/`host_vars` for production, edge, and air-gapped nodes. chrony is used over the noble default `systemd-timesyncd`; see `docs/adr/0010`. |
| `os_prep_chrony_conf_file` | `/etc/chrony/chrony.conf` | `os_prep` | Path to the chrony config file, owned in full by the role's template (Ubuntu/Debian layout; RHEL uses `/etc/chrony.conf`). Single-sourced so the template and the molecule assertions reference one value. |

## Dependencies

None.

## Tags

The role exposes per-concern tags so the operator can run a subset:

| Tag        | Concern                                                        | Populated by |
| ---------- | -------------------------------------------------------------- | ------------ |
| `swap`     | Disable swap (comment fstab entries + runtime swapoff)         | L1.1.1       |
| `kernel`   | Load and persist required kernel modules                       | L1.1.2       |
| `sysctl`   | Apply Kubernetes-required sysctl values                        | L1.1.3       |
| `chrony`   | Install and enable chrony for time sync                        | L1.1.4       |
| `apparmor` | Verify AppArmor is enabled and enforcing                       | L1.1.5       |
| `cis`      | Blacklist CIS-recommended unused filesystem modules            | L1.1.6       |

## Example playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: os_prep
```

Selective execution:

```bash
ansible-playbook site.yml --tags sysctl,kernel
ansible-playbook site.yml --skip-tags chrony
```

## Testing

Molecule scenario `default` exercises the role in a systemd-enabled
Docker container (`geerlingguy/docker-ubuntu2404-ansible`).

```bash
cd bootstrap/roles/os_prep
molecule converge      # apply the role
molecule verify        # assert expected artifacts are present
molecule idempotence   # confirm a second converge reports zero changes
molecule destroy
```

### What molecule does and does not verify

Docker containers do not provide a real host kernel. Molecule's job
for this role is to validate **artifact content and idempotence**, not
the runtime kernel behaviour those artifacts produce:

- **Verified by molecule:** files in `/etc/sysctl.d/`,
  `/etc/modules-load.d/`, `/etc/modprobe.d/` have the expected content;
  the chrony package is installed and `chrony.conf` has the expected
  content and mode; a second converge reports zero changed tasks.
- **Not verified by molecule:** kernel modules actually loading into the
  host kernel; `swapoff` removing entries from `/proc/swaps`; chrony
  service running/enabled state and the `systemd-timesyncd` mask (live
  systemd actions, deferred to the L1.1.7 smoke test); AppArmor
  enforcement state on the host.

Assertions that require a real kernel are guarded with
`when: ansible_facts['virtualization_type'] not in ['docker', 'podman', 'container', 'containerd']`
so they skip inside molecule and run during real `site.yml` execution.

## License

Apache-2.0. See repository [`LICENSE`](../../../LICENSE).

## Author

M Nusrat Ullah.
