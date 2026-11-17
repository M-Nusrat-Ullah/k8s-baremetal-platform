# bootstrap/

The Ansible bootstrap layer for the `k8s-baremetal-platform` project. This
directory contains the imperative provisioning logic that takes
freshly-provisioned Linux hosts to a running Kubernetes cluster: OS prep,
container runtime, kubeadm-driven control plane, CNI (Cilium), and the Flux
bootstrap that hands ongoing operation to GitOps.

For project-level context (audiences, design pillars, deploy shapes), see
the [repo-root README](../README.md). For design decisions, see
[`docs/adr/`](../docs/adr/).

## Current state

Layers 1.0, 1.1, and 1.2 are complete. The L2 Cilium CNI design is accepted
and implementation begins next. See [`docs/adr/`](../docs/adr/) for the
decision behind each slice.

What lives here today:

- Hardened `ansible.cfg` with pipelining, persistent SSH ControlMaster,
  YAML-formatted task output, and in-memory fact caching.
- A repo-root `.envrc` (direnv) that activates the layer virtualenv and
  exports the pinned `ANSIBLE_COLLECTIONS_PATH` on entry — see Quick start.
- Pinned Python tooling (`requirements.txt`) and Galaxy collections
  (`requirements.yml`).
- `roles/os_prep/` — OS prep role (swap, modules, sysctls, chrony, AppArmor,
  CIS module blacklist, real-host smoke-test harness). Molecule green.
- `roles/containerd/` — container runtime role; containerd 2.3.6 + CNI
  plugins v1.9.1. Molecule green.
- `roles/kube_install/` — kubeadm/kubelet/kubectl install role (K8s 1.36.6).
  Molecule green (12 assertions).
- `roles/kube_bootstrap/` — kubeadm init, kubeconfig, control-plane untaint,
  worker join. Composes with `kube_install`.
- Component version registry at `group_vars/all/versions.yml`; containerd,
  CNI plugins, and Kubernetes pinned. Cilium/Helm/Gateway API pending (L2).
- Per-shape inventory under `inventory/<shape>/`; `lab-single-node` carries
  the real lab host IP and SSH user.
- Top-level `site.yml`: SSH trust play → `os_prep` → `containerd` →
  `kube_install` → `kube_bootstrap`, one play per role.
- Lint configs (`.yamllint`, `.ansible-lint` with `profile: production`) and
  pre-commit hooks — these live at the repo root and apply repo-wide.

What is not here yet:

- `roles/cilium_install/` and the Gateway API CRD assets (L2 — next).
- `edge-site` and `ha-bare-metal` inventories remain group-structure
  skeletons with empty `hosts: {}` until real targets exist.

## Quick start

