# ADR-0014: containerd install method, install-method seam, and CNI plugin scope

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1.8
- **Supersedes:** none
- **Superseded by:** none

## Context

The platform requires a container runtime on every node before kubeadm can
initialise the cluster (L1.2). Three decisions are coupled here and resolved
together: *how* containerd is installed, *whether* the install method is an
abstraction seam, and *which role* owns the base CNI plugins.

### Install method options considered

**Option A — Docker apt repository (`containerd.io` package, pinned).**
Docker Inc. maintains `containerd.io` for Ubuntu noble as a first-party
package. It bundles runc (no separate runc install step), is updated
independently of the Docker engine, and ships on a predictable versioning
cadence. The production failure mode the testbed demonstrates
(`CLUSTER_BASELINE.md` §`install.sh:73`: unpinned, unverified, no hold) is an
*apt discipline* failure, not an apt architecture failure. The correct fix is
to pin (`apt install containerd.io=<version>`), hold (`apt-mark hold`), and
verify — not to abandon the install path.

**Option B — upstream static binary tarball (`cri-containerd-cni`).**
Eliminated: the `cri-containerd-cni` bundle was deprecated and removed in
containerd v1.7. Using it today means pinning three separate artifacts
(containerd binary, runc binary, CNI plugins) from separate release pages,
each requiring an independent checksum, with no distro integration for
postinst service wiring. More maintenance surface, not less.

**Option C — distro package (`containerd` from Ubuntu universe).**
Eliminated: Ubuntu universe ships containerd 1.7.x for noble. The locked
stack requires containerd 2.x (config v3 schema, required for the
`pinned_images.sandbox` key; v2 schema's `sandbox_image` key is absent in 2.x
defaults). Version mismatch with the rest of the locked stack.

## Decision

### Decision 1 — install method: apt (`containerd.io`, Docker repo, pinned + held)

Install `containerd.io` from the Docker apt repository, pinned to
`containerd.version` (defined in `group_vars/all/versions.yml`) and held with
`apt-mark hold`. The Docker GPG key is fetched as an ASCII-armored `.asc` file
to `/etc/apt/keyrings/docker.asc` and referenced via `Signed-By` in a deb822
`.sources` file — the modern apt security model, not the deprecated `apt-key`
store. runc is bundled inside `containerd.io` and requires no separate install
task. `python3-debian` is installed as a prerequisite because
`ansible.builtin.deb822_repository` requires it on the target; Ubuntu 24.04
full installs typically ship it, but minimal and cloud images may not, so the
role installs it explicitly to be self-contained on any noble variant.

### Decision 2 — install method as an abstraction seam

`containerd_install_method` (default: `apt`) drives a `include_tasks` dispatch
in `tasks/main.yml`. Only `apt` is implemented today. A future binary-tarball
path — for a distro that Docker does not package 2.x for, or for an air-gapped
site — lands as `tasks/install-binary.yml` and flips this variable, with no
change to `tasks/main.yml` or any other task file. The preflight asserts that
the selected method is implemented and fails loudly on an unrecognised value.

The base CNI plugins (Decision 3 below) are deliberately **not** behind this
seam: they are always fetched as a checksum-verified upstream tarball
regardless of how containerd itself is installed, because no distro package
bundles them with the runtime.

### Decision 3 — CNI plugins owned by the containerd role

The base CNI plugins (`containernetworking/plugins` release tarball, amd64,
pinned to `cni_plugins.version` with `cni_plugins.checksum` verification) are
installed by this role into `containerd_cni_bin_dir` (`/opt/cni/bin`).

Ownership here rather than in a dedicated CNI role or in the Cilium role
(L1.3) is justified on three grounds:

1. **CRI prerequisite ordering.** containerd cannot bring up a Pod sandbox
   without the `loopback` plugin. The plugin set must be present before the
   runtime is configured and certainly before kubeadm runs. Placing it here
   ensures the ordering constraint is satisfied by role dependency, not by
   run-order convention.
2. **Cilium does not replace the base set.** Cilium drops its own binary into
   `/opt/cni/bin` but delegates to `loopback`, `bridge`, `host-local`,
   `portmap`, and — for telco workloads via Multus — `macvlan`, `ipvlan`, and
   `host-device`. These must pre-exist. Cilium's role should not install
   plugins it does not own.
3. **Symmetry with static binary installs.** Under a future binary install
   method, both containerd and CNI plugins come from upstream tarballs. The
   seam argument (Decision 2) applies cleanly: the CNI task is always a
   tarball fetch, independent of how containerd arrived.

amd64 only at this decision point. A multi-arch path (arm64 URL + checksum
variant) is deferred until the cluster is up end-to-end on noble/amd64.

## Consequences

- `containerd_install_method: apt` is the only implemented path; any other
  value fails the preflight loudly.
- A future binary/air-gapped install adds `tasks/install-binary.yml` and sets
  `containerd_install_method: binary` in the relevant host/group vars, with no
  change to any other task file.
- `python3-debian` is installed unconditionally on every node that runs this
  role. It is a small package with no significant footprint.
- CNI plugin versions are pinned in `group_vars/all/versions.yml` alongside
  the containerd version. They must be updated together when upgrading the
  runtime to ensure the plugin ABI is compatible.
- arm64 support requires a second `cni_plugins.checksum_arm64` key in
  `versions.yml` and a conditional URL in `tasks/cni-plugins.yml`; deferred.
