# ADR-0010: chrony for node time synchronization in `os_prep`

- **Status:** Accepted
- **Date:** 2026-06-03
- **Deciders:** M Nusrat Ullah
- **Layer:** L1.1
- **Supersedes:** none
- **Superseded by:** none
- **Amended by:** ADR-0013

## Context

The `os_prep` role (ADR-0004) prepares each node's OS baseline as a sequence of
per-concern slices. This slice (L1.1.4) establishes time synchronization.

Disciplined, agreed time is a Kubernetes correctness prerequisite, not a
nicety. TLS certificate validity windows, etcd lease and Raft election timing,
kubelet-to-apiserver token authentication, and cross-node log ordering all
assume node clocks agree to within a small margin. A node whose clock drifts
silently is a correctness fault, not a cosmetic one.

Ubuntu 24.04 (noble), the only supported platform (ADR-0003 pins the stack;
the role declares noble-only), ships `systemd-timesyncd` as its default time
daemon and does not install chrony. timesyncd became non-default upstream in
Ubuntu 25.10, which switched to chrony. So this slice is a deliberate
divergence from the running noble default, and the divergence is what needs
justifying — installing chrony means owning a package and a config file that
the base system does not otherwise carry.

Several decisions are settled together here because they are tightly coupled:
which daemon, how the two are prevented from racing, how the package is
versioned, what the config file contains, and what is deliberately excluded
from it.

## Decision

### Decision 1 — chrony over systemd-timesyncd

Install and run chrony as the node's sole time source. systemd-timesyncd is an
SNTP client: it polls upstream and steps the clock, but keeps no drift model,
so when the upstream becomes unreachable it stops disciplining the clock and
the hardware oscillator free-runs. chrony maintains a drift file and continues
correcting the clock through an upstream outage from its learned rate. For the
`edge-site` and `ha-bare-metal` deploy shapes, where uplinks are intermittent
and sites may be partially isolated, this is a concrete operational difference,
not a theoretical one. chrony can additionally serve time to peers — useful for
an isolated site with one upstream-connected node — which timesyncd cannot do
at all.

The cost, recorded honestly: on noble this adds one package and one config file
to own and patch, where timesyncd is already present at zero install cost. The
choice also aligns with the upstream direction (chrony is the 25.10+ default),
which de-risks it on the maintenance horizon. Applied uniformly across all
three deploy shapes — including `lab-single-node`, where it is mild overkill —
because cross-shape consistency is worth more than saving one package on the
lab profile.

### Decision 2 — systemd-timesyncd is stopped, disabled, and masked by the role

> **Amended by ADR-0013 (L1.1.7, verified on hardware).** The decision below —
> mask timesyncd so it can never race chrony — stands. Its mechanism and
> rationale are corrected: on noble, installing chrony *removes* the
> `systemd-timesyncd` package outright (both provide the `time-daemon` virtual
> package and chrony conflicts with it), so by the time the role acts the unit
> is usually already absent. Two consequences for the original text below:
> (1) the "reversible ... unlike removing the package" contrast is moot — the
> package removal is what actually happens, and the mask is layered on top as a
> forward-guard against any later reinstall; (2) a single `systemd_service` call
> with `state: stopped` fails on the absent unit, so the role now gathers
> service facts, stops/disables timesyncd *only when present*, and writes the
> `/dev/null` mask symlink unconditionally (idempotent, absence-tolerant). The
> end state — masked, not racing chrony — is unchanged and is asserted in
> `verify.yml` exactly as before. Verified on noble 6.8 (GA) and 6.17 (HWE).
> The "Remove systemd-timesyncd with apt" alternative listed below is, in
> practice, what the chrony install does; it is no longer a path we reject but
> the observed behaviour we mask on top of.

