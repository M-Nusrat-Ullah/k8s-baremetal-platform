# bootstrap/

The Ansible bootstrap layer for the `k8s-baremetal-platform` project. This
directory contains the imperative provisioning logic that takes
freshly-provisioned Linux hosts to a running Kubernetes cluster: OS prep,
container runtime, kubeadm-driven control plane, CNI, Multus, and the Flux
bootstrap that hands ongoing operation to GitOps.

For project-level context (audiences, design pillars, deploy shapes), see
the [repo-root README](../README.md). For design decisions, see
[`docs/adr/`](../docs/adr/).

## Current state

Layer 1.0 (Ansible tooling scaffold) is complete; Layer 1.1 is in progress.
The `os_prep` role is under active, slice-by-slice development
(`roles/os_prep/`): swap, kernel modules, sysctls, chrony, AppArmor, the CIS
filesystem-module blacklist, and the real-host smoke-test harness (L1.1.7) have
landed; the container-runtime role follows. See
[`roles/os_prep/README.md`](roles/os_prep/README.md) for per-slice detail,
[`tests/smoke/README.md`](tests/smoke/README.md) for the smoke-test runbook, and
[`docs/adr/`](../docs/adr/) for the decision behind each.

What lives here today:

- Hardened `ansible.cfg` with pipelining, persistent SSH ControlMaster,
  YAML-formatted task output, and in-memory fact caching.
- A repo-root `.envrc` (direnv) that activates the layer virtualenv and
  exports the pinned `ANSIBLE_COLLECTIONS_PATH` on entry — see Quick start.
- Pinned Python tooling (`requirements.txt`) and Galaxy collections
  (`requirements.yml`).
- The `os_prep` role with its own Molecule scenario (per-role, not global —
  see Conventions).
- Component version registry at `group_vars/all/versions.yml` — values are
  `null` placeholders pending dedicated pin commits.
- Per-shape inventory skeletons under `inventory/<shape>/`.
- Top-level `site.yml`: a trust play that pins SSH host keys on first contact
  (`StrictHostKeyChecking=accept-new`) and verifies reachability via `ping`,
  then a node-baseline play that applies the `os_prep` role to every host.
- Lint configs (`.yamllint`, `.ansible-lint` with `profile: production`) and
  pre-commit hooks — these live at the repo root and apply repo-wide.

What is not here yet:

- The container-runtime and kubeadm roles (L1.1+/L1.2).
- Fully populated inventory. `lab-single-node` carries the lab host (placeholder
  connection values — real ones kept local); `edge-site` and `ha-bare-metal`
  remain group-structure skeletons with empty `hosts: {}` until real targets
  exist.

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

| Phase | Scope                                           |
| ----- | ----------------------------------------------- |
| L1.0  | Ansible tooling scaffold (complete)             |
| L1.1  | OS prep + container runtime roles (in progress) |
| L1.2  | kubeadm + kubelet + kubectl roles               |
| L2.x  | CNI (Cilium, kube-proxy replacement) and Multus |
| L3    | Policy (Kyverno) and admission baseline         |
| L4a   | GitOps bootstrap (Flux), secrets at rest (SOPS) |
| Telco | Opt-in telco overlay (additive — see below)     |

The **telco overlay** is opt-in and additive to the general-purpose path
(per the three-audience goal — general platform, telco/5G, and application
engineers): a hugepages + CPU Manager / Topology Manager kubelet profile, the
SR-IOV stack (`sriov` device-plugin + `sriov-cni` + the `vfio-pci` module,
the last added to the os_prep load list and kept disjoint from the CIS
blacklist per ADR-0007), and a dedicated `node-role: dataplane` node pool.
Only user-plane CNFs (e.g. a UPF) need it; the general-purpose path and the
standard control-plane workloads — including the HAProxy/ACS proxy — do not.

Decisions are tracked in [`docs/adr/`](../docs/adr/). Future ADRs will
cover the Ansible tooling baseline and the versions-registry shape
decision; until they land, the rationale lives in code comments inside
`ansible.cfg` and `versions.yml`.
