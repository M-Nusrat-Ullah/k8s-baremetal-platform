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

Layer 1.0 — Ansible tooling scaffold — is in progress. No roles or
provisioning logic exist yet; that work begins in L1.1+.

What lives here today:

- Hardened `ansible.cfg` with pipelining, persistent SSH ControlMaster,
  YAML-formatted task output, and in-memory fact caching.
- Pinned Python tooling (`requirements.txt`) and Galaxy collections
  (`requirements.yml`).
- Component version registry at `group_vars/all/versions.yml` — values
  are `null` placeholders pending dedicated pin commits.
- Per-shape inventory skeletons under `inventory/<shape>/`.
- Trust-establishment stub playbook (`site.yml`) that pins SSH host keys
  on first contact (`StrictHostKeyChecking=accept-new`) and verifies
  reachability via the `ping` module.
- Lint configs (`.yamllint`, `.ansible-lint` with `profile: production`)
  and pre-commit hooks — these live at the repo root and apply
  repo-wide.

What is not here yet:

- No roles. The first roles (OS prep, container runtime, kubeadm)
  land in L1.1+.
- No Molecule scenarios. A reusable template directory ships at the
  end of L1.0.
- No populated inventory. Each shape's `hosts.yml` declares the
  group structure with empty `hosts: {}` until a real target exists.

## Quick start

Python 3.12+ is required (ansible-core 2.20's floor). Ubuntu 24.04 LTS
ships 3.12.3 and is the validated host.

```bash
# CWD: repo root
git clone https://github.com/M-Nusrat-Ullah/k8s-baremetal-platform
cd k8s-baremetal-platform

# 1. Create and activate the per-layer virtualenv
python3 -m venv bootstrap/.venv
source bootstrap/.venv/bin/activate

# 2. Install Python tooling
pip install --upgrade pip
pip install -r bootstrap/requirements.txt

# 3. Install Galaxy collections into the layer-local path
(cd bootstrap && ansible-galaxy collection install -r requirements.yml -p ./collections)

# 4. Wire up the pre-commit git hook (one-time per clone)
pre-commit install

# 5. Smoke test — should print "skipping: no hosts matched" with no errors
(cd bootstrap && ansible-playbook -i inventory/lab-single-node/ site.yml --check)
```

If step 5 prints `PLAY RECAP ***` with no host lines and exits cleanly,
the layer is correctly set up.

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
├── site.yml # top-level orchestration playbook
└── README.md # this file
```

`.venv/` and `collections/` are local-only and excluded from version
control. The `roles/` and `molecule/` directories will appear as L1.0
completes and L1.1 begins.

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
| L1.0  | Ansible tooling scaffold (in progress)          |
| L1.1  | OS prep + container runtime roles               |
| L1.2  | kubeadm + kubelet + kubectl roles               |
| L2.x  | CNI (Cilium, kube-proxy replacement) and Multus |
| L3    | Policy (Kyverno) and admission baseline         |
| L4a   | GitOps bootstrap (Flux), secrets at rest (SOPS) |

Decisions are tracked in [`docs/adr/`](../docs/adr/). Future ADRs will
cover the Ansible tooling baseline and the versions-registry shape
decision; until they land, the rationale lives in code comments inside
`ansible.cfg` and `versions.yml`.