Two time daemons must never run at once; they fight over the clock. The chrony
package's post-install is documented to disable timesyncd, but the exact
mechanism and timing on noble could not be confirmed and varies on upgraded
systems. Rather than depend on that side effect, the role explicitly stops,
disables, and **masks** `systemd-timesyncd` (`systemctl mask` → symlink to
`/dev/null`). Masking is the strong form: a masked unit cannot be pulled back
in as a dependency of something else, unlike a merely disabled unit. It is also
reversible (`systemctl unmask`), unlike removing the package, so the decision is
recoverable and does not perturb the systemd package set.

This is a live systemd action, so per the role's persist/guarded split
(ADR-0004) it is guarded out of containers and exercised on real hosts and at
the L1.1.7 smoke test. timesyncd is handled before chrony is started so the two
never run simultaneously.

### Decision 3 — `state: present`, no version pin, no `apt-mark hold`

chrony is installed with `state: present` (install if absent; never force an
upgrade per run) and is **not** held at a pinned version, unlike the Kubernetes
stack (kubelet/kubeadm/containerd), which ADR-0003 pins and holds.

This is a deliberate, narrow exception to the repository's version-pinning
pillar, and it is the correct default for an OS utility daemon:

- Exact apt-version pins age out of the noble archive as the package is
  superseded by security updates; `apt install chrony=<old>` then fails
  outright. Pinning would manufacture the exact reproducibility break it is
  meant to prevent.
- chrony is a network-facing daemon. Holding it at a fixed version blocks
  security updates — the wrong posture for an attack-surface component.
- The reproducibility boundary for a base OS utility is the pinned
  distribution release (noble, ADR-0003), not a per-package version. The
  Kubernetes components are pinned because version skew across them breaks the
  cluster; chrony has no such coupling.

`state: latest` is also rejected: it re-evaluates and may upgrade on every run,
producing churn and non-determinism (and slow apt work on the HDD dev target).

### Decision 4 — the role owns chrony.conf in full

The config is rendered from a template to `os_prep_chrony_conf_file`
(`/etc/chrony/chrony.conf`), and the file deliberately omits the distribution's
`confdir`/`sourcedir` include directives. With those includes gone, the shipped
`/etc/chrony/sources.d/ubuntu-ntp-pools.sources` is left inert and the active
time sources are exactly `os_prep_chrony_servers`. This is the determinism the
baseline wants: every node's effective time config is one auditable file, not a
composition of role output and whatever the package shipped. The cost is that
the role must carry the handful of baseline directives itself rather than
inheriting upstream changes to the shipped defaults; accepted for auditability.

The file's content beyond the sources:

- **`driftfile /var/lib/chrony/chrony.drift`** — the learned-rate store that is
  the entire reason chrony is chosen over timesyncd (Decision 1).
- **`makestep 1.0 3`** — step the clock rather than slew if the offset exceeds
  one second, but only for the first three updates: correct a large
  boot-time offset as a single jump so TLS, etcd, and kubelet auth see correct
  time immediately, while steady-state corrections are slewed so time never
  jumps backward under running workloads.
- **`rtcsync`** — let the kernel sync the hardware clock from system time, so a
  reboot starts near-correct before NTP is reachable.
- **Client-only posture** — no `allow` directive, so the node does not serve
  time and the command socket stays bound to localhost.

`os_prep_chrony_servers` defaults to the public NTP Pool purely so a fresh node
syncs at all; it is explicitly a bootstrap value, to be overridden with site or
internal NTP servers (`type: server`) for production, edge, and air-gapped
deployments via `group_vars`/`host_vars`.

### Deliberately excluded

