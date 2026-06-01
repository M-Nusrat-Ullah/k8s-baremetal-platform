# ADR-0008: Ansible collections provisioning and resolution

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1
- **Supersedes:** none
- **Superseded by:** none

## Context

The repository pins its Ansible collection dependencies in
`bootstrap/requirements.yml` (community.general, ansible.posix,
community.crypto, kubernetes.core, community.docker — each pinned to an
exact version) and installs them into `bootstrap/collections/`, which is
gitignored and rebuilt per environment with:

    ansible-galaxy collection install -r bootstrap/requirements.yml \
      -p bootstrap/collections

`bootstrap/ansible.cfg` sets `collections_path = ./collections`, so an
operator running `ansible-playbook` from inside `bootstrap/` resolves the
pinned set correctly. This worked for every slice up to L1.1.1 because
those slices used only built-in modules.

L1.1.2 was the first slice to use a non-builtin module
(`community.general.modprobe`), which surfaced a problem the design had
been masking: **every tool that does not run from `bootstrap/` with that
`ansible.cfg` active fails to resolve the pinned collections.** The same
root cause appeared in three different tools in one session:

1. **Molecule** — runs from the scenario directory, not `bootstrap/`, so
   it never read `bootstrap/ansible.cfg`; `converge` failed to resolve
   `community.general.modprobe`.
2. **ansible-lint** — ignores `collections_path` from `ansible.cfg`
   entirely (a long-standing upstream behaviour, issues #1771 and #4851)
   and computes its own collection search path; `syntax-check` failed on
   the same module.
3. **Ad-hoc `ansible-playbook` from the repo root** — would hit the same
   wall for the same reason.

The `ansible.cfg` `collections_path` setting is therefore necessary but
not sufficient: it covers only the operator-from-`bootstrap/` path. Each
additional tool was being patched with its own mechanism, which does not
scale and is the kind of per-tool special-casing that accumulates into
unmaintainable friction.

## Decision

Standardize on a single resolution mechanism that every tool honours: the
`ANSIBLE_COLLECTIONS_PATH` environment variable, pointing at
`bootstrap/collections`. It is set once per environment, by the mechanism
native to that environment:

- **Local development** — a checked-in `.envrc` (direnv) at the repo root
  exports `ANSIBLE_COLLECTIONS_PATH="${PWD}/bootstrap/collections"`. After
  a one-time `direnv allow`, every local tool — `ansible-playbook`,
  `molecule`, `ansible-lint`, and the pre-commit hook that wraps it —
  inherits the variable automatically.
- **Operators running `ansible-playbook` from `bootstrap/`** — already
  covered by `bootstrap/ansible.cfg`'s `collections_path`. No direnv
  required on a target host; the cfg is sufficient for the deployment
  path.
- **CI** — the workflow job sets the same variable in its environment.
  Deferred until a workflow exists (the `.github/workflows/` directory is
  currently empty); when CI is introduced, exporting this variable is part
  of that work.

The collections themselves remain gitignored and rebuilt per environment
from the pinned `requirements.yml`, rather than vendored into git. Pinning
lives in `requirements.yml`; this ADR governs only how the installed set
is *resolved*, not how it is versioned.

`.envrc` is committed to the repository (and removed from the `.gitignore`
credentials block, where it had been ignored alongside `.env`). It holds
only a non-sensitive path, not secrets; committing it is what makes the
local setup reproducible across clones. Secret-bearing `.env` files remain
ignored.

### Molecule `config_options` retained as defense-in-depth

The Molecule scenario also sets
`provisioner.config_options.defaults.collections_path` to the same
`bootstrap/collections` path. With `ANSIBLE_COLLECTIONS_PATH` exported via
direnv, this is redundant — Molecule inherits the environment variable.

It is kept deliberately. The explicit `config_options` makes the scenario
self-contained: it resolves the pinned collections even when run in a
shell where direnv did not load (a fresh terminal before `direnv allow`,
an editor-spawned subprocess, a CI runner before its env is wired). The
cost is one configuration line; the benefit is that the scenario does not
silently depend on ambient shell state. This is the one intentional
exception to the "single mechanism" rule, and it is additive — it points
at the same path, so it cannot diverge from the env-var resolution.

## Consequences

**Positive:**

- One variable resolves collections for every tool in every environment;
  no per-tool special-casing beyond the one documented Molecule exception.
- The pinned, version-locked collection set is what every tool sees —
  lint, test, and run all validate against the same versions that ship.
- Local onboarding is a documented, reproducible sequence (install direnv,
  `direnv allow`, install collections) rather than tribal knowledge.
- The CI path is pre-decided: when a workflow lands, the resolution
  mechanism is already specified.

**Negative:**

- Local development gains a direnv dependency. Mitigated: direnv is a
  single apt package and one shell-hook line, and the operator/deploy path
  deliberately does not require it.
- Two resolution mechanisms coexist (env var + the retained Molecule
  `config_options`). Accepted and documented above as intentional
  redundancy pointing at one path, not drift.
- `ANSIBLE_COLLECTIONS_PATH`, like any path env var, is process-inherited;
  a tool launched from an environment where direnv has not loaded will not
  see it. This is precisely why the operator path falls back to
  `ansible.cfg` and the Molecule scenario keeps its explicit config.

## Alternatives considered

- **Rely on `ansible.cfg` `collections_path` alone.** Rejected: it does
  not cover tools that run outside `bootstrap/`, and ansible-lint ignores
  it outright. This is the status quo that failed.
- **Set `ANSIBLE_COLLECTIONS_PATH` per tool** (a pre-commit hook env, a
  Molecule env block, a shell export, each separately). Rejected: the same
  value duplicated across N tools is N places to drift; one environment
  export covers them all.
- **Mock the collection modules in `.ansible-lint`** (`mock_modules`).
  Rejected: it makes lint *pretend* the module exists, suppressing real
  validation of module usage, and the mock list grows with every
  collection module the repo uses. It contradicts the `profile: production`
  / empty-`skip_list` posture.
- **Vendor `bootstrap/collections` into git** so any tool finds it on a
  default path. Rejected: commits thousands of third-party files, bloats
  the repo, and turns dependency bumps into large opaque diffs.
  `requirements.yml` is the version source of truth; the installed tree is
  a build artifact.
- **Install collections to a default search path** (e.g.
  `~/.ansible/collections` or the repo-root `.ansible/collections` that
  ansible-lint already scans). Rejected: pollutes a shared/global location
  with project-specific pinned versions, risking cross-project version
  collisions; keeping the set repo-local under `bootstrap/collections` and
  pointing tools at it is cleaner.

## References

- ADR-0004 — `os_prep` role structure; L1.1.2 surfaced this issue
- ADR-0007 — kernel module strategy; the `community.general.modprobe`
  usage that first required a non-builtin collection
- ansible-lint issues #1771 and #4851 — `collections_path` from
  `ansible.cfg` is ignored; `ANSIBLE_COLLECTIONS_PATH` is the supported lever
