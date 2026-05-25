# policies/

Kyverno `ClusterPolicy` library, split into `baseline/` (PSS, default-deny
NetworkPolicy, signature verification) and `exceptions/` (per-workload
overrides documented per PRIVILEGED_EXCEPTIONS_TEMPLATE.md).
Referenced from `gitops/infrastructure/kyverno/`. Layer 3, pending.
