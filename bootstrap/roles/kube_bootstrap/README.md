# kube_bootstrap

Forms the Kubernetes cluster via `kubeadm`. Runs after `kube_install`
has prepared every node.

## What it does (by task file)

| File | Runs on | When |
|---|---|---|
| `init.yml` | First control-plane node | Always |
| `kubeconfig.yml` | First control-plane node | Always |
| `untaint.yml` | First control-plane node | `deploy_shape == lab-single-node` |
| `join.yml` | Worker nodes | When `workers` group is populated |

## Post-init expected state (lab-single-node)

After `init.yml` completes, the cluster will look like this — **this is
correct, not a failure**:

```
NAME     STATUS     ROLES           AGE   VERSION
<node>   NotReady   control-plane   Xs    v1.34.x
```

- `NotReady` — no CNI installed yet. Cilium arrives in L2.
- CoreDNS pods `Pending` — same reason.
- No `kube-proxy` DaemonSet — skipped at init (`skipPhases: [addon/kube-proxy]`).
- Control-plane static pods + etcd: `Running`.

## Why no Molecule scenario?

`kubeadm init` requires systemd as PID 1, a real kernel, etcd I/O,
and real network interfaces. The Docker driver cannot provide these.
This is an intentional, documented gap. The role is tested on a real
host only.

## Variables

See `defaults/main.yml` for the full list with descriptions.

Key decisions baked into `templates/kubeadm-config.yaml.j2`:

- **`skipPhases: [addon/kube-proxy]`** — Cilium kube-proxy-replacement;
  never install kube-proxy.
- **`cgroupDriver` omitted** — GA CRI auto-detect in 1.34; field
  deprecated. See ADR-00XX.
- **`podSubnet` omitted** — Cilium cluster-pool IPAM. See ADR-00XX.
- **`KubeletConfiguration` omitted** — deferred to CIS kubelet hardening
  slice.
