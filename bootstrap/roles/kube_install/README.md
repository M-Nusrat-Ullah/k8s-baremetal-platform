# kube_install

Installs `kubeadm`, `kubelet`, and `kubectl` from `pkgs.k8s.io` at a
pinned version, applies a dpkg hold, and optionally pre-pulls
control-plane images before `kubeadm init`.

Runs on **every node** (control plane and workers) before cluster
formation. Does not touch the cluster itself.

## Dependencies

Must run after `os_prep` and `containerd` (swap disabled, kernel modules
loaded, `SystemdCgroup = true` set in containerd config).

## Variables

| Variable | Default | Description |
|---|---|---|
| `kubernetes.version` | `null` | Exact apt package version (e.g. `1.34.8-1.1`). **Must be set** before this role runs. Source from `apt-cache madison kubeadm`. |
| `kubernetes.apt_repo` | pkgs.k8s.io v1.34 | apt repository URL. Change to `v1.35` for the upgrade. |
| `kubernetes.apt_signing_key` | pkgs.k8s.io v1.34 | Signing key URL. Change alongside `apt_repo`. |
| `kube_prepull_images` | `true` | Run `kubeadm config images pull` before init. Set `false` in Molecule. |

## Testing

```bash
cd bootstrap/roles/kube_install
molecule create
molecule converge
molecule verify
molecule destroy
```

Run one command at a time and read the output before proceeding.

## Why no Molecule test for `kube_bootstrap`?

`kubeadm init` and `kubeadm join` require systemd as PID 1, a real
kernel, etcd I/O, and actual network interfaces. These constraints cannot
be satisfied in a Docker-driver Molecule scenario. The bootstrap role is
tested on a real host only. This is a documented, intentional gap — not
an oversight.
