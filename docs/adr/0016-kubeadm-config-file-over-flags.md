# ADR-0016: kubeadm driven by config file, not CLI flags

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.2
- **Supersedes:** none
- **Superseded by:** none

## Context

`kubeadm init` accepts configuration either as CLI flags or as a
structured config file passed via `--config`. CLI flags are the path of
least resistance for quick labs; a config file is the canonical
production pattern. The locked stack requires expressing `skipPhases:
[addon/kube-proxy]` and per-shape differences (`controlPlaneEndpoint`
present for `ha-bare-metal`, absent for `lab-single-node`). Neither is
ergonomic as CLI flags, especially inside an Ansible task.

## Decision

All `kubeadm init` and `kubeadm join` invocations use `--config` with a
templated multi-document YAML file (`kubeadm-config.yaml.j2`). No
cluster-shaping flags are passed on the CLI. The API version is
`kubeadm.k8s.io/v1beta4` — current for Kubernetes 1.34; v1beta3 is
deprecated since 1.31 and not used.

## Consequences

**Positive:**

- The config file is a first-class repo artifact, Jinja2-templated,
  diff-able in PRs, and carries inline rationale comments.
- `skipPhases` and conditional fields (`controlPlaneEndpoint`) are
  expressed cleanly without conditional flag injection in shell tasks.
- The `kubeadm-config` ConfigMap written by kubeadm at init reflects the
  template exactly, making post-init inspection via `kubectl -n kube-system
  get cm kubeadm-config -o yaml` reliable.
- A portfolio reviewer sees structured, commented config rather than a
  flag-assembled shell invocation.

**Negative:**

- Any new kubeadm option must be added to the template, not to the
  `kubeadm init` command line. Requires discipline to maintain.

## Alternatives considered

**CLI flags only.** Simpler for single-node labs. Rejected: cannot express
`skipPhases` cleanly; produces an Ansible task that grows flags over time
with no canonical record of what was passed.

**Mixed (flags + minimal config file).** Some guides pass `--pod-network-cidr`
as a flag while writing a partial config for other options. Rejected: the
seam between what is in the file and what is on the CLI is opaque and
error-prone; the template approach is strictly cleaner.

## References

- kubeadm Configuration API v1beta4 — https://kubernetes.io/docs/reference/config-api/kubeadm-config.v1beta4/