- **`leapsectz right/UTC`.** Ubuntu's own default chrony.conf carries this, but
  it is omitted here. On noble the leap-aware `right/` zoneinfo was split into
  the separate `tzdata-legacy` package, which is not installed by default and
  which Ubuntu's chrony package deliberately stopped depending on. With the
  directive present but the `right/UTC` data absent, chronyd rejects the
  directive and logs a recurring error for no functional gain. Leap seconds are
  handled by the upstream server's NTP leap-indicator regardless — the standard
  mechanism — so the directive is an enhancement, not a requirement. Including
  it would mean pulling `tzdata-legacy` (a bundle of obsolete zone aliases the
  platform does not want) onto every node to silence an error. A site that
  genuinely wants local leap tables installs `tzdata-legacy` and adds
  `leapsectz` via `host_vars`.
- **Time serving (`allow` / `local stratum`).** Serving time to peers is a
  per-site capability, not a host baseline; an isolated site that needs it adds
  it via `host_vars`.
- **File logging (`log` / `logdir`).** Kept out to stay minimal and avoid disk
  churn; chrony's events still reach the systemd journal.

## Consequences

**Positive:**

- Nodes hold accurate time through upstream outages, removing a class of silent
  TLS/etcd/kubelet failures that timesyncd would permit on intermittent links.
- timesyncd cannot race chrony: the mask is enforced and asserted (on real
  hosts), not assumed from package behaviour.
- chrony stays patchable as a security-relevant daemon, and installs reliably
  over time because nothing pins it to a version that leaves the archive.
- Each node's time configuration is a single, fully-owned, auditable file.
- The leapsectz omission is on record, so a future "Ubuntu ships it, why don't
  we" edit is answered in review rather than reintroducing a noble error.

**Negative:**

- One more package and config file to own than the noble default would require.
- The role carries the baseline chrony directives itself and will not inherit
  future changes to the distribution's shipped defaults; this is the price of
  owning the file (Decision 4).
- The service-state and mask guarantees are verified only on real hosts and at
  L1.1.7, not in molecule — consistent with every prior slice's live-action
  split (ADR-0004), but it means the container test proves artifacts only.

## Alternatives considered

- **Keep systemd-timesyncd (the noble default) and configure it.** Rejected:
  no drift discipline across outages and no serving capability — the two
  properties that matter for edge and isolated bare-metal. Zero-install
  convenience does not outweigh a correctness gap on the target shapes.
- **Pin chrony to an exact apt version and hold it, per the Kubernetes-stack
  policy (ADR-0003).** Rejected: pins age out of the archive and break installs,
  and holding a network daemon blocks security updates. The pin policy exists
  for version-skew-coupled cluster components, which chrony is not.
- **Rely on the chrony package's post-install to disable timesyncd.** Rejected:
  unconfirmed mechanism on noble, and known to leave timesyncd active until
  reboot on some paths. Explicit mask is deterministic.
- **Remove systemd-timesyncd with `apt`.** Rejected: heavier and irreversible
  relative to masking, and it perturbs the systemd package set for no added
  safety over a mask.
- **Drop-in under `/etc/chrony/conf.d/` composing with the shipped config.**
  Rejected: leaves the effective configuration split across the role's file and
  the package's, including the live Ubuntu pool source, defeating the
  single-auditable-file goal. Full ownership was chosen instead (Decision 4).
- **Include `leapsectz right/UTC` to mirror Ubuntu's default.** Rejected: on
  noble it points at absent `tzdata-legacy` data and logs a recurring error for
  no gain; see Deliberately excluded.

## References

- ADR-0003 — Kubernetes version pin and upgrade strategy; the pin-and-hold
  policy that Decision 3 deliberately does not extend to OS utilities
- ADR-0004 — `os_prep` role structure and idempotence; the persist/guarded
  split and the module-over-command rule applied here
- ADR-0009 — sysctl baseline; the prior slice and the model for recording
  deliberate exclusions
- Ubuntu Server documentation — time synchronisation; chrony as the 25.10+
  default and the `chrony.service` unit
- Launchpad #2040371, #2008076 — `right/*` zoneinfo split into `tzdata-legacy`
  and Ubuntu chrony dropping the `tzdata-legacy` dependency (Decision 4
  exclusion)