Python 3.12+ is required (ansible-core 2.20's floor). Ubuntu 24.04 LTS
ships 3.12.3 and is the validated host. The repo uses
[direnv](https://direnv.net) to load `.envrc` on `cd` into the directory:
it puts `bootstrap/.venv/bin` on `PATH` and exports
`ANSIBLE_COLLECTIONS_PATH`, so no manual `source` is ever needed — and a
hand-run `source` is discouraged because it races direnv. Install direnv
and hook it into your shell once before the steps below.

```bash
# CWD: repo root
git clone https://github.com/M-Nusrat-Ullah/k8s-baremetal-platform
cd k8s-baremetal-platform

# 1. Create the per-layer virtualenv (system python3 builds it)
python3 -m venv bootstrap/.venv

# 2. Trust .envrc — activates the venv and exports ANSIBLE_COLLECTIONS_PATH.
#    Re-run after any edit to .envrc.
direnv allow

# 3. Install Python tooling (pip resolves from the venv now, no source)
pip install --upgrade pip
pip install -r bootstrap/requirements.txt

# 4. Install Galaxy collections into the layer-local path
ansible-galaxy collection install -r bootstrap/requirements.yml -p bootstrap/collections

# 5. Wire up the pre-commit git hook (one-time per clone)
pre-commit install

# 6. Verify the environment resolves from the venv, not the system
which molecule ansible-lint python   # all under bootstrap/.venv/bin
echo "$ANSIBLE_COLLECTIONS_PATH"      # …/bootstrap/collections

# 7. Smoke test — should print "skipping: no hosts matched" with no errors
(cd bootstrap && ansible-playbook -i inventory/lab-single-node/ site.yml --check)

# 8. Control-node binaries (needed from L2; not Python, not Galaxy).
#    Pins live in bootstrap/group_vars/all/versions.yml (cosign.*, helm.*);
#    the values below are those pins — update both together.
#    cosign verifies Cilium image signatures when digests are pinned (ADR-0030);
#    helm renders charts for the values gate and pulls them. Use any directory
#    on PATH instead of ~/.local/bin if you prefer.
D=$(mktemp -d)
curl -fsSL -o "$D/cosign" https://github.com/sigstore/cosign/releases/download/v3.1.4/cosign-linux-amd64
echo "424e2c97d0b45fd7a6b608a87f090f35633f4c23ece5f092d48bba11aaf4bbfa  $D/cosign" | sha256sum -c -
install -m 0755 "$D/cosign" ~/.local/bin/cosign
curl -fsSL -o "$D/helm.tgz" https://get.helm.sh/helm-v4.3.2-linux-amd64.tar.gz
echo "d1c0278d46beab79582d7e50f5b3dc206944ba8e577cde618513fd07daa53983  $D/helm.tgz" | sha256sum -c -
tar -xzf "$D/helm.tgz" -C "$D" && install -m 0755 "$D/linux-amd64/helm" ~/.local/bin/helm
cosign version | grep GitVersion; helm version --short   # v3.1.4 ; v4.3.2+g…
```

If step 6 shows the venv paths and step 7 prints `PLAY RECAP ***` with no
host lines and exits cleanly, the layer is correctly set up.

> **Not using direnv?** After step 1, `source bootstrap/.venv/bin/activate`
> and `export ANSIBLE_COLLECTIONS_PATH="$PWD/bootstrap/collections"` by
> hand — ansible-lint honors only that variable, not `ansible.cfg`'s
> `collections_path`. Never combine a manual `source` with direnv active.

## Layout

```text
bootstrap/
├── ansible.cfg # runtime configuration
├── group_vars/
│ └── all/
│ └── versions.yml # component version registry
├── inventory/
│ ├── edge-site/hosts.yml # deploy shape: edge site
│ ├── ha-bare-metal/hosts.yml # deploy shape: HA bare metal
│ └── lab-single-node/hosts.yml # deploy shape: single-node lab
├── requirements.txt # Python control-plane tooling
├── requirements.yml # Galaxy collections
├── roles/
│ └── os_prep/ # OS-prep role (slice-by-slice; see its README)
├── site.yml # top-level orchestration playbook
├── tests/
│ └── smoke/ # real-host smoke harness + runbook (L1.1.7)
└── README.md # this file
```

`.venv/` and `collections/` are local-only and excluded from version control.
Molecule scenarios live inside each role (`roles/<role>/molecule/`), not at
this level — see Conventions.

## Deploy shapes

Three shapes — defined in the
[repo-root README](../README.md#deploy-shapes) — each backed by an
inventory directory under `inventory/`:

| Shape             | Inventory directory          |
| ----------------- | ---------------------------- |
| `lab-single-node` | `inventory/lab-single-node/` |
| `edge-site`       | `inventory/edge-site/`       |
| `ha-bare-metal`   | `inventory/ha-bare-metal/`   |

There is **no default inventory.** Every `ansible-playbook` invocation
must pass `-i inventory/<shape>/` explicitly. This prevents
silently-running-against-the-wrong-shape mistakes; the cost is one extra
argument per command.

## Daily commands

Run Ansible commands from this directory (`bootstrap/`) so `ansible.cfg`
is auto-discovered. Lint and hook commands run from repo root.

| Task                       | Command                                                                                                             | CWD       |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------- |
| Lint everything            | `pre-commit run --all-files`                                                                                        | repo root |
| Smoke test a shape         | `ansible-playbook -i inventory/<shape>/ site.yml --check`                                                           | bootstrap |
| Apply a shape              | `ansible-playbook -i inventory/<shape>/ site.yml`                                                                   | bootstrap |
| Limit to one host          | append `--limit <hostname>` to either of the above                                                                  | bootstrap |
| List installed collections | `ansible-galaxy collection list --collections-path ./collections`                                                   | bootstrap |
| Refresh after a deps bump  | `pip install -r requirements.txt && ansible-galaxy collection install -r requirements.yml -p ./collections --force` | bootstrap |

## Conventions

- **Single source of truth for versions.** Edit
  `group_vars/all/versions.yml`; do not pass `-e` overrides at runtime.
  Version bumps land in dedicated `chore(versions): bump <component>`
  commits so the diff against this file is a complete upgrade audit
  trail.
- **No implicit inventory.** Every play takes `-i inventory/<shape>/`
  explicitly. The `inventory =` default was deliberately removed from
  `ansible.cfg`.
- **Conventional Commits.** Commit messages follow
  [Conventional Commits](https://www.conventionalcommits.org/). Not
  enforced by a hook today; upheld in review.
- **Pre-commit gates every change.** `yamllint`, `ansible-lint` under
  `profile: production`, and standard hygiene hooks. CI re-runs the
  same set so local `--no-verify` skips cannot land on `main`.
- **Per-role Molecule, not global.** When roles land in L1.1+, each
  ships its own Molecule scenario derived from the template (also
  L1.0). There is no top-level Molecule scenario for the playbook as
  a whole.

## Roadmap

| Phase | Scope                                                              | State       |
| ----- | ------------------------------------------------------------------ | ----------- |
| L1.0  | Ansible tooling scaffold                                           | complete    |
| L1.1  | OS prep + container runtime roles                                  | complete    |
| L1.2  | kubeadm + kubelet + kubectl roles                                  | complete    |
| L2    | CNI — Cilium 1.20.x, kube-proxy replacement, Gateway API, BGP (design accepted; ADR-0022..0031) | next |
| L3    | Policy (Kyverno) and admission baseline                            | pending     |
| L4a   | GitOps bootstrap (Flux), secrets at rest (SOPS)                   | pending     |
| Telco | Opt-in telco overlay (hugepages, SR-IOV/DPDK — additive; see below) | pending   |

The **telco overlay** is opt-in and additive to the general-purpose path
(per the three-audience goal — general platform, telco/5G, and application
engineers): a hugepages + CPU Manager / Topology Manager kubelet profile, the
SR-IOV stack (`sriov` device-plugin + `sriov-cni` + the `vfio-pci` module,
the last added to the os_prep load list and kept disjoint from the CIS
blacklist per ADR-0007), and a dedicated `node-role: dataplane` node pool.
Only user-plane CNFs (e.g. a UPF) need it; the general-purpose path does not.
**Multus** is removed from the general-purpose stack (the L2 design adopts
Cilium Egress Gateway for VLAN-pinned pod egress) and is deferred to the
telco overlay, where it is only needed if a line-rate DPDK user-plane
workload appears (see L2 design doc §12, §15).

Decisions are tracked in [`docs/adr/`](../docs/adr/).
