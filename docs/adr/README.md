# Architecture Decision Records

This directory holds Architecture Decision Records (ADRs) for the
`k8s-baremetal-platform` project, following Michael Nygard's format.

Each ADR is a short markdown file documenting one significant decision:
what was decided, what led to it, what alternatives were on the table,
and what consequences follow. ADRs are immutable once accepted — to
change a decision, write a new ADR that supersedes the old one.

## Format

Files are named `NNNN-kebab-case-title.md` where `NNNN` is a
zero-padded sequential number. Sections:

- **Status** — Proposed / Accepted / Deprecated / Superseded by ADR-NNNN
- **Context** — forces and constraints leading to the decision
- **Decision** — what was decided, in active voice
- **Consequences** — what becomes easier and harder as a result
- **Alternatives considered** — what else was evaluated and why it lost

See [ADR-0001](0001-record-architecture-decisions.md) for the meta-ADR
introducing this process.

## Index

| #    | Title                         | Status   |
| ---- | ----------------------------- | -------- |
| 0001 | Record architecture decisions | Accepted |
