# containerd

Installs and configures containerd 2.x as the Kubernetes CRI on every node,
including the base CNI plugin set required before kubeadm runs. This role is
the second role applied by `bootstrap/site.yml`, after `os_prep` and before
the kubeadm layer (L1.2).

The role is idempotent and safe to re-run. It pins the runtime to an explicit
version, holds it against unattended upgrades, and generates the CRI config
from the binary's own defaults — so the config schema always matches the
installed version and the Docker package's CRI-disabled default is replaced
unconditionally.

## Requirements

- Ansible 2.20 or newer.
- `os_prep` applied first: `overlay` and `br_netfilter` modules must be loaded
  (preflight asserts this on real hosts; the check is guarded out of containers
  for Molecule).
- Target hosts: Ubuntu 24.04 LTS (`noble`). The `apt` install method targets
  the Docker apt repository; other distributions require a different install
  method (see `containerd_install_method` below).
- Privilege escalation: the role uses `become: true`. The connecting user needs
  passwordless sudo, or invocation with `--ask-become-pass`.

## Platform scope

Ubuntu 24.04 only, same reasoning as `os_prep`. Multi-distro and arm64 support
requires a matching Molecule platform and CI lane before being declared in
`meta/main.yml`.

## Role variables

Version pins (`containerd.version`, `containerd.sandbox_image`,
`cni_plugins.version`, `cni_plugins.checksum`) live in
`group_vars/all/versions.yml`, not here. Role variables are paths and
behavioural knobs only.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `containerd_install_method` | `apt` | Selects the install path. Only `apt` is implemented (Docker apt repo, pinned + held). The preflight fails loudly on any other value. A future `binary` path for air-gapped sites lands as `tasks/install-binary.yml` with no change to `tasks/main.yml`. See [ADR-0014](../../../docs/adr/0014-containerd-install-method-and-cni-scope.md). |
| `containerd_config_file` | `/etc/containerd/config.toml` | Path to the CRI config file rendered by the role. Single-sourced so the config task and Molecule verify reference one value. |
| `containerd_cni_bin_dir` | `/opt/cni/bin` | Directory the base CNI plugins are unpacked into. Must exist before Cilium (L1.3) is installed; Cilium drops its own binary here and delegates to the base set. |
| `containerd_apt_keyring_file` | `/etc/apt/keyrings/docker.asc` | On-disk path for the Docker ASCII-armored GPG key, referenced via `Signed-By` in the deb822 source. |
| `containerd_apt_source_file` | `/etc/apt/sources.list.d/docker.sources` | On-disk path for the deb822 `.sources` entry. The basename matches the deb822 repo name (`docker`). |

## What the role does

1. **Preflight** — asserts the install method is implemented, the OS family is
   Debian, and (on real hosts) that `overlay` and `br_netfilter` are loaded.
2. **Install** — fetches the Docker GPG key, adds the deb822 repo, installs
   `containerd.io` at the pinned version (`allow_downgrade: true` corrects a
   node carrying a newer unpinned version), and holds the package against
   unattended upgrades. `python3-debian` is installed first as a prerequisite
   for `deb822_repository`.
3. **CNI plugins** — creates `/opt/cni/bin`, fetches the `containernetworking/
   plugins` tarball (checksum-verified), and unpacks it. Provides `loopback`,
   `bridge`, `host-local`, `portmap`, `macvlan`, `ipvlan`, and `host-device`.
   The telco-relevant set (`macvlan`, `ipvlan`, `host-device`) supports Multus
   CNI delegation for 5G UPF and SR-IOV workloads without any additional
   configuration.
4. **Config** — runs `containerd config default` against the installed binary
   (generating a v3 schema with CRI enabled), applies two targeted transforms
   (`SystemdCgroup = true`; pinned sandbox image), and writes the result via
   idempotent `copy`. Replaces the Docker package's CRI-disabled default
   unconditionally. See [ADR-0015](../../../docs/adr/0015-containerd-config-generation-strategy.md).
5. **Service** — enables and starts `containerd.service` on real hosts (guarded
   out of containers). A handler restarts the service on config change.

## Dependencies

- Role `os_prep` must run first (`overlay` + `br_netfilter` prerequisite).

## Tags

| Tag | Concern |
| --- | ------- |
| `preflight` | Install method and OS family assertions; kernel module check |
| `install` | Docker repo, key, `containerd.io` package, hold |
| `cni` | CNI plugin tarball fetch and unpack |
| `config` | Config generation, transform, copy; service enable/start |

## Example playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: os_prep
    - role: containerd
```

Selective execution:

```bash
ansible-playbook site.yml --tags cni
ansible-playbook site.yml --skip-tags preflight
```

## Testing

Molecule scenario `default` exercises the role in a systemd-enabled Docker
container (`geerlingguy/docker-ubuntu2404-ansible`).

```bash
cd bootstrap/roles/containerd
molecule converge      # apply the role (pulls from Docker apt repo + GitHub)
molecule verify        # assert expected artifacts are present
molecule idempotence   # confirm a second converge reports zero changes
molecule destroy
```

### What molecule does and does not verify

**Verified by molecule:**

- `containerd.io` installed at the exact pinned version.
- `runc` binary present and executable at `/usr/bin/runc` (bundled in
  `containerd.io`, not a separate package).
- Docker apt keyring (`/etc/apt/keyrings/docker.asc`) and deb822 source file
  (`/etc/apt/sources.list.d/docker.sources`) present.
- `config.toml` at mode 0644, `SystemdCgroup = true` exactly once, sandbox
  image pinned exactly once, no `disabled_plugins` line disabling `cri`.
- All seven base CNI plugin binaries present and executable in
  `/opt/cni/bin/`: `loopback`, `bridge`, `host-local`, `portmap`, `macvlan`,
  `ipvlan`, `host-device`.
- A second converge reports zero changes (idempotence, via `molecule
  idempotence`).

**Not verified by molecule (proven by real-host smoke test):**

- `containerd.service` running and enabled (service state needs a real systemd
  manager; the enable/start task is guarded out of containers).
- The restart handler firing on a config change.
- `containerd config default` output matching the expected v3 schema on a
  kernel other than the one in the geerlingguy image.

Assertions requiring a real host are guarded with:

```yaml
when: ansible_facts['virtualization_type'] not in ['docker', 'podman', 'container', 'containerd']
```

### Notes on converge network requirements

`molecule converge` fetches two external resources: the Docker apt repo
(`download.docker.com`) for the `containerd.io` package, and the CNI plugins
tarball from GitHub (`github.com/containernetworking/plugins/releases`). An
air-gapped Molecule environment will fail at those steps.

## License

Apache-2.0. See repository [`LICENSE`](../../../LICENSE).

## Author

M Nusrat Ullah.
