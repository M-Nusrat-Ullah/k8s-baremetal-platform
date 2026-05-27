# bootstrap/molecule-template/

Reusable Molecule scenario template — see the parent `bootstrap/README.md`
under "Conventions" for the role-creation workflow, and the comments
inside `molecule.yml`, `converge.yml`, and `verify.yml` for what to edit.

This directory is not itself a runnable scenario; Molecule does not
discover it. The four files exist to be copied into each role's
`molecule/default/` directory at role creation time.

## How to use

When you create a new role:

```bash
# CWD: bootstrap/
mkdir -p roles/<role-name>/molecule
cp -r molecule-template/ roles/<role-name>/molecule/default
```

Then edit the copied files:

**`molecule.yml`** — replace the `geerlingguy/docker-ubuntu2404-ansible:latest`
tag with a digest pin (`sha256:...`). Inspect the image you actually
want with:

```bash
docker pull geerlingguy/docker-ubuntu2404-ansible:latest
docker image inspect geerlingguy/docker-ubuntu2404-ansible:latest --format '{{index .RepoDigests 0}}'
```

**`converge.yml`** — replace `roles_under_test` with the actual role
name (and list any role dependencies before it).
**`verify.yml`** — replace the `ansible.builtin.fail` placeholder
with real `ansible.builtin.assert` tasks. Until this is done, the
scenario will fail by design.

## Why a template, not a generator

Editing three small files per role is less complex than maintaining a
template-expansion script. The drawback is that improvements here do
not auto-propagate to existing role scenarios. That trade-off is
acceptable while the role count is small; if a future "update all
scenarios" pain becomes real, a generator script can replace this
template then.

## Why not lint the template

`ansible-lint` excludes `bootstrap/molecule-template/` because the
files contain placeholders (`roles_under_test`, the `fail` task in
`verify.yml`) that intentionally cannot pass `profile: production`
checks. Once a role copies the template into its own
`molecule/default/`, the linter sees the customised versions and
applies the full ruleset.

## Driver choice

Docker, using the `geerlingguy/docker-ubuntu2404-ansible` image
family. These images bundle systemd, Python, and the small set of
tooling Ansible needs to converge inside a container — saving every
scenario from re-deriving systemd setup. Jeff Geerling updates them
roughly monthly; bump the digest pin in your role's `molecule.yml`
when upstream releases.
If a role needs a non-Ubuntu platform (RHEL, Debian), add it as an
additional entry under `platforms:` in that role's `molecule.yml`. Do
not modify this template to add multi-platform support — keep the
template minimal.
