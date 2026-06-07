# ADR-0021: site.yml role composition — single play per role; kube_bootstrap self-gates

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.2
- **Supersedes:** none
- **Superseded by:** none

## Context

`bootstrap/site.yml` composes five roles across three deploy shapes
(`lab-single-node`, `edge-site`, `ha-bare-metal`). Four of the roles
(`os_prep`, `containerd`, `kube_install`, `kube_bootstrap`) run across all
nodes, but `kube_bootstrap` has distinct behaviour per host role:

- `init.yml` + `kubeconfig.yml` + `untaint.yml` → `control_plane[0]` only
- `join.yml` → hosts in `workers` only

The question is whether to express this split at the **play level**
(separate plays for CP and workers) or at the **role level** (one play on
`all`; the role's `main.yml` gates per host).

`kube_bootstrap/tasks/main.yml` already carries explicit `when:` conditions
on every `include_tasks` call — `inventory_hostname == groups['control_plane'][0]`
for init/kubeconfig/untaint and `inventory_hostname in groups['workers']` for
join. The role was built to be invoked once on `all` and self-route.

`join.yml` handles the cross-host token dependency via the standard
`delegate_to: groups['control_plane'][0]` + `run_once: true` pattern:
the join command is generated on the CP and consumed by workers through
the registered variable. This pattern works correctly under a single play
on `all`.

## Decision

Use **one play per role** in `site.yml`. `kube_bootstrap` is invoked as a
single play targeting `all`; host-role routing stays in `main.yml`.

The default Ansible `linear` strategy guarantees init-before-join ordering
without any additional coordination: linear synchronises all hosts at each
top-level task, so the CP's `init.yml` include (task 1) completes on every
host's clock before any worker's `join.yml` include (task 4) begins.

The `Run:` block in `site.yml`'s header is updated to document
`--tags kube_bootstrap` as the targeted re-run path.

## Consequences

**Positive:**

- Host-role routing logic lives in exactly one place (`main.yml`); `site.yml`
  does not duplicate or shadow it.
- Adding secondary control-plane join for `ha-bare-metal` (cp2/cp3,
  `kubeadm join --control-plane`) is a new self-gated include in `main.yml`
  with no change to `site.yml`.
- A reviewer reading `site.yml` sees the play structure and is directed to
  `main.yml` comments for per-host routing detail — separation of concerns
  is explicit.

**Negative:**

- Init-before-join ordering depends on `strategy: linear` (the default).
  Switching the `kube_bootstrap` play to `strategy: free` would break the
  guarantee silently. This risk is documented in the play's inline comment.
- On `lab-single-node`, `join.yml` is still entered (the node is in
  `workers`) and mints a throwaway join token before the `kubelet.conf`
  idempotency guard skips the actual join. The token is harmless but
  unnecessary. A future `kube_bootstrap_deploy_shape != 'lab-single-node'`
  guard on the join include in `main.yml` would eliminate it.

## Alternatives considered

- **Two plays: `control_plane[0]` + `workers:!control_plane`.** Expresses
  host-role routing at the play level — closer to Kubespray's style. Rejected
  because it either makes `main.yml`'s `when:` conditions dead code (if
  `tasks_from:` bypasses them) or requires rewriting `main.yml` to remove
  gating that was deliberately placed there. Either outcome splits the routing
  logic across two files for no net gain.
- **One play on `all` with `strategy: free`.** Eliminates the synchronisation
  barrier; join would race against init. Rejected: ordering cannot be
  guaranteed without explicit `wait_for` coordination tasks, which adds
  complexity that the linear default eliminates for free.
