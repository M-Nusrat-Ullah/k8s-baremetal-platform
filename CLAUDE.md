# k8s-baremetal-platform — Claude Code working agreement

Mechanical implementation on Sonnet. Authoritative spec:
docs/architecture/L2-cilium-cni-design.md — read the relevant § before editing.
HARDENING / CLUSTER_BASELINE / PRIVILEGED_EXCEPTIONS and the local reference docs
in docs/reference/ (gitignored) are binding constraints — read by path when a slice needs them.

## Model escalation — tell me, don't push through
- Default model (Sonnet 4.6): fine for file-writing, YAML, lint fixes, commits.
- STOP and say "needs Opus + thinking — switch the model to Opus and turn Thinking on"
  on: a decision not already settled in the design doc; an unexpected lint/molecule/version
  failure whose cause isn't obvious; anything the doc doesn't fully specify. Never guess
  version-specific Cilium/kubeadm behavior or invent image digests — look it up or stop.
- When the next step is pure transcription again, say "mechanical — Sonnet is fine".

## Hard rules
- Stage file-by-file (never git add -A); git status between commits; code and ADR in
  SEPARATE commits.
- Conventional Commits, scoped, <=52-char imperative subject, blank line after subject.
- pre-commit (yamllint + ansible-lint production profile) fully GREEN before staging; run
  `direnv exec . pre-commit run --all-files` on a clean tree first.
- Run venv tools via `direnv exec . <cmd>` — direnv owns the venv, never source it manually.
- ansible.posix / ansible.builtin only — no command/shell for what a module does. All role
  vars prefixed with the role name. Facts as ansible_facts['x'].
- Molecule inner loop: create once, converge repeatedly, verify after task groups,
  idempotence separately, destroy at end — never `molecule test` in the loop.
- Trailing-newline discipline before staging; eyeball markdown on GitHub after .md commits.
- No scope creep: flag unrelated issues, don't fix them.
- NEVER `git add` anything under `docs/reference/` — files there are
  confidential (CEO-supplied), gitignored, and must never enter history.
