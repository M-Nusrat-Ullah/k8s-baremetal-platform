# k8s-baremetal-platform

Production-grade Kubernetes platform for bare-metal and on-prem deployments.
Built as a personal portfolio project; intended to host telco-shaped workloads
(5G core, TR-069 ACS edge) alongside general application workloads.

## Status

**In development.** Layer 1.1 (node OS baseline) in progress: the `os_prep`
Ansible role is built slice-by-slice and validated on real hardware via a
reboot smoke test (through L1.1.7). Layer 1.0 (Ansible tooling scaffold)
complete. See [`docs/adr/`](docs/adr/) for the running log of design decisions.

## Who this is for

This repository is a general-purpose Kubernetes platform that supports
several specialised workload classes through opt-in features. The core
cluster (Layers 1–4) is workload-agnostic.

- **Platform / SRE engineers** deploying Kubernetes to bare metal or
  on-prem VMs who want a hardened, GitOps-driven baseline without
  inheriting cloud-provider assumptions.
- **Telco / 5G engineers** who need Multus secondary networks, BGP,
  and per-workload privilege exceptions (UPF, SecGW, IPsec gateways)
  layered on top of a standard cluster — not as forks of it.
- **Application engineers** wanting a reference of what
  production-posture Kubernetes looks like end to end: hardening,
  policy, observability, supply chain.

Telco features are opt-in per workload, not always-on. A general
application can be deployed without touching Multus, BGP, or
NetworkAttachmentDefinitions.

## Quick links

- [Architecture Decision Records](docs/adr/)
- Bootstrap (Ansible, kubeadm) — Layer 1, pending
- GitOps (Flux) — Layer 4, pending

## Design pillars

- **Reproducible.** Every component is version- or digest-pinned.
- **Hardened by default.** Pod Security Standards `restricted`, default-deny
  NetworkPolicy, AESCBC encryption at rest, audit logging — applied at
  bootstrap, not bolted on after.
- **GitOps-driven.** Ansible bootstraps the cluster (kubeadm + CNI + Flux);
  everything after that is reconciled by Flux from this repository.
- **Telco-aware.** Multus secondary networks and BGP integration are
  available as opt-in per workload, not always-on.

## Deploy shapes

| Shape             | Topology                        | Use case                           |
| ----------------- | ------------------------------- | ---------------------------------- |
| `lab-single-node` | 1 node, control plane untainted | Local development, learning        |
| `edge-site`       | 1 CP + 2–3 workers, no HA       | On-prem edge / cell-site footprint |
| `ha-bare-metal`   | 3 CP + 3+ workers               | Production HA                      |

## License

Apache 2.0. See [LICENSE](LICENSE).

Copyright 2026 M Nusrat Ullah.
