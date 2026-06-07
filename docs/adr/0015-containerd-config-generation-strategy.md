# ADR-0015: containerd config generation strategy and sandbox image pin

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1.8
- **Supersedes:** none
- **Superseded by:** none

## Context

Every containerd node requires `/etc/containerd/config.toml` with two values
set correctly before kubeadm can proceed:

- `SystemdCgroup = true` — mandatory on a systemd host with Kubernetes 1.34;
  the kubelet derives its cgroup driver from the CRI runtime, and a mismatch
  is the root cause of the classic "kubeadm init hangs / cgroupsPath" failure.
- A pinned sandbox (pause) image — must match the pause version kubeadm
  expects for the target Kubernetes version to avoid a pull-at-init-time
  race on air-gapped or rate-limited nodes.

The Docker `containerd.io` package ships `/etc/containerd/config.toml` with
`disabled_plugins = ["cri"]`, which disables the CRI plugin entirely. Any
strategy that does not replace this file leaves the runtime non-functional as
a Kubernetes CRI.

Three config strategies were considered.

### Option A — hand-maintained Jinja2 template

Maintain a full `config.toml.j2` template covering every relevant stanza.
Rejected: containerd's config schema is large (~200 lines in v3), version-
coupled (v2 and v3 differ in key names and structure), and mostly irrelevant
to this platform's concerns. Transcribing it by hand introduces transcription
risk — a misplaced key or wrong default silently changes runtime behaviour.
The template would need updating with every containerd minor release that
changes the schema.

### Option B — `ansible.builtin.lineinfile` / `blockinfile` on the shipped file

Patch the Docker .deb's shipped file in place. Rejected for two reasons:
(1) the shipped file has `disabled_plugins = ["cri"]`, so patching it requires
also removing that line — `lineinfile` in replace mode cannot reliably delete
a line and insert a different one atomically; (2) the shipped file's schema is
v2-shaped in some Docker releases, and `blockinfile` cannot validate schema
version before patching.

### Option C — generate from the binary, transform, copy (chosen)

Run `containerd config default` (the pinned binary's own default-generator),
apply two targeted regex transforms, and write the result via
`ansible.builtin.copy`. `copy` compares rendered content to disk and reports
`changed=0` on an identical re-run, so idempotence holds. The generated
default always has CRI enabled (`disabled_plugins = []`), so the CRI-disabled
shipped file is fully replaced on first run.

## Decision

### Decision 1 — generate-transform-copy with two targeted regexes

`tasks/config.yml` runs `containerd config default` (changed_when: false —
read-only generator, no system state), applies two `regex_replace` transforms
inline in the `copy` task's `content:` parameter, and writes
`containerd_config_file` (`/etc/containerd/config.toml`) with mode 0644.

**Transform 1 — SystemdCgroup:**

    pattern:  (?m)^(\s*)SystemdCgroup\s*=.*$
    replace:  \g<1>SystemdCgroup = true

Anchored to the key name, preserves indentation, matches regardless of the
current value. The v3 default has exactly one `SystemdCgroup` key (under the
runc options stanza); `verify.yml` asserts `length == 1` to catch duplication.

**Transform 2 — sandbox image (v3 key name):**

    pattern:  (?m)^(\s*)sandbox = '.*'$
    replace:  \g<1>sandbox = '{{ containerd.sandbox_image }}'

In containerd config v3 the pause image is `sandbox` under
`[plugins."io.containerd.cri.v1.images".pinned_images]`. The v2 key
(`sandbox_image` under `[plugins."io.containerd.grpc.v1.cri"]`) does not
appear in 2.x defaults. The regex matches the single-quoted TOML string form
produced by `containerd config default`; `verify.yml` asserts `length == 1`.

Both transforms were validated against real `containerd config default` output
from the pinned `containerd.io 2.1.5-1~ubuntu.24.04~noble` binary during the
Molecule converge run (not against a synthetic snippet), confirming the key
names and quoting conventions are correct for this version.

### Decision 2 — sandbox image pin matched to kubeadm 1.34

`containerd.sandbox_image` is set to `registry.k8s.io/pause:3.10.1` in
`group_vars/all/versions.yml`. This value was sourced from
`kubeadm config images list` output for the kubernetes.version pin (1.34.x).
It must be updated in lock-step with `kubernetes.version` at L1.2 and
reconfirmed via `kubeadm config images list --kubernetes-version <ver>` before
any Kubernetes version upgrade. The ADR for the 1.34->1.35 upgrade (planned as
a portfolio artifact) must include this reconfirmation step.

### Decision 3 — SystemdCgroup is not exposed as a variable

`SystemdCgroup = true` is set unconditionally and is not exposed via a role
variable. On this platform (systemd host, Kubernetes 1.34, containerd 2.x)
there is no valid value other than `true`. Exposing it as a variable creates
a footgun: a caller who sets it to `false` produces a silently broken cluster.
The correct override surface for cgroup-related behaviour is the kubelet
configuration (L1.2), not the CRI config.

## Consequences

- `containerd config default` is the one `command` module task in the role
  (ADR-0004 prefers modules; the exception is documented in the task comment).
  It is always `changed_when: false`.
- Any containerd upgrade that changes the v3 config schema — new keys, renamed
  stanzas — will not break the role: the generator produces the new schema and
  the two targeted transforms apply to their specific keys. Stanzas the role
  does not touch are inherited from the binary's own defaults.
- `sandbox_image` (v2 key) must **not** be used as the transform target;
  it does not exist in containerd 2.x defaults. If a future release renames
  `sandbox` again, `verify.yml`'s `length == 1` assertion will catch the
  mismatch on the next Molecule run.
- The `sandbox` pin must be updated before any Kubernetes version upgrade.
  Failing to update it does not break the running cluster (containerd caches
  the image) but causes a mismatch between the pinned image and what kubeadm
  would pull, and may cause issues on nodes where the image is not yet cached.
