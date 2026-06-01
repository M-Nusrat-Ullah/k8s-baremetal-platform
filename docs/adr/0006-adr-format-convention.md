# ADR-0006: ADR format and metadata convention

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** M Nusrat Ullah
- **Layer:** —
- **Supersedes:** none
- **Superseded by:** none
- **Amends:** ADR-0001 (format prescription)

## Context

ADR-0001 established the practice of recording decisions as Nygard-format
ADRs but did not pin a precise header layout. Over the first five records,
two formats emerged in practice:

- **0001–0003** — title with a colon (`# ADR-NNNN: Title`); metadata as two
  inline bold lines (`**Status:** Accepted, 2026-05-24` and `**Deciders:**`),
  with the decision date folded into the status string.
- **0004–0005** — title with an em-dash (`# ADR-NNNN — Title`); metadata as a
  bullet block carrying `Status`, `Date`, `Layer`, `Supersedes`,
  `Superseded by`, and (where relevant) `Amends` / `Amended by`.

`docs/adr/README.md` documented only the older inline style, and its index
stopped at 0003 — so 0004 and 0005 were both undocumented and unindexed.

The drift is low-stakes individually but undercuts the log's purpose. A
reader cannot rely on a predictable header; supersession and amendment
chains are expressed inconsistently; and to a portfolio reviewer, two
competing formats in a five-file directory read as unfinished rather than
deliberate.

## Decision

Adopt a single hybrid ADR format, and normalize all existing ADRs
(0001–0005) to it. The normalization is format-only: decision text,
dates, deciders, and supersession facts are preserved exactly; only the
title punctuation and the metadata header shape change.

The hybrid keeps the richer metadata block from 0004–0005 (the `Date`,
`Layer`, and supersession fields carry real value) and the section
structure common to all five, and standardizes the title to a colon.

### Convention

**Filename:** `NNNN-kebab-case-title.md`, `NNNN` zero-padded and sequential.

**Title:** `# ADR-NNNN: Title` — colon, sentence case.

**Metadata block** — a bullet list immediately under the title:

- `Status:` — Proposed / Accepted / Deprecated / Superseded by ADR-NNNN
- `Date:` — YYYY-MM-DD, the date the decision was accepted
- `Deciders:` — name(s)
- `Layer:` — the `L#.#` this decision belongs to, or `—` for repo-wide /
  meta decisions
- `Supersedes:` and `Superseded by:` — ADR references or `none`. Always
  present: these two fields are the spine of the decision log, and an
  explicit `none` affirms a record is current rather than leaving it
  ambiguous.
- `Amends:` and `Amended by:` — ADR references. Present **only when they
  apply**; omitted entirely otherwise, since amendment is an occasional
  cross-link rather than part of every record's lifecycle.

**Sections**, in order:

- `Context` — forces and constraints leading to the decision
- `Decision` — what was decided, in active voice. A single ADR may use
  `Decision 1` / `Decision 2` subsections when it settles two tightly
  coupled decisions made together (as ADR-0004 does); do not force these
  into separate records.
- `Consequences` — what becomes easier and harder. May use **Positive:**
  and **Negative:** sub-labels.
- `Alternatives considered` — what else was evaluated and why it lost
- `References` — optional; omit the section when empty

### Supersede vs. amend

These are distinct lifecycle operations and are not interchangeable:

- **Supersede** — a new ADR reverses or replaces a prior decision. The old
  ADR's `Status` becomes `Superseded by ADR-NNNN`; the new ADR carries
  `Supersedes: ADR-NNNN`. The old decision is no longer in force.
- **Amend** — a new ADR refines part of a prior decision that otherwise
  still stands. The old ADR keeps `Status: Accepted` and gains an
  `Amended by: ADR-NNNN` line; the new ADR carries `Amends: ADR-NNNN`. The
  core decision remains in force; only a detail is corrected or sharpened.

ADR-0005 amending ADR-0004 is the worked example: 0004's role structure and
idempotence rule stand; only its swap-module prescription was corrected.

Accepted ADRs remain immutable in substance (ADR-0001's rule is unchanged):
to change a decision, supersede it; to correct a detail, amend it. The
0001–0005 normalization is the one sanctioned exception, and it touches
presentation only — no decision, date, or rationale is altered.

## Consequences

**Positive:**

- Every ADR has a predictable header; the metadata block is machine- and
  human-scannable.
- Supersession and amendment chains are expressed one way, so the decision
  log can be read as a connected history rather than isolated files.
- `docs/adr/README.md` documents the real format and indexes every record,
  so the directory is self-describing.
- A reviewer sees a deliberate, self-consistent convention — the format
  itself becomes evidence of the engineering discipline the repo is meant
  to demonstrate.

**Negative:**

- A one-time reformat touches all five existing files. Mitigated by keeping
  the change format-only and reviewing the diff to confirm no body text
  moved.
- The metadata block is heavier than classic inline Nygard. Mitigated by
  omitting inapplicable `Amends` / `Amended by` lines rather than carrying
  them as `none` noise.

## Alternatives considered

- **MADR (Markdown ADR).** More structured — explicit "considered options"
  with per-option pros and cons. Rejected: migrating five prose-Nygard
  records into MADR's option-table shape would rewrite their bodies, not
  just their headers, violating the format-only constraint; and MADR's
  ceremony earns little for a single engineer.
- **Grandfather the old format** — leave 0001–0003 inline, apply the hybrid
  only to new ADRs. Rejected: this is the drift, formalized. Two formats
  in-tree perpetuate the exact inconsistency this ADR exists to remove, and
  the one-time cost of normalizing three files is trivial.
- **Standardize on classic inline Nygard** (the 0001–0003 style) everywhere.
  Rejected: loses the `Date`, `Layer`, and supersession-chain fields that
  0004–0005 demonstrated are worth carrying.

## References

- ADR-0001 — the meta-ADR establishing the ADR practice; amended by this record
- Michael Nygard, _Documenting Architecture Decisions_ (cognitect.com, 2011)
- [MADR](https://adr.github.io/madr/) — the structured alternative evaluated above
