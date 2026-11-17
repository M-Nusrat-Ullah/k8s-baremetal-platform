#!/usr/bin/env python3
"""Cilium values render gate (ADR-0030, decision 4).

Purpose
-------
Prove that every key in the committed Cilium values files is live: that the
pinned chart actually reads it. Helm silently ignores a key the chart does
not define, so a misspelled, removed or renamed key looks valid and does
nothing. The gate finds such dead keys before they reach a cluster.

Usage
-----
    cilium-render-gate.py CHART_DIR VALUES.yaml [VALUES.yaml ...]

Run it with the venv python (needs PyYAML) and the pinned helm on PATH:

    direnv exec . python scripts/cilium-render-gate.py CHART_DIR common.yaml lab.yaml

Exit code 0: every key changed the render. Exit code 1: at least one dead key.
Rerun it whenever the chart version or a values file changes.

Method
------
The values files are merged in order and the chart is rendered with
`helm template`. The chart is then rendered once more per leaf key with that
key's value changed (a boolean is flipped, a number is incremented, a list
gets an extra item, a string gets a suffix). A key whose change alters
nothing in the render is dead. A render that fails after a change means the
chart validates the key, so the key is live.

Secrets are left out of the comparison. The chart regenerates certificates
on every render, so a Secret always differs and would make every key look
live.

The ALT table
-------------
For a string key the default mutation appends "-x" to the value. If the
template branches on an enum (for example `hubble.tls.auto.method` is one of
`helm`, `cronJob`, `certmanager`), "helm-x" matches no branch and the render
does not change, so a live key is reported DEAD. That is a false positive.
ALT maps such a key to a different valid value, which is used instead of the
suffix. When a string key is reported DEAD, check whether it is an enum, add
it to ALT with another valid value, rerun, and confirm the result by hand.
"""
import copy
import os
import subprocess
import sys
import tempfile

import yaml

KUBE_VERSION = "1.36.6"

# Valid alternative values for enum-like string keys, where "<value>-x" would
# match no template branch and look dead although the key is live. Add a key
# here whenever a string key is reported DEAD, then confirm by hand.
ALT = {"hubble.tls.auto.method": "cronJob"}


def merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def leaves(d, path=()):
    for k, v in d.items():
        if isinstance(v, dict) and v:
            yield from leaves(v, path + (k,))
        else:
            yield path + (k,)


def render(chart, values):
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(values, f)
        name = f.name
    try:
        r = subprocess.run(
            ["helm", "template", "cilium", chart, "-n", "kube-system", "--kube-version", KUBE_VERSION,
             "--api-versions", "gateway.networking.k8s.io/v1/GatewayClass", "-f", name],
            capture_output=True, text=True)
    finally:
        os.unlink(name)
    if r.returncode:
        return None
    return {f"{d['kind']}/{d['metadata']['name']}": d
            for d in yaml.safe_load_all(r.stdout) if d and d["kind"] != "Secret"}


def mutate(v, key):
    if key in ALT:
        return ALT[key]
    if isinstance(v, bool):
        return not v
    if isinstance(v, (int, float)):
        return v + 1
    if isinstance(v, list):
        return v + ["x"]
    return f"{v}-x"


def main():
    chart, files = sys.argv[1], sys.argv[2:]
    base = {}
    for f in files:
        base = merge(base, yaml.safe_load(open(f, encoding="utf-8")))
    ref = render(chart, base)
    if ref is None:
        sys.exit("base render FAILED")
    print(f"base render OK: {len(ref)} objects (helm: {subprocess.getoutput('helm version --short')})")
    dead = 0
    for path in leaves(base):
        v = copy.deepcopy(base)
        d = v
        for p in path[:-1]:
            d = d[p]
        key = ".".join(path)
        d[path[-1]] = mutate(d[path[-1]], key)
        out = render(chart, v)
        if out is None:
            print(f"live (chart validates)  {key}")
        elif out == ref:
            dead += 1
            print(f"*** DEAD KEY           {key}")
        else:
            changed = sorted(k for k in set(ref) | set(out) if ref.get(k) != out.get(k))
            print(f"live                    {key}  -> {', '.join(changed[:3])}")
    print(f"dead keys: {dead}")
    sys.exit(1 if dead else 0)


if __name__ == "__main__":
    main()
