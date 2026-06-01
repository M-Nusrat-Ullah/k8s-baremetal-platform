# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-05-24
- **Deciders:** M Nusrat Ullah
- **Layer:** —
- **Supersedes:** none
- **Superseded by:** none
- **Amended by:** ADR-0006 (format & metadata convention)

## Context

`k8s-baremetal-platform` is a single-engineer project where architectural
decisions accumulate over many sessions. Without a written record, the
reasoning behind each decision is lost: future-me, reviewers, and hiring
managers reading the repo cannot tell why the cluster runs Cilium instead
of Calico, why containerd 2.x was chosen over 1.7, or why etcd backup is
a CronJob rather than Velero.

ADRs (Architectural Decision Records) are the simplest established
mechanism for capturing this reasoning: one short markdown file per
decision, written _at the time the decision is made_, not retrospectively.

## Decision

Use ADRs to document significant architectural decisions in this
repository, following Michael Nygard's format. ADRs live in `docs/adr/`,
are numbered sequentially (`NNNN-kebab-case-title.md`), and are committed
as part of the change that implements the decision.

A decision is "significant" enough for an ADR if reversing it would
require non-trivial work: changing a CNI, swapping a runtime,
restructuring directories, picking a registry, choosing a policy engine.
Day-to-day implementation details do not need ADRs.

ADRs are immutable once accepted. To change a decision, write a new ADR
that supersedes the old one. The old ADR's status changes to
`Superseded by ADR-NNNN`.

## Consequences

**Positive:**

- Future readers reconstruct _why_ a choice was made, not just _what_.
- Every significant decision gets a 15-minute writing exercise that
  often catches lazy reasoning before it ships.
- The ADR log functions as a portfolio narrative — reviewers trace the
  thinking layer by layer.

**Negative:**

- Slight overhead per decision.
- Risk of over-using ADRs for trivia, mitigated by the significance
  criterion above.

## Alternatives considered

- **Decision records in commit messages.** Lost in noise; hard to find
  later; cannot be revised or superseded cleanly.
- **RFC process (HashiCorp / Rust style).** Heavier than needed for a
  single engineer; designed for community consensus.
- **No formal record.** What past Nybsys projects did. Loses reasoning,
  leads to re-arguing settled decisions.

## References

- Michael Nygard, _Documenting Architecture Decisions_ (cognitect.com, 2011)
- [adr-tools](https://github.com/npryce/adr-tools)
- [MADR](https://adr.github.io/madr/) — alternative format
