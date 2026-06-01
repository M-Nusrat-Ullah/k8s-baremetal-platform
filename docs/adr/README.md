# Architecture Decision Records

This directory holds Architecture Decision Records (ADRs) for the
`k8s-baremetal-platform` project. Each ADR is a short markdown file
documenting one significant decision: what was decided, what led to it,
what alternatives were on the table, and what consequences follow.

ADRs are immutable in substance once accepted. To reverse a decision,
write a new ADR that supersedes the old one; to refine a detail of a
decision that otherwise still stands, write one that amends it. See
[ADR-0001](0001-record-architecture-decisions.md) for the meta-ADR
establishing the practice, and
[ADR-0006](0006-adr-format-convention.md) for the format and metadata
convention all records follow.

## Format

Files are named `NNNN-kebab-case-title.md`, where `NNNN` is a zero-padded
sequential number. The title is `# ADR-NNNN: Title`.

A metadata block follows the title as a bullet list:

- **Status** — Proposed / Accepted / Deprecated / Superseded by ADR-NNNN
- **Date** — YYYY-MM-DD, the date the decision was accepted
- **Deciders** — name(s)
- **Layer** — the `L#.#` the decision belongs to, or `—` for repo-wide or
  meta decisions
- **Supersedes** / **Superseded by** — ADR references, or `none`; always
  present
- **Amends** / **Amended by** — ADR references; present only when they
  apply, omitted otherwise

The body sections, in order, are **Context**, **Decision**,
**Consequences**, **Alternatives considered**, and an optional
**References**. A single ADR may use `Decision 1` / `Decision 2`
subsections when it settles two tightly coupled decisions together.
ADR-0006 is the authoritative specification and serves as a worked
example of the format.

### Supersede vs. amend

- **Supersede** replaces a decision: the old ADR's status becomes
  `Superseded by ADR-NNNN` and the decision is no longer in force.
- **Amend** refines part of a decision that otherwise still stands: the
  old ADR keeps `Status: Accepted` and gains an `Amended by` line.

ADR-0005 amending ADR-0004 is the worked example.

## Index

| #    | Title                                                   | Layer | Status   |
| ---- | ------------------------------------------------------- | ----- | -------- |
| 0001 | Record architecture decisions                           | —     | Accepted |
| 0002 | Repository structure                                    | —     | Accepted |
| 0003 | Kubernetes version pin and upgrade strategy             | —     | Accepted |
| 0004 | `os_prep` role structure and idempotence as design rule | L1.1  | Accepted |
| 0005 | Swap disable strategy                                   | L1.1  | Accepted |
| 0006 | ADR format and metadata convention                      | —     | Accepted |
| 0007 | Kernel module strategy for `os_prep`                    | L1.1  | Accepted |
| 0008 | Ansible collections provisioning and resolution         | L1.1  | Accepted |
